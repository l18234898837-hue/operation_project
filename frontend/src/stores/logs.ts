import { computed, ref } from "vue";
import { defineStore } from "pinia";

import { copyTextToClipboard } from "../chat/clipboard";
import { mockQaLogs } from "../mock/logs";
import type {
  QaLogAnswerType,
  QaLogFilters,
  QaLogItem,
  QaLogProcessStatus,
  QaLogStatus,
  QaLogSummary
} from "../types/log";

const DEFAULT_PAGE_SIZE = 8;
const HIGH_LATENCY_MS = 2500;

export const useQaLogStore = defineStore("qa-logs", () => {
  const logs = ref<QaLogItem[]>(mockQaLogs.map((log) => ({ ...log })));
  const filters = ref<QaLogFilters>({
    keyword: "",
    answerType: "all",
    status: "all",
    processStatus: "all",
    page: 1,
    pageSize: DEFAULT_PAGE_SIZE
  });
  const selectedLogId = ref<string | null>(null);
  const copyMessage = ref("");

  const answerTypeOptions = computed<Array<{ label: string; value: QaLogAnswerType | "all" }>>(() => [
    { label: "全部类型", value: "all" },
    { label: "知识库回答", value: "rag" },
    { label: "通用解释", value: "general_llm" },
    { label: "拒答", value: "refused" },
    { label: "证据不足", value: "none" }
  ]);

  const statusOptions = computed<Array<{ label: string; value: QaLogStatus | "all" }>>(() => [
    { label: "全部状态", value: "all" },
    { label: "已回答", value: "answered" },
    { label: "证据不足", value: "insufficient_evidence" },
    { label: "拒答", value: "refused" },
    { label: "低置信度", value: "low_confidence" },
    { label: "接口错误", value: "error" }
  ]);

  const processStatusOptions = computed<Array<{ label: string; value: QaLogProcessStatus | "all" }>>(() => [
    { label: "处理状态", value: "all" },
    { label: "待处理", value: "new" },
    { label: "已查看", value: "reviewed" },
    { label: "已处理", value: "resolved" }
  ]);

  const filteredLogs = computed(() => {
    const keyword = filters.value.keyword.trim().toLowerCase();

    return logs.value.filter((log) => {
      const keywordMatched =
        !keyword ||
        log.question.toLowerCase().includes(keyword) ||
        log.answerPreview.toLowerCase().includes(keyword) ||
        log.traceId.toLowerCase().includes(keyword);
      const answerTypeMatched = filters.value.answerType === "all" || log.answerType === filters.value.answerType;
      const statusMatched = filters.value.status === "all" || log.status === filters.value.status;
      const processMatched =
        filters.value.processStatus === "all" || log.processStatus === filters.value.processStatus;

      return keywordMatched && answerTypeMatched && statusMatched && processMatched;
    });
  });

  const summary = computed<QaLogSummary>(() => ({
    total: filteredLogs.value.length,
    answered: filteredLogs.value.filter((log) => log.status === "answered").length,
    insufficientEvidence: filteredLogs.value.filter((log) => log.status === "insufficient_evidence").length,
    refused: filteredLogs.value.filter((log) => log.status === "refused").length,
    lowConfidence: filteredLogs.value.filter((log) => log.status === "low_confidence").length,
    highLatency: filteredLogs.value.filter((log) => log.latencyMs >= HIGH_LATENCY_MS).length
  }));

  const totalPages = computed(() => Math.max(1, Math.ceil(filteredLogs.value.length / filters.value.pageSize)));

  const paginatedLogs = computed(() => {
    const safePage = Math.min(filters.value.page, totalPages.value);
    const start = (safePage - 1) * filters.value.pageSize;
    return filteredLogs.value.slice(start, start + filters.value.pageSize);
  });

  const selectedLog = computed(() => logs.value.find((log) => log.id === selectedLogId.value) ?? null);

  function resetPage() {
    filters.value.page = 1;
  }

  function setKeyword(keyword: string) {
    filters.value.keyword = keyword;
    resetPage();
  }

  function setAnswerType(answerType: QaLogAnswerType | "all") {
    filters.value.answerType = answerType;
    resetPage();
  }

  function setStatus(status: QaLogStatus | "all") {
    filters.value.status = status;
    resetPage();
  }

  function setProcessStatus(status: QaLogProcessStatus | "all") {
    filters.value.processStatus = status;
    resetPage();
  }

  function setPage(page: number) {
    filters.value.page = Math.min(Math.max(1, page), totalPages.value);
  }

  function resetFilters() {
    filters.value = {
      keyword: "",
      answerType: "all",
      status: "all",
      processStatus: "all",
      page: 1,
      pageSize: DEFAULT_PAGE_SIZE
    };
  }

  function selectLog(id: string) {
    selectedLogId.value = id;
  }

  function closeDetail() {
    selectedLogId.value = null;
  }

  async function copyTraceId(traceId: string) {
    const result = await copyTextToClipboard(traceId);
    copyMessage.value = result.ok ? "trace_id 已复制" : "复制失败，请手动选择 trace_id";
  }

  function markProcessed(id: string) {
    logs.value = logs.value.map((log) => (log.id === id ? { ...log, processStatus: "resolved" } : log));
  }

  function createUnansweredFromLog(id: string) {
    logs.value = logs.value.map((log) =>
      log.id === id
        ? {
            ...log,
            knowledgeGap: true,
            processStatus: log.processStatus === "new" ? "reviewed" : log.processStatus,
            gapReason: log.gapReason ?? "已从日志详情加入未命中问题候选，真实回流接口待接入"
          }
        : log
    );
  }

  return {
    logs,
    filters,
    summary,
    filteredLogs,
    paginatedLogs,
    totalPages,
    selectedLog,
    copyMessage,
    answerTypeOptions,
    statusOptions,
    processStatusOptions,
    setKeyword,
    setAnswerType,
    setStatus,
    setProcessStatus,
    setPage,
    resetFilters,
    selectLog,
    closeDetail,
    copyTraceId,
    markProcessed,
    createUnansweredFromLog
  };
});
