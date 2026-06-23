import { useQaLogStore } from "../stores/logs";
import type {
  QaLogAnswerType,
  QaLogFilters,
  QaLogItem,
  QaLogProcessStatus,
  QaLogStatus,
  QaLogSummary
} from "../types/log";

type Assert<T extends true> = T;
type IsAssignable<TValue, TExpected> = TValue extends TExpected ? true : false;

const store = useQaLogStore();

type LogsAreQaLogItems = Assert<IsAssignable<typeof store.logs, QaLogItem[]>>;
type FilterShape = Assert<IsAssignable<typeof store.filters, QaLogFilters>>;
type SummaryShape = Assert<IsAssignable<typeof store.summary, QaLogSummary>>;
type AnswerTypeOptionShape = Assert<
  IsAssignable<(typeof store.answerTypeOptions)[number]["value"], QaLogAnswerType | "all">
>;
type StatusOptionShape = Assert<
  IsAssignable<(typeof store.statusOptions)[number]["value"], QaLogStatus | "all">
>;
type ProcessStatusOptionShape = Assert<
  IsAssignable<(typeof store.processStatusOptions)[number]["value"], QaLogProcessStatus | "all">
>;

void store.filteredLogs;
void store.paginatedLogs;
void store.totalPages;
void store.selectedLog;
void store.copyMessage;
void store.setKeyword("逆变器");
void store.setAnswerType("rag");
void store.setStatus("low_confidence");
void store.setProcessStatus("reviewed");
void store.setPage(2);
void store.resetFilters();
void store.selectLog("log-rag-inverter");
void store.closeDetail();
void store.copyTraceId("trace_qa_001");
void store.markProcessed("log-rag-inverter");
void store.createUnansweredFromLog("log-refused-weather");
void (null as unknown as LogsAreQaLogItems);
void (null as unknown as FilterShape);
void (null as unknown as SummaryShape);
void (null as unknown as AnswerTypeOptionShape);
void (null as unknown as StatusOptionShape);
void (null as unknown as ProcessStatusOptionShape);
