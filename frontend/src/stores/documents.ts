import { computed, ref } from "vue";
import { defineStore } from "pinia";

import {
  getDocumentDetail,
  listDocuments,
  retryDocumentParse,
  setDocumentEnabled,
  uploadDocument
} from "../api/documents";
import { baseDocumentCategories } from "../mock/documents";
import type {
  DocumentCategory,
  DocumentCategoryKey,
  DocumentDetail,
  DocumentEnableStatus,
  DocumentFilters,
  DocumentItem,
  DocumentParseStatus,
  DocumentSummary,
  DocumentTreeNode,
  DocumentType
} from "../types/document";

const DEFAULT_PAGE_SIZE = 10;
const parseStatusLabels: Record<DocumentParseStatus, string> = {
  uploaded: "\u5f85\u89e3\u6790",
  processing: "\u89e3\u6790\u4e2d",
  ready: "\u5df2\u5b8c\u6210",
  failed: "\u89e3\u6790\u5931\u8d25"
};
const enableStatusLabels: Record<DocumentEnableStatus, string> = {
  enabled: "\u5df2\u542f\u7528",
  disabled: "\u5df2\u7981\u7528"
};

export const useDocumentStore = defineStore("documents", () => {
  const documents = ref<DocumentItem[]>([]);
  const filters = ref<DocumentFilters>({
    category: "all",
    keyword: "",
    type: "all",
    parseStatus: "all",
    enableStatus: "all",
    page: 1,
    pageSize: DEFAULT_PAGE_SIZE
  });
  const isLoading = ref(false);
  const isUploading = ref(false);
  const errorMessage = ref("");
  const lastNotice = ref("");
  const selectedDocumentId = ref<string | null>(null);
  const selectedDocumentDetail = ref<DocumentDetail | null>(null);
  const isDetailOpen = ref(false);
  const isDetailLoading = ref(false);
  const pendingDocumentIds = ref<Set<string>>(new Set());
  const hasPendingDocumentActions = computed(() => pendingDocumentIds.value.size > 0);
  const hasProcessingDocuments = computed(() =>
    documents.value.some((document) => document.parseStatus === "processing")
  );
  let documentLoadRequestSequence = 0;
  let documentMutationSequence = 0;
  let documentDetailRequestSequence = 0;

  const documentTypeOptions = computed<Array<{ label: string; value: DocumentType | "all" }>>(() => [
    { label: "全部类型", value: "all" },
    { label: "PDF", value: "PDF" },
    { label: "Word", value: "Word" },
    { label: "Excel", value: "Excel" },
    { label: "Markdown", value: "Markdown" },
    { label: "TXT", value: "TXT" }
  ]);
  const parseStatusOptions = computed<Array<{ label: string; value: DocumentParseStatus | "all" }>>(() => [
    { label: "解析状态", value: "all" },
    { label: "待解析", value: "uploaded" },
    { label: "解析中", value: "processing" },
    { label: "已完成", value: "ready" },
    { label: "解析失败", value: "failed" }
  ]);
  const enableStatusOptions = computed<Array<{ label: string; value: DocumentEnableStatus | "all" }>>(() => [
    { label: "启用状态", value: "all" },
    { label: "已启用", value: "enabled" },
    { label: "已禁用", value: "disabled" }
  ]);

  const summary = computed<DocumentSummary>(() => ({
    total: documents.value.length,
    processing: documents.value.filter((document) => document.parseStatus === "processing").length,
    failed: documents.value.filter((document) => document.parseStatus === "failed").length,
    enabled: documents.value.filter((document) => document.enableStatus === "enabled").length
  }));

  const categories = computed<DocumentCategory[]>(() =>
    baseDocumentCategories.map((category) => ({
      ...category,
      count:
        category.key === "all"
          ? documents.value.length
          : documents.value.filter((document) => document.category === category.key).length
    }))
  );

  const documentTreeNodes = computed<DocumentTreeNode[]>(() => [
    {
      id: "all",
      kind: "all",
      label: categories.value.find((category) => category.key === "all")?.label ?? "全部文档",
      count: documents.value.length,
      value: "all"
    },
    ...Object.entries(parseStatusLabels).map(([status, label]) => ({
      id: `status:${status}`,
      kind: "status" as const,
      label,
      count: documents.value.filter((document) => document.parseStatus === status).length,
      value: status
    })),
    ...Object.entries(enableStatusLabels).map(([status, label]) => ({
      id: `status:${status}`,
      kind: "status" as const,
      label,
      count: documents.value.filter((document) => document.enableStatus === status).length,
      value: status
    })),
    ...categories.value
      .filter((category) => category.key !== "all")
      .map((category) => ({
        id: `category:${category.key}`,
        kind: "category" as const,
        label: category.label,
        count: category.count,
        value: category.key
      })),
    ...documentTypeOptions.value
      .filter((type) => type.value !== "all")
      .map((type) => ({
        id: `type:${type.value}`,
        kind: "type" as const,
        label: type.label,
        count: documents.value.filter((document) => document.type === type.value).length,
        value: type.value
      }))
  ]);

  const selectedTreeNodeId = computed<string | null>(() => {
    const activeFilterNodeIds = [
      filters.value.category !== "all" ? `category:${filters.value.category}` : null,
      filters.value.type !== "all" ? `type:${filters.value.type}` : null,
      filters.value.parseStatus !== "all" ? `status:${filters.value.parseStatus}` : null,
      filters.value.enableStatus !== "all" ? `status:${filters.value.enableStatus}` : null
    ].filter((nodeId): nodeId is string => nodeId !== null);

    if (activeFilterNodeIds.length === 0) {
      return "all";
    }

    return activeFilterNodeIds.length === 1 ? activeFilterNodeIds[0] : null;
  });

  const currentCategoryLabel = computed(
    () => categories.value.find((category) => category.key === filters.value.category)?.label ?? "全部文档"
  );

  const filteredDocuments = computed(() => {
    const keyword = filters.value.keyword.trim().toLowerCase();

    return documents.value.filter((document) => {
      const categoryMatched =
        filters.value.category === "all" ||
        document.category === filters.value.category ||
        document.parseStatus === filters.value.category ||
        document.enableStatus === filters.value.category;
      const keywordMatched =
        !keyword ||
        document.name.toLowerCase().includes(keyword) ||
        document.type.toLowerCase().includes(keyword);
      const typeMatched = filters.value.type === "all" || document.type === filters.value.type;
      const parseMatched =
        filters.value.parseStatus === "all" || document.parseStatus === filters.value.parseStatus;
      const enableMatched =
        filters.value.enableStatus === "all" || document.enableStatus === filters.value.enableStatus;

      return categoryMatched && keywordMatched && typeMatched && parseMatched && enableMatched;
    });
  });

  const totalPages = computed(() =>
    Math.max(1, Math.ceil(filteredDocuments.value.length / filters.value.pageSize))
  );

  const paginatedDocuments = computed(() => {
    const safePage = Math.min(filters.value.page, totalPages.value);
    const start = (safePage - 1) * filters.value.pageSize;
    return filteredDocuments.value.slice(start, start + filters.value.pageSize);
  });

  async function loadDocuments(options: { resetPage?: boolean } = {}) {
    if (hasPendingDocumentActions.value || isUploading.value) {
      return;
    }

    const requestSequence = ++documentLoadRequestSequence;
    const mutationSequence = documentMutationSequence;
    isLoading.value = true;
    errorMessage.value = "";

    try {
      const nextDocuments = await listDocuments();
      if (
        requestSequence !== documentLoadRequestSequence ||
        mutationSequence !== documentMutationSequence ||
        hasPendingDocumentActions.value ||
        isUploading.value
      ) {
        return;
      }

      documents.value = nextDocuments;
      if (options.resetPage ?? true) {
        resetPage();
      }
    } catch (error) {
      if (requestSequence === documentLoadRequestSequence && !hasPendingDocumentActions.value && !isUploading.value) {
        errorMessage.value = error instanceof Error ? error.message : "文档列表加载失败";
      }
    } finally {
      if (requestSequence === documentLoadRequestSequence) {
        isLoading.value = false;
      }
    }
  }

  async function refreshProcessingDocuments() {
    if (isLoading.value || isUploading.value || hasPendingDocumentActions.value) {
      return;
    }

    await loadDocuments({ resetPage: false });
  }

  async function loadDocumentDetail(id: string) {
    const requestSequence = ++documentDetailRequestSequence;
    isDetailLoading.value = true;
    errorMessage.value = "";

    try {
      const detail = await getDocumentDetail(id);
      if (requestSequence !== documentDetailRequestSequence || selectedDocumentId.value !== id) {
        return;
      }

      selectedDocumentDetail.value = detail;
      replaceDocument(detail.item);
    } catch (error) {
      if (requestSequence === documentDetailRequestSequence && selectedDocumentId.value === id) {
        errorMessage.value = error instanceof Error ? error.message : "文档详情加载失败";
      }
    } finally {
      if (requestSequence === documentDetailRequestSequence && selectedDocumentId.value === id) {
        isDetailLoading.value = false;
      }
    }
  }

  async function openDocumentDetail(id: string) {
    selectedDocumentId.value = id;
    isDetailOpen.value = true;
    selectedDocumentDetail.value = null;
    await loadDocumentDetail(id);
  }

  function closeDocumentDetail() {
    documentDetailRequestSequence += 1;
    isDetailOpen.value = false;
    selectedDocumentId.value = null;
    selectedDocumentDetail.value = null;
    isDetailLoading.value = false;
  }

  async function refreshSelectedDocumentDetail() {
    if (!selectedDocumentId.value || !isDetailOpen.value) {
      return;
    }

    await loadDocumentDetail(selectedDocumentId.value);
  }

  function replaceDocument(nextDocument: DocumentItem) {
    documents.value = documents.value.map((document) =>
      document.id === nextDocument.id ? nextDocument : document
    );
  }

  function isDocumentPending(id: string) {
    return pendingDocumentIds.value.has(id);
  }

  function markDocumentPending(id: string) {
    documentMutationSequence += 1;
    pendingDocumentIds.value = new Set(pendingDocumentIds.value).add(id);
  }

  function unmarkDocumentPending(id: string) {
    const nextPendingIds = new Set(pendingDocumentIds.value);
    nextPendingIds.delete(id);
    pendingDocumentIds.value = nextPendingIds;
    documentMutationSequence += 1;
  }

  function resetPage() {
    filters.value.page = 1;
  }

  function setCategory(category: DocumentCategoryKey) {
    filters.value.category = category;
    resetPage();
  }

  function selectTreeNode(node: DocumentTreeNode) {
    filters.value.category = "all";
    filters.value.type = "all";
    filters.value.parseStatus = "all";
    filters.value.enableStatus = "all";

    if (node.kind === "category") {
      filters.value.category = node.value as DocumentCategoryKey;
    } else if (node.kind === "type") {
      filters.value.type = node.value as DocumentType;
    } else if (node.kind === "status" && node.value in parseStatusLabels) {
      filters.value.parseStatus = node.value as DocumentParseStatus;
    } else if (node.kind === "status" && node.value in enableStatusLabels) {
      filters.value.enableStatus = node.value as DocumentEnableStatus;
    }

    resetPage();
  }

  function setSearchKeyword(keyword: string) {
    filters.value.keyword = keyword;
    resetPage();
  }

  function setTypeFilter(type: DocumentType | "all") {
    filters.value.type = type;
    resetPage();
  }

  function setParseStatusFilter(status: DocumentParseStatus | "all") {
    filters.value.parseStatus = status;
    resetPage();
  }

  function setEnableStatusFilter(status: DocumentEnableStatus | "all") {
    filters.value.enableStatus = status;
    resetPage();
  }

  function setPage(page: number) {
    filters.value.page = Math.min(Math.max(1, page), totalPages.value);
  }

  function resetFilters() {
    filters.value = {
      category: "all",
      keyword: "",
      type: "all",
      parseStatus: "all",
      enableStatus: "all",
      page: 1,
      pageSize: DEFAULT_PAGE_SIZE
    };
  }

  async function toggleDocumentEnabled(id: string) {
    const document = documents.value.find((item) => item.id === id);
    if (!document || isDocumentPending(id)) {
      return;
    }

    errorMessage.value = "";
    const nextEnabled = document.enableStatus !== "enabled";
    markDocumentPending(id);

    try {
      const updated = await setDocumentEnabled(id, nextEnabled);
      replaceDocument(updated);
      if (selectedDocumentId.value === id) {
        await refreshSelectedDocumentDetail();
      }
      lastNotice.value = nextEnabled
        ? "文档已启用，将参与 RAG 检索。"
        : "文档已禁用，暂不参与 RAG 检索。";
    } catch (error) {
      errorMessage.value = error instanceof Error ? error.message : "文档启用状态更新失败";
    } finally {
      unmarkDocumentPending(id);
    }
  }

  async function uploadDocumentFile(file: File) {
    if (isUploading.value || isLoading.value || hasPendingDocumentActions.value) {
      return;
    }

    isUploading.value = true;
    errorMessage.value = "";

    try {
      const uploaded = await uploadDocument(file);
      documents.value = [uploaded, ...documents.value.filter((document) => document.id !== uploaded.id)];
      resetPage();
      lastNotice.value =
        uploaded.parseStatus === "failed"
          ? `文档已上传，但解析失败：${uploaded.failureReason || "不支持的文件格式"}`
          : "文档已上传并导入";
    } catch (error) {
      errorMessage.value = error instanceof Error ? error.message : "文档上传失败";
    } finally {
      isUploading.value = false;
    }
  }

  async function retryParse(id: string) {
    if (isDocumentPending(id)) {
      return;
    }

    errorMessage.value = "";
    markDocumentPending(id);

    try {
      const updated = await retryDocumentParse(id);
      replaceDocument(updated);
      if (selectedDocumentId.value === id) {
        await refreshSelectedDocumentDetail();
      }
      if (updated.parseStatus === "ready") {
        lastNotice.value = "文档已重新解析并完成入库。";
      } else if (updated.parseStatus === "failed") {
        lastNotice.value = `文档重新解析失败：${updated.failureReason ?? "请查看失败原因"}`;
      } else {
        lastNotice.value = "文档已进入解析流程，稍后刷新状态。";
      }
    } catch (error) {
      errorMessage.value = error instanceof Error ? error.message : "重新解析请求提交失败";
    } finally {
      unmarkDocumentPending(id);
    }
  }

  function getFailureReason(id: string) {
    return documents.value.find((document) => document.id === id)?.failureReason ?? "";
  }

  return {
    documents,
    filters,
    isLoading,
    isUploading,
    errorMessage,
    lastNotice,
    selectedDocumentId,
    selectedDocumentDetail,
    isDetailOpen,
    isDetailLoading,
    pendingDocumentIds,
    hasPendingDocumentActions,
    hasProcessingDocuments,
    categories,
    documentTreeNodes,
    selectedTreeNodeId,
    currentCategoryLabel,
    summary,
    filteredDocuments,
    paginatedDocuments,
    totalPages,
    documentTypeOptions,
    parseStatusOptions,
    enableStatusOptions,
    loadDocuments,
    refreshProcessingDocuments,
    loadDocumentDetail,
    openDocumentDetail,
    closeDocumentDetail,
    refreshSelectedDocumentDetail,
    isDocumentPending,
    setCategory,
    selectTreeNode,
    setSearchKeyword,
    setTypeFilter,
    setParseStatusFilter,
    setEnableStatusFilter,
    setPage,
    resetFilters,
    uploadDocumentFile,
    toggleDocumentEnabled,
    retryParse,
    getFailureReason
  };
});
