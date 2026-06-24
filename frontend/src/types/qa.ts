export type AnswerType = "rag" | "general_llm" | "refused" | "none";

export type QaIntent =
  | "knowledge_base_qa"
  | "general_explanation"
  | "out_of_scope"
  | "realtime_external"
  | "invalid_input";

export interface QaAskRequest {
  question: string;
  session_id?: string | null;
}

export interface QaReference {
  rank: number;
  segment_id: string | null;
  document_id: string | null;
  heading_path: string;
  excerpt: string;
  vector_score: number | null;
  keyword_score: number | null;
  rrf_score: number | null;
  rerank_score: number | null;
}

export interface QaAskResponse {
  trace_id: string;
  answer_type: AnswerType;
  intent: QaIntent;
  answer: string;
  confidence: number | null;
  references: QaReference[];
  decision: Record<string, unknown>;
}
