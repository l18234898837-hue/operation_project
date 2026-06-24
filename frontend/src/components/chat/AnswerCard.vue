<script setup lang="ts">
import type { ChatMessage } from "../../chat/conversationModel";
import SourceReferences from "./SourceReferences.vue";
import FeedbackBar from "./FeedbackBar.vue";

withDefaults(defineProps<{
  message: ChatMessage;
  statusText?: string;
}>(), {
  statusText: ""
});

defineEmits<{
  copy: [content: string];
  retry: [assistantMessageId?: string];
}>();
</script>

<template>
  <article :class="['chat-message', message.role, message.status]">
    <time>{{ message.createdAt }}</time>
    <div class="message-bubble">
      <p>
        {{
          message.role === "assistant" && message.status === "streaming" && !message.content
            ? statusText || "正在生成回答..."
            : message.content
        }}<span
          v-if="message.role === 'assistant' && message.status === 'streaming'"
          class="stream-cursor"
          aria-hidden="true"
        ></span>
      </p>
      <SourceReferences v-if="message.response?.references.length" :references="message.response.references" />
    </div>

    <FeedbackBar
      v-if="message.role === 'assistant' && message.status !== 'streaming'"
      :show-copy="message.status !== 'error'"
      @copy="$emit('copy', message.content)"
      @retry="$emit('retry', message.id)"
    />
  </article>
</template>
