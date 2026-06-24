<script setup lang="ts">
import type { ChatMessage } from "../../chat/conversationModel";
import SourceReferences from "./SourceReferences.vue";
import FeedbackBar from "./FeedbackBar.vue";

defineProps<{
  message: ChatMessage;
}>();

defineEmits<{
  copy: [content: string];
  retry: [];
}>();
</script>

<template>
  <article :class="['chat-message', message.role]">
    <time>{{ message.createdAt }}</time>
    <div class="message-bubble">
      <p>{{ message.content }}</p>
      <SourceReferences v-if="message.response?.references.length" :references="message.response.references" />
    </div>

    <FeedbackBar
      v-if="message.role === 'assistant'"
      @copy="$emit('copy', message.content)"
      @retry="$emit('retry')"
    />
  </article>
</template>
