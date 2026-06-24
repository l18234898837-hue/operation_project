export type AnswerType = "rag" | "general_llm" | "refused" | "none";

export type QaIntent =
  | "knowledge_base_qa"
  | "general_explanation"
  | "out_of_scope"
  | "realtime_external"
  | "invalid_input";

export type BackendSessionId = `${string}-${string}-${string}-${string}-${string}`;

export interface QaAskRequest {
  question: string;
  session_id?: BackendSessionId | null;
}

export interface QaReference {
  rank: number;
  segment_id: string | null;
  document_id: string | null;
  document_file_name: string | null;
  heading_path: string;
  excerpt: string;
  vector_score: number | null;
  keyword_score: number | null;
  rrf_score: number | null;
  rerank_score: number | null;
  visible: boolean;
}

export interface QaAskResponse {
  session_id: BackendSessionId;
  trace_id: string;
  answer_type: AnswerType;
  intent: QaIntent;
  answer: string;
  confidence: number | null;
  references: QaReference[];
  decision: Record<string, unknown>;
}

export type QaStreamStatusStage = "understanding" | "rewriting" | "retrieving" | "generating" | "done" | "error";

export type QaStreamEvent =
  | { event: "status"; data: { stage: QaStreamStatusStage; message: string } }
  | { event: "answer_delta"; data: { text: string } }
  | { event: "references"; data: { references: QaReference[] } }
  | { event: "done"; data: QaAskResponse }
  | { event: "error"; data: { stage: "error"; message: string; error?: string } };

export interface AskQuestionStreamOptions {
  signal?: AbortSignal;
  onEvent: (event: QaStreamEvent) => void;
}
