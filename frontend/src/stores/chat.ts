import { defineStore } from "pinia";
import { computed, ref } from "vue";

import { askQuestionStream } from "../api/qa";
import { copyTextToClipboard } from "../chat/clipboard";
import { getConversationSnapshot, type ChatMessage, type Conversation } from "../chat/conversationModel";
import { describeAnswerType } from "../chat/qaPresentation";
import type { BackendSessionId, QaAskResponse, QaReference, QaStreamEvent } from "../types/qa";

function createMessageId() {
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function createBackendSessionId(): BackendSessionId {
  return crypto.randomUUID() as BackendSessionId;
}

function getConversationGroup(timestamp: number) {
  const date = new Date(timestamp);
  const today = new Date();
  const startOfToday = new Date(today.getFullYear(), today.getMonth(), today.getDate()).getTime();
  const startOfDate = new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime();
  const daysAgo = Math.floor((startOfToday - startOfDate) / 86_400_000);

  if (daysAgo === 0) {
    return "今天";
  }

  if (daysAgo === 1) {
    return "昨天";
  }

  return "更早";
}

export function currentChatTime() {
  return new Intl.DateTimeFormat("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false
  }).format(new Date());
}

function currentHistoryTime(timestamp: number) {
  const now = new Date(timestamp);
  const group = getConversationGroup(timestamp);

  if (group === "更早") {
    return new Intl.DateTimeFormat("zh-CN", {
      month: "2-digit",
      day: "2-digit"
    }).format(now);
  }

  return new Intl.DateTimeFormat("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false
  }).format(now);
}

function buildStreamingResponse(
  previousResponse: QaAskResponse | undefined,
  sessionId: BackendSessionId,
  answer: string,
  references: QaReference[]
): QaAskResponse {
  return {
    session_id: sessionId,
    trace_id: previousResponse?.trace_id ?? "",
    answer_type: previousResponse?.answer_type ?? "none",
    intent: previousResponse?.intent ?? "general_explanation",
    answer,
    confidence: previousResponse?.confidence ?? null,
    references,
    decision: previousResponse?.decision ?? {}
  };
}

