import { defineStore } from "pinia";
import { computed, ref } from "vue";

import { askQuestion } from "../api/qa";
import { copyTextToClipboard } from "../chat/clipboard";
import { getConversationSnapshot, type ChatMessage, type Conversation } from "../chat/conversationModel";
import { initialConversations } from "../chat/initialConversations";
import { describeAnswerType } from "../chat/qaPresentation";

function createMessageId() {
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

export function currentChatTime() {
  return new Intl.DateTimeFormat("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false
  }).format(new Date());
}

export const useChatStore = defineStore("chat", () => {
  const question = ref("");
  const conversations = ref<Conversation[]>(structuredClone(initialConversations));
  const activeConversationId = ref<string | null>(null);
  const lastQuestion = ref("");
  const errorMessage = ref("");
  const copyMessage = ref("");

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
  const canSend = computed(() => question.value.trim().length > 0 && status.value !== "asking");
  const historyGroups = computed(() => {
    const groupLabels = ["今天", "昨天", "更早"];

    return groupLabels
      .map((label) => ({
        label,
        items: conversations.value.filter((conversation) => conversation.group === label)
      }))
      .filter((group) => group.items.length > 0);
  });

  async function sendQuestion(nextQuestion = question.value) {
    const normalizedQuestion = nextQuestion.trim();

    if (!normalizedQuestion || status.value === "asking") {
      return;
    }

    const conversationId = activeConversationId.value ?? createMessageId();
    const existingConversation = conversations.value.find((conversation) => conversation.id === conversationId);
    const userMessage: ChatMessage = {
      id: createMessageId(),
      role: "user",
      content: normalizedQuestion,
      createdAt: currentChatTime()
    };

    question.value = "";
    lastQuestion.value = normalizedQuestion;
    errorMessage.value = "";
    activeConversationId.value = conversationId;

    if (existingConversation) {
      existingConversation.title = normalizedQuestion;
      existingConversation.time = userMessage.createdAt;
      existingConversation.status = "asking";
      existingConversation.messages = [...existingConversation.messages, userMessage];
    } else {
      conversations.value.unshift({
        id: conversationId,
        title: normalizedQuestion,
        time: userMessage.createdAt,
        group: "今天",
        status: "asking",
        messages: [userMessage]
      });
    }

    try {
      const response = await askQuestion({ question: normalizedQuestion, session_id: conversationId });
      const conversation = conversations.value.find((item) => item.id === conversationId);
      const assistantMessage: ChatMessage = {
        id: createMessageId(),
        role: "assistant",
        content: response.answer,
        createdAt: currentChatTime(),
        response
      };

      if (conversation) {
        conversation.messages = [...conversation.messages, assistantMessage];
        conversation.status = response.answer_type === "refused" ? "refused" : "answered";
      }
    } catch {
      const conversation = conversations.value.find((item) => item.id === conversationId);
      errorMessage.value = "问答接口暂时不可用，请确认后端服务已启动后重试。";

      if (conversation) {
        conversation.status = "error";
      }
    }
  }

  function selectConversation(conversationId: string) {
    activeConversationId.value = conversationId;
    errorMessage.value = "";
    copyMessage.value = "";
  }

  function retryLastQuestion() {
    if (lastQuestion.value) {
      void sendQuestion(lastQuestion.value);
    }
  }

  async function copyAnswer(answer = latestResponse.value?.answer ?? "") {
    const result = await copyTextToClipboard(answer);
    copyMessage.value = result.ok ? "回答已复制到剪贴板" : "复制失败，请手动选中回答文本复制";
  }

  return {
    question,
    conversations,
    activeConversationId,
    lastQuestion,
    errorMessage,
    copyMessage,
    activeSnapshot,
    status,
    messages,
    latestResponse,
    pageTitle,
    answerDescription,
    canSend,
    historyGroups,
    sendQuestion,
    selectConversation,
    retryLastQuestion,
    copyAnswer
  };
});
