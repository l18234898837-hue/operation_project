<script setup lang="ts">
import { CopyDocument, Refresh } from "@element-plus/icons-vue";

withDefaults(defineProps<{
  showCopy?: boolean;
  showRetry?: boolean;
}>(), {
  showCopy: true,
  showRetry: true
});

defineEmits<{
  copy: [];
  retry: [];
}>();
</script>

<template>
  <div class="answer-actions">
    <button v-if="showCopy" type="button" @click="$emit('copy')">
      <CopyDocument aria-hidden="true" />
      复制
    </button>
    <button v-if="showRetry" type="button" @click="$emit('retry')">
      <Refresh aria-hidden="true" />
      重新生成
    </button>
  </div>
</template>