export const useChatStore = defineStore("chat", () => {
  const question = ref("");
  const conversations = ref<Conversation[]>([]);
  const activeConversationId = ref<string | null>(null);
  const historyQuery = ref("");
  const lastQuestion = ref("");
  const errorMessage = ref("");
  const copyMessage = ref("");
  const streamStatusMessage = ref("");
  const activeStreamController = ref<AbortController | null>(null);
  const activeStreamConversationId = ref<string | null>(null);
  const activeStreamMessageId = ref<string | null>(null);

  const activeSnapshot = computed(() => getConversationSnapshot(conversations.value, activeConversationId.value));
  const status = computed(() => activeSnapshot.value.status);
  const messages = computed(() => activeSnapshot.value.messages);
  const latestResponse = computed(() => {
    const assistantMessages = messages.value.filter((message) => message.role === "assistant");
    return assistantMessages.at(-1)?.response ?? null;
  });
  const pageTitle = computed(() => activeSnapshot.value.title);
  const answerDescription = computed(() =>
    latestResponse.value ? describeAnswerType(latestResponse.value.answer_type) : describeAnswerType("none")
  );
  const canSend = computed(() => question.value.trim().length > 0 && !isStreamingStatus(status.value));
  const historyGroups = computed(() => {
    const normalizedQuery = historyQuery.value.trim().toLocaleLowerCase();
    const groupLabels = ["今天", "昨天", "更早"];
    const filteredConversations = conversations.value.filter((conversation) => {
      if (!normalizedQuery) {
        return true;
      }

      const titleMatches = conversation.title.toLocaleLowerCase().includes(normalizedQuery);
      const messageMatches = conversation.messages.some((message) =>
        message.content.toLocaleLowerCase().includes(normalizedQuery)
      );

      return titleMatches || messageMatches;
    });

    return groupLabels
      .map((label) => ({
        label,
        items: filteredConversations.filter((conversation) => conversation.group === label)
      }))
      .filter((group) => group.items.length > 0);
  });
  const hasHistorySearchResults = computed(() => historyQuery.value.trim().length === 0 || historyGroups.value.length > 0);

  function isStreamingStatus(value: string) {
    return value === "asking" || value === "streaming";
  }

  function getActiveConversation() {
    return conversations.value.find((conversation) => conversation.id === activeConversationId.value) ?? null;
  }

  function isActiveConversation(conversationId: string) {
    return activeConversationId.value === conversationId;
  }

  function clearActiveStreamStatus(conversationId: string) {
    if (isActiveConversation(conversationId)) {
      streamStatusMessage.value = "";
    }
  }

  function setActiveStreamStatus(conversationId: string, message: string) {
    if (isActiveConversation(conversationId)) {
      streamStatusMessage.value = message;
    }
  }

  function setActiveStreamError(conversationId: string, message: string) {
    if (isActiveConversation(conversationId)) {
      errorMessage.value = message;
      streamStatusMessage.value = "";
    }
  }

  function abortActiveStream() {
    const streamConversationId = activeStreamConversationId.value;
    const streamMessageId = activeStreamMessageId.value;

    activeStreamController.value?.abort();

    if (streamConversationId && streamMessageId) {
      const conversation = conversations.value.find((item) => item.id === streamConversationId);
      const message = conversation?.messages.find((item) => item.id === streamMessageId);

      if (conversation && message && isStreamingStatus(conversation.status)) {
        conversation.status = "error";
        message.status = "error";
        message.content = message.content.trim() || "回答已中断";
        updateConversationTimestamp(conversation);
      }
    }

    activeStreamController.value = null;
    activeStreamConversationId.value = null;
    activeStreamMessageId.value = null;
    streamStatusMessage.value = "";
  }

  function updateConversationTimestamp(conversation: Conversation, timestamp = Date.now()) {
    conversation.updatedAt = timestamp;
    conversation.time = currentHistoryTime(timestamp);
    conversation.group = getConversationGroup(timestamp);
  }

  function newConversation() {
    abortActiveStream();
    activeConversationId.value = null;
    question.value = "";
    errorMessage.value = "";
    copyMessage.value = "";
  }

  function deleteConversation(conversationId: string) {
    const isDeletingActive = activeConversationId.value === conversationId;
    const isDeletingStreamingConversation = activeStreamConversationId.value === conversationId;

    if (isDeletingActive || isDeletingStreamingConversation) {
      abortActiveStream();
    }

    if (isDeletingActive) {
      activeConversationId.value = null;
      question.value = "";
      errorMessage.value = "";
      copyMessage.value = "";
    }

    conversations.value = conversations.value.filter((conversation) => conversation.id !== conversationId);
  }

  async function sendQuestion(nextQuestion = question.value) {
    const normalizedQuestion = nextQuestion.trim();

    if (!normalizedQuestion || isStreamingStatus(status.value)) {
      return;
    }

    const timestamp = Date.now();
    const conversationId = activeConversationId.value ?? createMessageId();
    const existingConversation = conversations.value.find((conversation) => conversation.id === conversationId);
    const backendSessionId = existingConversation?.backendSessionId ?? createBackendSessionId();
    const userMessage: ChatMessage = {
      id: createMessageId(),
      role: "user",
      content: normalizedQuestion,
      createdAt: currentChatTime(),
      status: "complete"
    };

    question.value = "";
    lastQuestion.value = normalizedQuestion;
    activeConversationId.value = conversationId;

    if (existingConversation) {
      existingConversation.title = normalizedQuestion;
      existingConversation.backendSessionId = backendSessionId;
      existingConversation.status = "asking";
      existingConversation.messages = [...existingConversation.messages, userMessage];
      updateConversationTimestamp(existingConversation, timestamp);
    } else {
      conversations.value.unshift({
        id: conversationId,
        backendSessionId,
        title: normalizedQuestion,
        time: currentHistoryTime(timestamp),
        group: getConversationGroup(timestamp),
        status: "asking",
        messages: [userMessage],
        createdAt: timestamp,
        updatedAt: timestamp
      });
    }

    await sendQuestionFromExistingTurn(conversationId, normalizedQuestion, backendSessionId);
  }

  async function sendQuestionFromExistingTurn(
    conversationId: string,
    normalizedQuestion: string,
    backendSessionId: BackendSessionId
  ) {
    abortActiveStream();

    const controller = new AbortController();
    activeStreamController.value = controller;
    if (isActiveConversation(conversationId)) {
      streamStatusMessage.value = "正在理解问题...";
      errorMessage.value = "";
      copyMessage.value = "";
    }

    const assistantMessage: ChatMessage = {
      id: createMessageId(),
      role: "assistant",
      content: "",
      createdAt: currentChatTime(),
      status: "streaming"
    };
    const conversation = conversations.value.find((item) => item.id === conversationId);

    if (!conversation) {
      activeStreamController.value = null;
      return;
    }

    conversation.status = "asking";
    conversation.messages = [...conversation.messages, assistantMessage];
    activeStreamConversationId.value = conversationId;
    activeStreamMessageId.value = assistantMessage.id;

    let streamedAnswer = "";
    let streamedReferences: QaReference[] = [];

    function isCurrentStream() {
      return activeStreamController.value === controller && conversations.value.some((item) => item.id === conversationId);
    }

    function findConversationAndMessage() {
      const targetConversation = conversations.value.find((item) => item.id === conversationId);
      const targetMessage = targetConversation?.messages.find((message) => message.id === assistantMessage.id);

      if (!targetConversation || !targetMessage || !isCurrentStream()) {
        return null;
      }

      return { targetConversation, targetMessage };
    }

    function applyStreamEvent(event: QaStreamEvent) {
      const target = findConversationAndMessage();

      if (!target) {
        return;
      }

      const { targetConversation, targetMessage } = target;

      switch (event.event) {
        case "status":
          setActiveStreamStatus(conversationId, event.data.message);
          if (event.data.stage === "generating") {
            targetConversation.status = "streaming";
          }
          break;
        case "answer_delta":
          streamedAnswer += event.data.text;
          targetConversation.status = "streaming";
          targetMessage.content = streamedAnswer;
          targetMessage.status = "streaming";
          targetMessage.response = buildStreamingResponse(
            targetMessage.response,
            targetConversation.backendSessionId ?? backendSessionId,
            streamedAnswer,
            streamedReferences
          );
          break;
        case "references":
          streamedReferences = event.data.references;
          targetMessage.response = buildStreamingResponse(
            targetMessage.response,
            targetConversation.backendSessionId ?? backendSessionId,
            streamedAnswer,
            streamedReferences
          );
          break;
        case "done":
          targetConversation.backendSessionId = event.data.session_id;
          targetConversation.status = event.data.answer_type === "refused" ? "refused" : "answered";
          targetMessage.content = event.data.answer;
          targetMessage.response = event.data;
          targetMessage.status = "complete";
          clearActiveStreamStatus(conversationId);
          updateConversationTimestamp(targetConversation);
          if (activeStreamController.value === controller) {
            activeStreamController.value = null;
            activeStreamConversationId.value = null;
            activeStreamMessageId.value = null;
          }
          break;
        case "error":
          setActiveStreamError(conversationId, "问答接口暂时不可用，请稍后重试。");
          targetConversation.status = "error";
          targetMessage.status = "error";
          targetMessage.content = streamedAnswer || event.data.message || "回答生成失败";
          updateConversationTimestamp(targetConversation);
          break;
      }
    }

    try {
      await askQuestionStream(
        { question: normalizedQuestion, session_id: backendSessionId },
        {
          signal: controller.signal,
          onEvent: applyStreamEvent
        }
      );
    } catch {
      const target = findConversationAndMessage();

      if (!target || controller.signal.aborted) {
        return;
      }

      setActiveStreamError(conversationId, "问答接口暂时不可用，请稍后重试。");
      target.targetConversation.status = "error";
      target.targetMessage.status = "error";
      target.targetMessage.content = streamedAnswer || "回答生成失败";
      updateConversationTimestamp(target.targetConversation);
    } finally {
      if (activeStreamController.value === controller) {
        clearActiveStreamStatus(conversationId);
        activeStreamController.value = null;
        activeStreamConversationId.value = null;
        activeStreamMessageId.value = null;
      }
    }
  }

  function selectConversation(conversationId: string) {
    activeConversationId.value = conversationId;
    errorMessage.value = "";
    copyMessage.value = "";
    streamStatusMessage.value = "";
  }

  function findRetryUserIndex(conversation: Conversation, assistantMessageId?: string) {
    const startIndex = assistantMessageId
      ? conversation.messages.findIndex(
          (message) => message.id === assistantMessageId && message.role === "assistant"
        )
      : conversation.messages.length - 1;

    if (startIndex === -1) {
      return -1;
    }

    for (let index = startIndex; index >= 0; index -= 1) {
      if (conversation.messages[index]?.role === "user") {
        return index;
      }
    }

    return -1;
  }

  function retryLastQuestion(assistantMessageId?: string) {
    const conversation = getActiveConversation();

    if (!conversation || isStreamingStatus(conversation.status)) {
      return;
    }

    const userMessageIndex = findRetryUserIndex(conversation, assistantMessageId);

    if (userMessageIndex === -1) {
      return;
    }

    const userMessage = conversation.messages[userMessageIndex];
    conversation.messages = conversation.messages.slice(0, userMessageIndex + 1);
    conversation.status = "asking";
    lastQuestion.value = userMessage.content;

    void sendQuestionFromExistingTurn(
      conversation.id,
      userMessage.content,
      conversation.backendSessionId ?? createBackendSessionId()
    );
  }

  async function copyAnswer(answer = latestResponse.value?.answer ?? "") {
    const result = await copyTextToClipboard(answer);
    copyMessage.value = result.ok ? "回答已复制到剪贴板" : "复制失败，请手动选中回答文本复制";
  }

  function logout() {
    abortActiveStream();
    localStorage.removeItem("pvqa-role");
  }

  return {
    question,
    conversations,
    activeConversationId,
    historyQuery,
    lastQuestion,
    errorMessage,
    copyMessage,
    streamStatusMessage,
    activeStreamController,
    activeSnapshot,
    status,
    messages,
    latestResponse,
    pageTitle,
    answerDescription,
    canSend,
    historyGroups,
    hasHistorySearchResults,
    newConversation,
    deleteConversation,
    sendQuestion,
    selectConversation,
    retryLastQuestion,
    copyAnswer,
    logout
  };
});
