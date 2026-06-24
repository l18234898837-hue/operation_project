import type { AnswerType } from "../types/qa";

export type AnswerTone = "success" | "info" | "warn" | "muted";

export interface AnswerTypeDescription {
  label: string;
  tone: AnswerTone;
}

export function describeAnswerType(answerType: "rag"): { label: "基于知识库回答"; tone: "success" };
export function describeAnswerType(answerType: "general_llm"): { label: "通用解释"; tone: "info" };
export function describeAnswerType(answerType: "refused"): { label: "暂无法回答"; tone: "warn" };
export function describeAnswerType(answerType: "none"): { label: "暂无答案"; tone: "muted" };
export function describeAnswerType(answerType: AnswerType): AnswerTypeDescription;
export function describeAnswerType(answerType: AnswerType): AnswerTypeDescription {
  switch (answerType) {
    case "rag":
      return { label: "基于知识库回答", tone: "success" };
    case "general_llm":
      return { label: "通用解释", tone: "info" };
    case "refused":
      return { label: "暂无法回答", tone: "warn" };
    case "none":
      return { label: "暂无答案", tone: "muted" };
    default:
      return { label: "未知状态", tone: "muted" };
  }
}

export function formatConfidence(confidence: null): "暂无置信度";
export function formatConfidence(confidence: 0.858): "86%";
export function formatConfidence(confidence: number | null): string;
export function formatConfidence(confidence: number | null): string {
  if (confidence === null || Number.isNaN(confidence)) {
    return "暂无置信度";
  }

  return `${Math.round(confidence * 100)}%`;
}
