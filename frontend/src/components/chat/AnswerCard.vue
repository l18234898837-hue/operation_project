<script setup lang="ts">
import { UserFilled } from "@element-plus/icons-vue";

import type { ChatMessage } from "../../chat/conversationModel";
import type { AnswerTypeDescription } from "../../chat/qaPresentation";
import logoUrl from "../../assets/logo-transparent.png";
import FeedbackBar from "./FeedbackBar.vue";
import MarkdownAnswer from "./MarkdownAnswer.vue";
import SourceReferences from "./SourceReferences.vue";

withDefaults(
  defineProps<{
    message: ChatMessage;
    answerDescription: AnswerTypeDescription;
    canRetry?: boolean;
    statusText?: string;
  }>(),
  {
    canRetry: false,
    statusText: ""
  }
);

defineEmits<{
  copy: [content: string];
  retry: [assistantMessageId?: string];
}>();
</script>

<template>
  <article :class="['chat-message', message.role, message.status]">
    <div class="chat-message-row">
      <span
        v-if="message.role === 'assistant'"
        class="message-avatar assistant-avatar"
        aria-label="系统助手"
      >
        <img :src="logoUrl" alt="" />
      </span>

      <div class="message-stack">
        <time>{{ message.createdAt }}</time>
        <div class="message-bubble">
          <div v-if="message.role === 'assistant'" class="assistant-answer-body">
            <p v-if="message.status === 'streaming' && !message.content">{{ statusText || "正在生成回答..." }}</p>
            <MarkdownAnswer v-else :content="message.content" />
            <span
              v-if="message.status === 'streaming'"
              class="stream-cursor"
              aria-hidden="true"
            ></span>
          </div>
          <p v-else>{{ message.content }}</p>

          <SourceReferences
            v-if="message.response?.references.length"
            :answer-description="answerDescription"
            :confidence="message.response.confidence"
            :references="message.response.references"
          />
        </div>
      </div>

      <span
        v-if="message.role === 'user'"
        class="message-avatar user-message-avatar"
        aria-label="用户"
      >
        <UserFilled aria-hidden="true" />
      </span>
    </div>

    <FeedbackBar
      v-if="message.role === 'assistant' && message.status !== 'streaming'"
      :show-copy="message.status !== 'error'"
      :show-retry="canRetry"
      @copy="$emit('copy', message.content)"
      @retry="$emit('retry', message.id)"
    />
  </article>
</template>
