<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import {
  CircleCheck,
  Clock,
  Document as DocumentIcon,
  Folder,
  Refresh,
  Search,
  Upload,
  Warning
} from "@element-plus/icons-vue";

import DocumentDetailFloatingPanel from "../components/documents/DocumentDetailFloatingPanel.vue";
import { useDocumentStore } from "../stores/documents";
import type { DocumentItem, DocumentType } from "../types/document";

const documentStore = useDocumentStore();
const failureDialogVisible = ref(false);
const selectedFailure = ref<DocumentItem | null>(null);
const uploadInput = ref<HTMLInputElement | null>(null);
let processingRefreshTimer: ReturnType<typeof window.setInterval> | null = null;

function stopProcessingRefreshTimer() {
  if (!processingRefreshTimer) {
    return;
  }

  window.clearInterval(processingRefreshTimer);
  processingRefreshTimer = null;
}

function startProcessingRefreshTimer() {
  if (processingRefreshTimer) {
    return;
  }

  processingRefreshTimer = window.setInterval(() => {
    void documentStore.refreshProcessingDocuments();
  }, 5000);
}

function handleKeydown(event: KeyboardEvent) {
  if (event.key === "Escape" && documentStore.isDetailOpen) {
    documentStore.closeDocumentDetail();
  }
}

onMounted(() => {
  void documentStore.loadDocuments();
  window.addEventListener("keydown", handleKeydown);
});

watch(
  () => documentStore.hasProcessingDocuments,
  (hasProcessingDocuments) => {
    if (hasProcessingDocuments) {
      startProcessingRefreshTimer();
      return;
    }

    stopProcessingRefreshTimer();
  },
  { immediate: true }
);

watch(
  () => [documentStore.filteredDocuments, documentStore.selectedDocumentId] as const,
  ([documents, selectedId]) => {
    if (!selectedId) {
      return;
    }
    if (!documents.some((document) => document.id === selectedId)) {
      documentStore.closeDocumentDetail();
    }
  }
);

onUnmounted(() => {
  stopProcessingRefreshTimer();
  window.removeEventListener("keydown", handleKeydown);
});

const selectedTreeNodeLabel = computed(
  () =>
    documentStore.documentTreeNodes.find((node) => node.id === documentStore.selectedTreeNodeId)?.label ??
    documentStore.currentCategoryLabel
);

const metricCards = computed(() => [
  {
    label: "全部文档",
    value: documentStore.summary.total,
    hint: "当前知识库总量",
    icon: DocumentIcon,
    tone: "blue"
  },
  {
    label: "解析中",
    value: documentStore.summary.processing,
    hint: "正在切块入库",
    icon: Clock,
    tone: "cyan"
  },
  {
    label: "解析失败",
    value: documentStore.summary.failed,
    hint: "需要人工处理",
    icon: Warning,
    tone: "red"
  },
  {
    label: "已启用",
    value: documentStore.summary.enabled,
    hint: "参与 RAG 检索",
    icon: CircleCheck,
    tone: "green"
  }
]);

function statusLabel(document: DocumentItem) {
  if (document.parseStatus === "processing") {
    return `解析中(${document.progress ?? 0}%)`;
  }

  const labels = {
    uploaded: "待解析",
    ready: "已完成",
    failed: "失败"
  };

  return labels[document.parseStatus];
}

function parseActionLabel(document: DocumentItem) {
  if (documentStore.isDocumentPending(document.id)) {
    return "处理中";
  }
  if (document.parseStatus === "ready") {
    return "重新解析";
  }
  if (document.parseStatus === "failed") {
    return "重试解析";
  }
  if (document.parseStatus === "processing") {
    return "解析中";
  }
  return "开始解析";
}

function typeClass(type: DocumentType) {
  return `type-${type.toLowerCase()}`;
}

function showFailure(document: DocumentItem) {
  selectedFailure.value = document;
  failureDialogVisible.value = true;
}

function isRetryDisabled(document: DocumentItem) {
  return documentStore.isDocumentPending(document.id) || document.parseStatus === "processing";
}

function shouldIgnoreRowClick(target: EventTarget | null) {
  return target instanceof HTMLElement
    ? Boolean(target.closest("button, a, input, select, textarea, [role='button']"))
    : false;
}

function handleRowClick(document: DocumentItem, event: MouseEvent) {
  if (shouldIgnoreRowClick(event.target)) {
    return;
  }

  void documentStore.openDocumentDetail(document.id);
}

async function triggerParse(document: DocumentItem) {
  if (isRetryDisabled(document)) {
    return;
  }

  const confirmed = window.confirm("确认重新解析该文档？这会重建文档分段。");
  if (!confirmed) {
    return;
  }

  await documentStore.retryParse(document.id);
}

function closeDetailPanel() {
  documentStore.closeDocumentDetail();
}

