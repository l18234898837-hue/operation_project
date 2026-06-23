<script setup lang="ts">
import { CopyDocument, Refresh } from "@element-plus/icons-vue";

defineEmits<{
  copy: [];
  retry: [];
}>();
</script>

<template>
  <div class="answer-actions">
    <button type="button" @click="$emit('copy')">
      <CopyDocument aria-hidden="true" />
      复制
    </button>
    <button type="button" @click="$emit('retry')">
      <Refresh aria-hidden="true" />
      重新生成
    </button>
  </div>
</template>
