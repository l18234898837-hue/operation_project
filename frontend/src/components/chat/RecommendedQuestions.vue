<script setup lang="ts">
import type { RecommendedQuestion } from "../../chat/recommendedQuestions";

defineProps<{
  items: RecommendedQuestion[];
}>();

defineEmits<{
  ask: [question: string];
}>();
</script>

<template>
  <div class="recommended-grid" aria-label="推荐问题">
    <button
      v-for="item in items"
      :key="item.text"
      class="recommended-chip"
      type="button"
      @click="$emit('ask', item.text)"
    >
      <span>{{ item.text }}</span>
    </button>
  </div>
</template>
