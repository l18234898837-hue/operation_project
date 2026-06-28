<script setup lang="ts">
import { Promotion } from "@element-plus/icons-vue";

defineProps<{
  disabled: boolean;
  canSend: boolean;
  sending: boolean;
}>();

const model = defineModel<string>({ required: true });

defineEmits<{
  send: [];
}>();
</script>

<template>
  <form class="chat-composer" @submit.prevent="$emit('send')">
    <div class="composer-input-stack">
      <textarea
        v-model="model"
        :disabled="disabled"
        rows="1"
        aria-label="输入你的问题"
        placeholder="请输入你的问题"
        title="按 Enter 发送，按 Shift+Enter 换行"
        @keydown.enter.exact.prevent="$emit('send')"
      />
      <p class="composer-shortcut-hint" aria-label="Enter 发送，Shift 加 Enter 换行">
        <span><kbd>Enter</kbd> 发送</span>
        <span><kbd>Shift</kbd><i>+</i><kbd>Enter</kbd> 换行</span>
      </p>
    </div>
    <button :disabled="!canSend" type="submit">
      <Promotion aria-hidden="true" />
      <span>{{ sending ? "发送中" : "发送" }}</span>
    </button>
  </form>
</template>
