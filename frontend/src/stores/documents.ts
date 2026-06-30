import { computed, ref } from "vue";
import { defineStore } from "pinia";

import { listDocuments, retryDocumentParse, setDocumentEnabled, uploadDocument } from "../api/documents";
import { baseDocumentCategories } from "../mock/documents";
import type {
  DocumentCategory,
  DocumentCategoryKey,
  DocumentEnableStatus,
  DocumentFilters,
  DocumentItem,
  DocumentParseStatus,
  DocumentSummary,
  DocumentType
} from "../types/document";

const DEFAULT_PAGE_SIZE = 10;

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
  const pendingDocumentIds = ref<Set<string>>(new Set());
  const hasPendingDocumentActions = computed(() => pendingDocumentIds.value.size > 0);
  let documentLoadRequestSequence = 0;

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

  async function loadDocuments() {
    if (hasPendingDocumentActions.value || isUploading.value) {
      return;
    }

    const requestSequence = ++documentLoadRequestSequence;
    isLoading.value = true;
    errorMessage.value = "";

    try {
      const nextDocuments = await listDocuments();
      if (requestSequence !== documentLoadRequestSequence || hasPendingDocumentActions.value || isUploading.value) {
        return;
      }

      documents.value = nextDocuments;
      resetPage();
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

  function replaceDocument(nextDocument: DocumentItem) {
    documents.value = documents.value.map((document) =>
      document.id === nextDocument.id ? nextDocument : document
    );
  }

  function isDocumentPending(id: string) {
    return pendingDocumentIds.value.has(id);
  }

  function markDocumentPending(id: string) {
    pendingDocumentIds.value = new Set(pendingDocumentIds.value).add(id);
  }

  function unmarkDocumentPending(id: string) {
    const nextPendingIds = new Set(pendingDocumentIds.value);
    nextPendingIds.delete(id);
    pendingDocumentIds.value = nextPendingIds;
  }

  function resetPage() {
    filters.value.page = 1;
  }

  function setCategory(category: DocumentCategoryKey) {
    filters.value.category = category;
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
      lastNotice.value = "已提交重新解析请求，文档已进入解析队列。";
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
    pendingDocumentIds,
    hasPendingDocumentActions,
    categories,
    currentCategoryLabel,
    summary,
    filteredDocuments,
    paginatedDocuments,
    totalPages,
    documentTypeOptions,
    parseStatusOptions,
    enableStatusOptions,
    loadDocuments,
    isDocumentPending,
    setCategory,
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
