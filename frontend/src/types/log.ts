export type QaLogAnswerType = "rag" | "general_llm" | "refused" | "none";

export type QaLogStatus =
  | "answered"
  | "insufficient_evidence"
  | "refused"
  | "low_confidence"
  | "error";

export type QaLogProcessStatus = "new" | "reviewed" | "resolved";

export interface QaLogReference {
  rank: number;
  document_id: string | null;
  segment_id: string | null;
  heading_path: string;
  excerpt: string;
  rerank_score: number | null;
}

export interface QaLogStageLatency {
  stage: "intent" | "retrieve" | "rerank" | "generate" | "total";
  label: string;
  milliseconds: number;
}

export interface QaLogItem {
  id: string;
  question: string;
  answerPreview: string;
  answerType: QaLogAnswerType;
  intent: string;
  status: QaLogStatus;
  processStatus: QaLogProcessStatus;
  confidence: number | null;
  traceId: string;
  referenceCount: number;
  latencyMs: number;
  createdAt: string;
  userName: string;
  references: QaLogReference[];
  stageLatencies: QaLogStageLatency[];
  decision: Record<string, unknown>;
  knowledgeGap: boolean;
  gapReason: string | null;
}

export interface QaLogFilters {
  keyword: string;
  answerType: QaLogAnswerType | "all";
  status: QaLogStatus | "all";
  processStatus: QaLogProcessStatus | "all";
  page: number;
  pageSize: number;
}

export interface QaLogSummary {
  total: number;
  answered: number;
  insufficientEvidence: number;
  refused: number;
  lowConfidence: number;
  highLatency: number;
}
