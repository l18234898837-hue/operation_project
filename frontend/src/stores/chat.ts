import { defineStore } from "pinia";
import { computed, ref, watch } from "vue";

import { askQuestionStream } from "../api/qa";
import { copyTextToClipboard } from "../chat/clipboard";
import {
  getConversationSnapshot,
  sanitizePersistedChatState,
  type ChatMessage,
  type Conversation,
  type PersistedChatState
} from "../chat/conversationModel";
import { describeAnswerType } from "../chat/qaPresentation";
import type { BackendSessionId, QaAskResponse, QaReference, QaStreamEvent } from "../types/qa";

interface ActiveStreamState {
  controller: AbortController;
  messageId: string;
  statusMessages: string[];
}

export interface ConversationHistoryItem extends Conversation {
  displayTime: string;
  displayGroup: string;
  matchedMessageSnippet: string | null;
  matchType: "title" | "message" | "title_message" | null;
}

export function shouldUseQuestionAsConversationTitle(conversation: Pick<Conversation, "messages">) {
  return !conversation.messages.some((message) => message.role === "user");
}

function createMessageId() {
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function createBackendSessionId(): BackendSessionId {
  return crypto.randomUUID() as BackendSessionId;
}

const CHAT_STORAGE_KEY = "pvqa-chat-state";

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

export function getConversationHistoryGroup(timestamp: number) {
  const date = new Date(timestamp);
  const today = new Date();
  const startOfToday = new Date(today.getFullYear(), today.getMonth(), today.getDate()).getTime();
  const startOfDate = new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime();
  const daysAgo = Math.floor((startOfToday - startOfDate) / 86_400_000);

  if (daysAgo === 0) {
    return "\u4eca\u5929";
  }

  if (daysAgo === 1) {
    return "\u6628\u5929";
  }

  return "\u66f4\u65e9";
}

export function formatConversationHistoryTime(timestamp: number) {
  const date = new Date(timestamp);

  if (getConversationHistoryGroup(timestamp) === "\u66f4\u65e9") {
    return new Intl.DateTimeFormat("zh-CN", {
      month: "2-digit",
      day: "2-digit"
    }).format(date);
  }

  return new Intl.DateTimeFormat("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false
  }).format(date);
}

function normalizeHistorySearchQuery(query: string) {
  return query.trim().toLocaleLowerCase();
}

function buildMatchedMessageSnippet(content: string, normalizedQuery: string) {
  const normalizedContent = content.toLocaleLowerCase();
  const matchIndex = normalizedContent.indexOf(normalizedQuery);

  if (matchIndex === -1) {
    return content.slice(0, 42);
  }

  const start = Math.max(0, matchIndex - 14);
  const end = Math.min(content.length, matchIndex + normalizedQuery.length + 24);
  const prefix = start > 0 ? "..." : "";
  const suffix = end < content.length ? "..." : "";

  return `${prefix}${content.slice(start, end)}${suffix}`;
}