function openUploadPicker() {
  if (documentStore.isUploading || documentStore.isLoading || documentStore.hasPendingDocumentActions) {
    return;
  }

  uploadInput.value?.click();
}

async function handleUploadChange(event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  input.value = "";

  if (!file) {
    return;
  }

  await documentStore.uploadDocumentFile(file);
}
</script>

<template>
  <section class="document-page" :aria-busy="documentStore.isLoading">
    <aside class="document-category-panel">
      <div class="document-category-head">
        <div>
          <p>Knowledge Categories</p>
          <h2>文档分类</h2>
        </div>
        <button type="button" aria-label="新增分类">
          <span>+</span>
        </button>
      </div>

      <label class="document-category-search">
        <Search aria-hidden="true" />
        <input type="search" placeholder="搜索分类" aria-label="搜索分类" />
      </label>

      <button
        v-for="node in documentStore.documentTreeNodes"
        :key="node.id"
        class="document-category-item"
        :class="[{ active: documentStore.selectedTreeNodeId === node.id }, `tree-${node.kind}`]"
        type="button"
        @click="documentStore.selectTreeNode(node)"
      >
        <Folder aria-hidden="true" />
        <span>{{ node.label }}</span>
        <strong>{{ node.count }}</strong>
      </button>
    </aside>

    <main class="document-main" :class="{ 'document-main-detail-open': documentStore.isDetailOpen }">
      <header class="document-hero">
        <div>
          <p class="eyebrow">Knowledge Base Intake</p>
          <h1>文档管理</h1>
          <span>管理知识库文档、解析任务与启用状态</span>
          <strong>当前分类：{{ selectedTreeNodeLabel }}</strong>
        </div>
        <input
          ref="uploadInput"
          class="document-hidden-file"
          type="file"
          accept=".md,.markdown,.txt,.pdf,.doc,.docx,.xls,.xlsx"
          @change="handleUploadChange"
        />
        <button
          class="document-upload-primary"
          type="button"
          :disabled="documentStore.isUploading || documentStore.isLoading || documentStore.hasPendingDocumentActions"
          @click="openUploadPicker"
        >
          <Upload aria-hidden="true" />
          {{ documentStore.isUploading ? "上传中" : "上传文档" }}
        </button>
      </header>

      <section class="document-metrics" aria-label="文档统计">
        <article v-for="metric in metricCards" :key="metric.label" class="document-metric-card" :class="metric.tone">
          <span>
            <component :is="metric.icon" aria-hidden="true" />
          </span>
          <div>
            <p>{{ metric.label }}</p>
            <strong>{{ metric.value }}</strong>
            <em>{{ metric.hint }}</em>
          </div>
        </article>
      </section>

      <section class="document-filter-bar" aria-label="文档筛选">
        <label class="document-search">
          <Search aria-hidden="true" />
          <input
            :value="documentStore.filters.keyword"
            type="search"
            placeholder="请输入文档名称关键词"
            @input="documentStore.setSearchKeyword(($event.target as HTMLInputElement).value)"
          />
        </label>

        <select
          :value="documentStore.filters.type"
          aria-label="文档类型"
          @change="documentStore.setTypeFilter(($event.target as HTMLSelectElement).value as DocumentType | 'all')"
        >
          <option v-for="option in documentStore.documentTypeOptions" :key="option.value" :value="option.value">
            {{ option.label }}
          </option>
        </select>

        <select
          :value="documentStore.filters.parseStatus"
          aria-label="解析状态"
          @change="documentStore.setParseStatusFilter(($event.target as HTMLSelectElement).value as never)"
        >
          <option v-for="option in documentStore.parseStatusOptions" :key="option.value" :value="option.value">
            {{ option.label }}
          </option>
        </select>

        <select
          :value="documentStore.filters.enableStatus"
          aria-label="启用状态"
          @change="documentStore.setEnableStatusFilter(($event.target as HTMLSelectElement).value as never)"
        >
          <option v-for="option in documentStore.enableStatusOptions" :key="option.value" :value="option.value">
            {{ option.label }}
          </option>
        </select>

        <button class="document-reset" type="button" @click="documentStore.resetFilters">
          <Refresh aria-hidden="true" />
          重置
        </button>
      </section>

      <section class="document-upload-strip">
        <div>
          <strong>真实文档列表已接入</strong>
          <span>Markdown/TXT 已支持真实入库；PDF/Word/Excel 会先保存为解析失败，待解析器接入后再处理。</span>
        </div>
        <button
          class="document-reset"
          type="button"
          :disabled="documentStore.isLoading || documentStore.hasPendingDocumentActions"
          @click="documentStore.loadDocuments()"
        >
          <Refresh aria-hidden="true" />
          {{ documentStore.isLoading ? "刷新中" : documentStore.hasPendingDocumentActions ? "处理中" : "刷新列表" }}
        </button>
      </section>

      <p v-if="documentStore.errorMessage" class="document-notice error">
        {{ documentStore.errorMessage }}
      </p>

      <div v-if="documentStore.isLoading" class="document-empty" aria-live="polite">
        正在加载文档列表...
      </div>

      <section class="document-table-card" :aria-busy="documentStore.isLoading">
        <table class="document-table">
          <thead>
            <tr>
              <th>文档名称</th>
              <th>类型</th>
              <th>解析状态</th>
              <th>启用状态</th>
              <th>更新时间</th>
              <th>失败原因</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="document in documentStore.paginatedDocuments"
              :key="document.id"
              :class="{ selected: documentStore.selectedDocumentId === document.id }"
              @click="handleRowClick(document, $event)"
            >
              <td>
                <div class="document-name-cell">
                  <span class="document-type-icon" :class="typeClass(document.type)">
                    {{ document.type.slice(0, 1) }}
                  </span>
                  <strong>{{ document.name }}</strong>
                </div>
              </td>
              <td>{{ document.type }}</td>
              <td>
                <div class="document-parse-cell" :class="document.parseStatus">
                  <span class="document-status-dot" />
                  <strong>{{ statusLabel(document) }}</strong>
                  <i v-if="document.parseStatus === 'processing'">
                    <b :style="{ width: `${document.progress ?? 0}%` }" />
                  </i>
                </div>
              </td>
              <td>
                <span class="document-enable-tag" :class="document.enableStatus">
                  {{ document.enableStatus === "enabled" ? "已启用" : "已禁用" }}
                </span>
              </td>
              <td>{{ document.updatedAt }}</td>
              <td>
                <button
                  v-if="document.failureReason"
                  class="document-link-button"
                  type="button"
                  @click="showFailure(document)"
                >
                  查看原因
                </button>
                <span v-else>-</span>
              </td>
              <td>
                <div class="document-actions">
                  <button
                    type="button"
                    :disabled="documentStore.isDocumentPending(document.id)"
                    @click="documentStore.toggleDocumentEnabled(document.id)"
                  >
                    {{
                      documentStore.isDocumentPending(document.id)
                        ? "处理中"
                        : document.enableStatus === "enabled"
                          ? "禁用"
                          : "启用"
                    }}
                  </button>
                  <button
                    class="primary"
                    type="button"
                    :disabled="isRetryDisabled(document)"
                    @click="triggerParse(document)"
                  >
                    {{ parseActionLabel(document) }}
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>

        <div v-if="!documentStore.isLoading && documentStore.paginatedDocuments.length === 0" class="document-empty">
          当前筛选条件下没有文档，试试重置筛选。
        </div>
      </section>

      <footer class="document-pagination">
        <span>共 {{ documentStore.filteredDocuments.length }} 条</span>
        <div>
          <button type="button" :disabled="documentStore.filters.page <= 1" @click="documentStore.setPage(documentStore.filters.page - 1)">
            上一页
          </button>
          <button
            v-for="page in documentStore.totalPages"
            :key="page"
            type="button"
            :class="{ active: page === documentStore.filters.page }"
            @click="documentStore.setPage(page)"
          >
            {{ page }}
          </button>
          <button
            type="button"
            :disabled="documentStore.filters.page >= documentStore.totalPages"
            @click="documentStore.setPage(documentStore.filters.page + 1)"
          >
            下一页
          </button>
        </div>
      </footer>

      <p v-if="documentStore.lastNotice" class="document-notice">{{ documentStore.lastNotice }}</p>

      <DocumentDetailFloatingPanel
        :open="documentStore.isDetailOpen"
        :detail="documentStore.selectedDocumentDetail"
        :loading="documentStore.isDetailLoading"
        :pending="
          documentStore.selectedDocumentId
            ? documentStore.isDocumentPending(documentStore.selectedDocumentId)
            : false
        "
        @close="closeDetailPanel"
        @toggle-enabled="documentStore.toggleDocumentEnabled"
        @retry-parse="
          (id) => {
            const document = documentStore.documents.find((item) => item.id === id);
            if (document) {
              void triggerParse(document);
            }
          }
        "
      />
    </main>

    <el-dialog v-model="failureDialogVisible" title="解析失败原因" width="460px">
      <div v-if="selectedFailure" class="document-failure-dialog">
        <strong>{{ selectedFailure.name }}</strong>
        <p>{{ selectedFailure.failureReason }}</p>
        <span>建议：重新导出可复制文本版本，或等待后端 OCR/表格解析能力接入。</span>
      </div>
      <template #footer>
        <button class="document-reset" type="button" @click="failureDialogVisible = false">关闭</button>
        <button
          v-if="selectedFailure"
          class="document-upload-primary dialog-action"
          type="button"
          :disabled="isRetryDisabled(selectedFailure)"
          @click="triggerParse(selectedFailure); failureDialogVisible = false"
        >
          {{ parseActionLabel(selectedFailure) }}
        </button>
      </template>
    </el-dialog>
  </section>
</template>
