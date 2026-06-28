<script setup lang="ts">
import { computed } from "vue";
import { Link } from "@element-plus/icons-vue";

import { formatConfidence, type AnswerTypeDescription } from "../../chat/qaPresentation";
import type { QaReference } from "../../types/qa";

const props = defineProps<{
  references: QaReference[];
  answerDescription: AnswerTypeDescription;
  confidence: number | null;
}>();

const documentFileNames = computed(() => {
  const names = props.references
    .filter((reference) => reference.visible)
    .map((reference) => reference.document_file_name?.trim())
    .filter((name): name is string => Boolean(name));

  return [...new Set(names)];
});
</script>

<template>
  <section v-if="documentFileNames.length > 0" class="document-source-panel" aria-label="来源文档">
    <header class="document-source-head">
      <span class="document-source-title">
        <Link class="source-icon" aria-hidden="true" />
        <strong>来源文档</strong>
      </span>
      <span :class="['document-source-meta', answerDescription.tone]">
        {{ answerDescription.label }}
        <b>{{ formatConfidence(confidence) }}</b>
      </span>
    </header>
    <div class="document-source-list">
      <span v-for="fileName in documentFileNames" :key="fileName" class="document-source-chip">
        {{ fileName }}
      </span>
    </div>
  </section>
</template>
