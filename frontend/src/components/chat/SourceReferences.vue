<script setup lang="ts">
import { computed, ref } from "vue";
import { Link } from "@element-plus/icons-vue";

import { formatConfidence } from "../../chat/qaPresentation";
import type { QaReference } from "../../types/qa";

const props = defineProps<{
  references: QaReference[];
}>();

const expanded = ref(false);
const visibleReferences = computed(() => (expanded.value ? props.references : props.references.slice(0, 3)));
const hasMore = computed(() => props.references.length > 3);
</script>

<template>
  <section v-if="references.length > 0" class="source-panel" aria-label="来源引用">
    <button class="source-panel-head" type="button" @click="expanded = !expanded">
      <Link class="source-icon" aria-hidden="true" />
      <strong>引用 {{ references.length }} 个来源</strong>
      <span>{{ hasMore ? (expanded ? "收起" : "展开全部") : "已展开" }}</span>
    </button>
    <div class="source-list">
      <article v-for="reference in visibleReferences" :key="reference.rank" class="source-row">
        <span class="source-file">片段 {{ reference.rank }}</span>
        <span>{{ reference.heading_path || "知识库片段" }}</span>
        <em v-if="reference.rerank_score !== null">相关度 {{ formatConfidence(reference.rerank_score) }}</em>
      </article>
    </div>
  </section>
</template>