function getHistorySearchMatch(conversation: Conversation, normalizedQuery: string) {
  if (!normalizedQuery) {
    return {
      matchedMessageSnippet: null,
      matchType: null
    } satisfies Pick<ConversationHistoryItem, "matchedMessageSnippet" | "matchType">;
  }

  const titleMatches = conversation.title.toLocaleLowerCase().includes(normalizedQuery);
  const matchedMessage = conversation.messages.find((message) =>
    message.content.toLocaleLowerCase().includes(normalizedQuery)
  );

  if (!titleMatches && !matchedMessage) {
    return null;
  }

  return {
    matchedMessageSnippet: matchedMessage ? buildMatchedMessageSnippet(matchedMessage.content, normalizedQuery) : null,
    matchType: titleMatches && matchedMessage ? "title_message" : titleMatches ? "title" : "message"
  } satisfies Pick<ConversationHistoryItem, "matchedMessageSnippet" | "matchType">;
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

function readPersistedChatState(): PersistedChatState {
  if (typeof window === "undefined") {
    return { conversations: [], activeConversationId: null };
  }

  const rawState = window.localStorage.getItem(CHAT_STORAGE_KEY);

  if (!rawState) {
    return { conversations: [], activeConversationId: null };
  }

  try {
    return sanitizePersistedChatState(JSON.parse(rawState));
  } catch {
    return { conversations: [], activeConversationId: null };
  }
}

function persistChatState(state: PersistedChatState) {
  if (typeof window === "undefined") {
    return;
  }

  window.localStorage.setItem(CHAT_STORAGE_KEY, JSON.stringify(sanitizePersistedChatState(state)));
}

export const useChatStore = defineStore("chat", () => {
  const persistedState = readPersistedChatState();
  const question = ref("");
  const conversations = ref<Conversation[]>(persistedState.conversations);
  const activeConversationId = ref<string | null>(persistedState.activeConversationId);
  const historyQuery = ref("");
  const lastQuestion = ref("");
  const errorMessage = ref("");
  const copyMessage = ref("");
  const streamStatusMessages = ref<string[]>([]);
  const activeStreams = ref(new Map<string, ActiveStreamState>());

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
  const activeStreamController = computed(() =>
    activeConversationId.value ? activeStreams.value.get(activeConversationId.value)?.controller ?? null : null
  );
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
  const derivedHistoryGroups = computed(() => {
    const normalizedQuery = normalizeHistorySearchQuery(historyQuery.value);
    const groupLabels = ["\u4eca\u5929", "\u6628\u5929", "\u66f4\u65e9"];
    const matchedConversations = conversations.value
      .map((conversation) => {
        const match = getHistorySearchMatch(conversation, normalizedQuery);

        if (!match) {
          return null;
        }

        return { conversation, match };
      })
      .filter((item) => item !== null);
    const sortedConversations = [...matchedConversations].sort(
      (left, right) => right.conversation.updatedAt - left.conversation.updatedAt
    );

    return groupLabels
      .map((label) => {
        const items: ConversationHistoryItem[] = sortedConversations
          .filter(({ conversation }) => getConversationHistoryGroup(conversation.updatedAt) === label)
          .map(({ conversation, match }) => ({
            ...conversation,
            displayGroup: label,
            displayTime: formatConversationHistoryTime(conversation.updatedAt),
            matchedMessageSnippet: match.matchedMessageSnippet,
            matchType: match.matchType
          }));

        return { label, items };
      })
      .filter((group) => group.items.length > 0);
  });
  const isHistorySearching = computed(() => normalizeHistorySearchQuery(historyQuery.value).length > 0);
  const historySearchResultCount = computed(() =>
    derivedHistoryGroups.value.reduce((total, group) => total + group.items.length, 0)
  );
  const hasHistorySearchResults = computed(
    () => !isHistorySearching.value || historySearchResultCount.value > 0
  );

  watch(
    [conversations, activeConversationId],
    () => {
      persistChatState({
        conversations: conversations.value,
        activeConversationId: activeConversationId.value
      });
    },
    { deep: true }
  );

  watch(
    [activeStreams, activeConversationId],
    () => {
      streamStatusMessages.value = activeConversationId.value
        ? activeStreams.value.get(activeConversationId.value)?.statusMessages ?? []
        : [];
    },
    { deep: true }
  );

  function isStreamingStatus(value: string) {
    return value === "asking" || value === "streaming";
  }

  function getActiveConversation() {
    return conversations.value.find((conversation) => conversation.id === activeConversationId.value) ?? null;
  }

  function isActiveConversation(conversationId: string) {
    return activeConversationId.value === conversationId;
  }

  function triggerConversationRender() {
    conversations.value = [...conversations.value];
  }

  function setActiveStreamState(conversationId: string, state: ActiveStreamState) {
    const nextStreams = new Map(activeStreams.value);
    nextStreams.set(conversationId, state);
    activeStreams.value = nextStreams;
  }

  function removeActiveStreamState(conversationId: string, controller?: AbortController) {
    const streamState = activeStreams.value.get(conversationId);

    if (!streamState || (controller && streamState.controller !== controller)) {
      return;
    }

    const nextStreams = new Map(activeStreams.value);
    nextStreams.delete(conversationId);
    activeStreams.value = nextStreams;
  }

  function clearActiveStreamStatus(conversationId: string) {
    const streamState = activeStreams.value.get(conversationId);

    if (streamState) {
      setActiveStreamState(conversationId, { ...streamState, statusMessages: [] });
    }
  }

  function setActiveStreamStatus(conversationId: string, message: string) {
    const streamState = activeStreams.value.get(conversationId);
    const normalizedMessage = message.trim();

    if (!streamState || !normalizedMessage) {
      return;
    }

    const lastMessage = streamState.statusMessages.at(-1);
    if (lastMessage === normalizedMessage) {
      return;
    }

    setActiveStreamState(conversationId, {
      ...streamState,
      statusMessages: [...streamState.statusMessages, normalizedMessage]
    });
  }

  function setActiveStreamError(conversationId: string, message: string) {
    if (isActiveConversation(conversationId)) {
      errorMessage.value = message;
    }

    clearActiveStreamStatus(conversationId);
  }

  function abortConversationStream(conversationId: string, markInterrupted = true) {
    const streamState = activeStreams.value.get(conversationId);

    if (!streamState) {
      return;
    }

    streamState.controller.abort();

    if (markInterrupted) {
      const conversation = conversations.value.find((item) => item.id === conversationId);
      const message = conversation?.messages.find((item) => item.id === streamState.messageId);

      if (conversation && message && isStreamingStatus(conversation.status)) {
        conversation.status = "error";
        message.status = "error";
        message.content = message.content.trim() || "回答已中断";
        updateConversationTimestamp(conversation);
      }
    }

    removeActiveStreamState(conversationId, streamState.controller);
  }

  function abortAllStreams() {
    Array.from(activeStreams.value.keys()).forEach((conversationId) => abortConversationStream(conversationId));
  }

  function updateConversationTimestamp(conversation: Conversation, timestamp = Date.now()) {
    conversation.updatedAt = timestamp;
    conversation.time = currentHistoryTime(timestamp);
    conversation.group = getConversationGroup(timestamp);
  }

  function newConversation() {
    activeConversationId.value = null;
    question.value = "";
    errorMessage.value = "";
    copyMessage.value = "";
  }

  function clearHistorySearch() {
    historyQuery.value = "";
  }

  function deleteConversation(conversationId: string) {
    const isDeletingActive = activeConversationId.value === conversationId;
    const isDeletingStreamingConversation = activeStreams.value.has(conversationId);

    if (isDeletingStreamingConversation) {
      abortConversationStream(conversationId, false);
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
      if (shouldUseQuestionAsConversationTitle(existingConversation)) {
        existingConversation.title = normalizedQuestion;
      }

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
    abortConversationStream(conversationId);

    const controller = new AbortController();
    const initialStatusMessages = ["已提交问题，等待服务响应..."];
    if (isActiveConversation(conversationId)) {
      streamStatusMessages.value = initialStatusMessages;
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
      return;
    }

    conversation.status = "asking";
    conversation.messages = [...conversation.messages, assistantMessage];
    triggerConversationRender();
    setActiveStreamState(conversationId, {
      controller,
      messageId: assistantMessage.id,
      statusMessages: initialStatusMessages
    });

    let streamedAnswer = "";
    let streamedReferences: QaReference[] = [];

    function isCurrentStream() {
      return (
        activeStreams.value.get(conversationId)?.controller === controller &&
        conversations.value.some((item) => item.id === conversationId)
      );
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
          triggerConversationRender();
          break;
        case "references":
          streamedReferences = event.data.references;
          targetMessage.response = buildStreamingResponse(
            targetMessage.response,
            targetConversation.backendSessionId ?? backendSessionId,
            streamedAnswer,
            streamedReferences
          );
          triggerConversationRender();
          break;
        case "done":
          targetConversation.backendSessionId = event.data.session_id;
          targetConversation.status = event.data.answer_type === "refused" ? "refused" : "answered";
          targetMessage.content = event.data.answer;
          targetMessage.response = event.data;
          targetMessage.status = "complete";
          triggerConversationRender();
          clearActiveStreamStatus(conversationId);
          updateConversationTimestamp(targetConversation);
          removeActiveStreamState(conversationId, controller);
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
      if (activeStreams.value.get(conversationId)?.controller === controller) {
        clearActiveStreamStatus(conversationId);
        removeActiveStreamState(conversationId, controller);
      }
    }
  }

  function selectConversation(conversationId: string) {
    activeConversationId.value = conversationId;
    errorMessage.value = "";
    copyMessage.value = "";
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
    abortAllStreams();
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
    streamStatusMessages,
    activeStreamController,
    activeSnapshot,
    status,
    messages,
    latestResponse,
    pageTitle,
    answerDescription,
    canSend,
    historyGroups: derivedHistoryGroups,
    hasHistorySearchResults,
    historySearchResultCount,
    isHistorySearching,
    newConversation,
    clearHistorySearch,
    deleteConversation,
    sendQuestion,
    selectConversation,
    retryLastQuestion,
    copyAnswer,
    logout
  };
});
