import { computed, ref } from "vue";
import { defineStore } from "pinia";

import { uploadDocument } from "../api/documents";
import { baseDocumentCategories, mockDocuments } from "../mock/documents";
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
  const documents = ref<DocumentItem[]>(mockDocuments.map((document) => ({ ...document })));
  const filters = ref<DocumentFilters>({
    category: "all",
    keyword: "",
    type: "all",
    parseStatus: "all",
    enableStatus: "all",
    page: 1,
    pageSize: DEFAULT_PAGE_SIZE
  });
  const lastNotice = ref("");

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

  async function uploadMockDocument(name: string, type: DocumentType) {
    const document = await uploadDocument(name, type);
    documents.value = [document, ...documents.value];
    lastNotice.value = "文档已加入解析队列，真实上传接口待后端接入";
    resetPage();
  }

  function toggleDocumentEnabled(id: string) {
    documents.value = documents.value.map((document) =>
      document.id === id
        ? {
            ...document,
            enableStatus: document.enableStatus === "enabled" ? "disabled" : "enabled",
            updatedAt: new Date().toLocaleString("sv-SE").replace("T", " ")
          }
        : document
    );
  }

  function retryParse(id: string) {
    documents.value = documents.value.map((document) =>
      document.id === id
        ? {
            ...document,
            parseStatus: "processing",
            enableStatus: "disabled",
            failureReason: null,
            progress: 15,
            updatedAt: new Date().toLocaleString("sv-SE").replace("T", " ")
          }
        : document
    );
    lastNotice.value = "已模拟重新解析，真实解析任务接口待后端接入";
  }

  function getFailureReason(id: string) {
    return documents.value.find((document) => document.id === id)?.failureReason ?? "";
  }

  return {
    documents,
    filters,
    lastNotice,
    categories,
    currentCategoryLabel,
    summary,
    filteredDocuments,
    paginatedDocuments,
    totalPages,
    documentTypeOptions,
    parseStatusOptions,
    enableStatusOptions,
    setCategory,
    setSearchKeyword,
    setTypeFilter,
    setParseStatusFilter,
    setEnableStatusFilter,
    setPage,
    resetFilters,
    uploadMockDocument,
    toggleDocumentEnabled,
    retryParse,
    getFailureReason
  };
});
