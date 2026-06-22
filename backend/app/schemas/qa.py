from __future__ import annotations

from typing import Any, Literal
import uuid

from pydantic import BaseModel, Field, field_validator


AnswerTypeLiteral = Literal["rag", "general_llm", "refused", "none"]
IntentLiteral = Literal[
    "knowledge_base_qa",
    "general_explanation",
    "out_of_scope",
    "realtime_external",
    "invalid_input",
]


class QaAskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    session_id: uuid.UUID | None = None

    @field_validator("question")
    @classmethod
    def strip_question(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("question must not be empty")
        return stripped


class QaReferenceSchema(BaseModel):
    rank: int
    segment_id: str | None
    document_id: str | None
    heading_path: str
    excerpt: str
    vector_score: float | None
    keyword_score: float | None
    rrf_score: float | None
    rerank_score: float | None


class QaAskResponse(BaseModel):
    trace_id: str
    answer_type: AnswerTypeLiteral
    intent: IntentLiteral
    answer: str
    confidence: float | None
    references: list[QaReferenceSchema]
    decision: dict[str, Any]
