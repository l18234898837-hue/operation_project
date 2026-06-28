<script setup lang="ts">
import { nextTick, ref, watch } from "vue";

import logoUrl from "../../assets/logo-transparent.png";
import { recommendedQuestions } from "../../chat/recommendedQuestions";
import type { AnswerTypeDescription } from "../../chat/qaPresentation";
import { canRegenerateAssistantMessage } from "../../chat/retryVisibility";
import type { ChatMessage, ChatStatus } from "../../chat/conversationModel";
import AnswerCard from "./AnswerCard.vue";
import ChatComposer from "./ChatComposer.vue";
import RecommendedQuestions from "./RecommendedQuestions.vue";

const question = defineModel<string>("question", { required: true });

const props = withDefaults(defineProps<{
  pageTitle: string;
  messages: ChatMessage[];
  status: ChatStatus;
  answerDescription: AnswerTypeDescription;
  canSend: boolean;
  copyMessage: string;
  errorMessage: string;
  streamStatusMessage?: string;
}>(), {
  streamStatusMessage: ""
});

const emit = defineEmits<{
  send: [];
  ask: [question: string];
  retry: [assistantMessageId?: string];
  copy: [content: string];
}>();

const transcriptRef = ref<HTMLElement | null>(null);

async function scrollToBottom() {
  await nextTick();
  transcriptRef.value?.scrollTo({
    top: transcriptRef.value.scrollHeight,
    behavior: "smooth"
  });
}

watch(
  () => [
    props.messages.length,
    props.status,
    props.messages.at(-1)?.content.length ?? 0,
    props.streamStatusMessage
  ],
  () => {
    void scrollToBottom();
  }
);
</script>

<template>
  <section class="chat-workspace">
    <header class="chat-workspace-head" :class="{ compact: messages.length > 0 }">
      <div>
        <h1>{{ pageTitle }}</h1>
      </div>
    </header>

    <div ref="transcriptRef" class="chat-transcript">
      <section v-if="messages.length === 0" class="chat-empty-state">
        <img :src="logoUrl" alt="" />
        <h2>你好，张工，有什么光伏运维问题需要查询？</h2>
        <p>系统将基于企业知识库回答，并提供可追溯来源</p>

        <RecommendedQuestions :items="recommendedQuestions" @ask="emit('ask', $event)" />
      </section>

      <template v-else>
        <AnswerCard
          v-for="message in messages"
          :key="message.id"
          :answer-description="answerDescription"
          :can-retry="canRegenerateAssistantMessage(messages, message)"
          :message="message"
          :status-text="streamStatusMessage"
          @copy="emit('copy', $event)"
          @retry="emit('retry', $event)"
        />
      </template>
    </div>

    <p v-if="copyMessage" class="copy-feedback" role="status">{{ copyMessage }}</p>

    <ChatComposer
      v-model="question"
      :disabled="status === 'asking' || status === 'streaming'"
      :can-send="canSend"
      :sending="status === 'asking' || status === 'streaming'"
      @send="emit('send')"
    />
  </section>
</template>
