<script setup lang="ts">
import { computed } from "vue";

import type { DocumentDetail, DocumentItem, ParseTaskSummary } from "../../types/document";

const props = defineProps<{
  open: boolean;
  detail: DocumentDetail | null;
  loading: boolean;
  pending: boolean;
}>();

const emit = defineEmits<{
  close: [];
  toggleEnabled: [id: string];
  retryParse: [id: string];
}>();

const documentItem = computed<DocumentItem | null>(() => props.detail?.item ?? null);

function parseStatusLabel(status: ParseTaskSummary["status"]) {
  switch (status) {
    case "pending":
      return "待执行";
    case "running":
      return "执行中";
    case "success":
      return "成功";
    case "failed":
      return "失败";
    default:
      return status;
  }
}

function detailStatusLabel(document: DocumentItem) {
  if (document.parseStatus === "processing") {
    return `解析中${document.progress != null ? ` (${document.progress}%)` : ""}`;
  }

  if (document.parseStatus === "uploaded") {
    return "待解析";
  }

  if (document.parseStatus === "ready") {
    return "已完成";
  }

  return "解析失败";
}

function metadataEntries(metadata: Record<string, unknown>) {
  return Object.entries(metadata).filter(([, value]) => value !== null && value !== "");
}

function formatTaskTime(task: ParseTaskSummary) {
  return task.finishedAt ?? task.startedAt ?? "暂无时间";
}
</script>

<template>
  <aside
    v-if="open"
    class="document-detail-floating-panel document-detail-backdropless"
    aria-live="polite"
  >
    <div class="document-detail-panel-card">
      <header class="document-detail-header">
        <div>
          <p>文档详情</p>
          <h2>{{ documentItem?.name ?? "文档详情" }}</h2>
        </div>
        <button type="button" class="document-detail-close" aria-label="关闭文档详情" @click="emit('close')">
          ×
        </button>
      </header>

      <div v-if="loading" class="document-detail-empty">
        正在加载文档详情...
      </div>

      <div v-else-if="!detail || !documentItem" class="document-detail-empty">
        暂无可展示的文档详情，请稍后重试或关闭面板。
      </div>

      <template v-else>
        <section class="document-detail-section">
          <div class="document-detail-title-row">
            <div>
              <strong>{{ documentItem.name }}</strong>
              <span>{{ documentItem.type }} · {{ detailStatusLabel(documentItem) }}</span>
            </div>
            <span class="document-enable-tag" :class="documentItem.enableStatus">
              {{ documentItem.enableStatus === "enabled" ? "已启用" : "已禁用" }}
            </span>
          </div>
          <div class="document-detail-actions">
            <button type="button" :disabled="pending" @click="emit('toggleEnabled', documentItem.id)">
              {{
                pending
                  ? "处理中"
                  : documentItem.enableStatus === "enabled"
                    ? "禁用文档"
                    : "启用文档"
              }}
            </button>
            <button type="button" class="primary" :disabled="pending" @click="emit('retryParse', documentItem.id)">
              {{ pending ? "处理中" : "重新解析" }}
            </button>
          </div>
        </section>

        <section class="document-detail-section">
          <h3>文件信息</h3>
          <dl class="document-detail-kv">
            <div>
              <dt>更新时间</dt>
              <dd>{{ documentItem.updatedAt }}</dd>
            </div>
            <div>
              <dt>源文件路径</dt>
              <dd>{{ detail.sourcePath ?? "暂无" }}</dd>
            </div>
            <div>
              <dt>Markdown 路径</dt>
              <dd>{{ detail.markdownPath ?? "暂无" }}</dd>
            </div>
            <div>
              <dt>文件哈希</dt>
              <dd>{{ detail.fileSha256 ?? "暂无" }}</dd>
            </div>
          </dl>
        </section>

        <section class="document-detail-section">
          <h3>解析信息</h3>
          <dl class="document-detail-kv">
            <div>
              <dt>分段数量</dt>
              <dd>{{ detail.segmentCount }}</dd>
            </div>
            <div>
              <dt>最近任务</dt>
              <dd>{{ detail.latestTask ? parseStatusLabel(detail.latestTask.status) : "暂无" }}</dd>
            </div>
            <div v-if="detail.latestTask">
              <dt>解析器</dt>
              <dd>{{ detail.latestTask.parserName ?? "暂无" }}</dd>
            </div>
            <div v-if="documentItem.failureReason">
              <dt>失败原因</dt>
              <dd>{{ documentItem.failureReason }}</dd>
            </div>
          </dl>
        </section>

        <section v-if="metadataEntries(detail.metadata).length > 0" class="document-detail-section">
          <h3>元数据</h3>
          <dl class="document-detail-kv">
            <div v-for="[key, value] in metadataEntries(detail.metadata)" :key="key">
              <dt>{{ key }}</dt>
              <dd>{{ String(value) }}</dd>
            </div>
          </dl>
        </section>

        <section class="document-detail-section">
          <h3>最近任务</h3>
          <div v-if="detail.recentTasks.length === 0" class="document-detail-empty inline">
            暂无任务记录
          </div>
          <article
            v-for="task in detail.recentTasks"
            :key="task.id"
            class="document-detail-task"
          >
            <div class="document-detail-task-row">
              <strong>{{ parseStatusLabel(task.status) }}</strong>
              <span>{{ formatTaskTime(task) }}</span>
            </div>
            <p>{{ task.parserName ?? "未记录解析器" }}</p>
            <small>
              重试 {{ task.retryCount }} 次
              <template v-if="task.durationMs !== null"> · {{ task.durationMs }} ms</template>
            </small>
            <em v-if="task.errorMessage">{{ task.errorMessage }}</em>
          </article>
        </section>

        <section class="document-detail-section">
          <h3>分段预览</h3>
          <div v-if="detail.segmentPreview.length === 0" class="document-detail-empty inline">
            暂无分段预览
          </div>
          <article
            v-for="segment in detail.segmentPreview"
            :key="segment.id"
            class="document-detail-segment"
          >
            <div class="document-detail-task-row">
              <strong>分段 #{{ segment.chunkIndex }}</strong>
              <span>{{ segment.charCount }} 字</span>
            </div>
            <p>{{ segment.headingPath ?? segment.sectionTitle ?? "未命名分段" }}</p>
            <small>{{ segment.hasEmbedding ? "已生成向量" : "未生成向量" }}</small>
          </article>
        </section>
      </template>
    </div>
  </aside>
</template>
