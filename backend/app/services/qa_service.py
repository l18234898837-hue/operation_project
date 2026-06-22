from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Protocol
import uuid

from sqlalchemy.orm import Session

from app.models.rag import (
    AnswerType,
    QaRecord,
    QaReference,
    QaSession,
    QaUnanswered,
)
from app.schemas.qa import QaAskResponse, QaReferenceSchema
from app.services.query_understanding import Intent, QueryUnderstandingResult


class UnderstandingClient(Protocol):
    async def understand(self, question: str) -> QueryUnderstandingResult:
        ...


class Retriever(Protocol):
    async def retrieve(self, query: str) -> list[object]:
        ...


class AnswerClient(Protocol):
    async def generate_rag(
        self,
        question: str,
        evidence: list[object],
        cautious: bool,
    ) -> str:
        ...

    async def generate_general(self, question: str) -> str:
        ...


@dataclass(frozen=True)
class QaDependencies:
    understanding_client: UnderstandingClient
    retriever: Retriever
    answer_client: AnswerClient


async def answer_question(
    session: Session,
    question: str,
    dependencies: QaDependencies,
    min_rerank_score: float,
    strong_rerank_score: float,
    reference_top_k: int,
    session_id: str | uuid.UUID | None = None,
) -> QaAskResponse:
    start = time.perf_counter()
    trace_id = uuid.uuid4().hex
    qa_session = _get_or_create_session(session, session_id)
    understanding = await dependencies.understanding_client.understand(question)

    if understanding.intent in _REFUSED_INTENTS:
        reason = understanding.refusal_reason or understanding.intent.value
        answer = _refusal_message(understanding)
        record = _add_record(
            session=session,
            qa_session=qa_session,
            trace_id=trace_id,
            question=question,
            understanding=understanding,
            answer=answer,
            answer_type=AnswerType.refused,
            confidence=understanding.confidence,
            latency_ms=_latency_ms(start),
            decision_extra={
                "route": "refused",
                "used_knowledge_base": False,
                "refusal_reason": reason,
            },
        )
        _add_unanswered(
            session=session,
            qa_session=qa_session,
            record=record,
            question=question,
            understanding=understanding,
            reason=reason,
        )
        session.commit()
        return _response_from_record(record, understanding.intent.value, [])

    if (
        understanding.intent == Intent.general_explanation
        and not understanding.should_use_knowledge_base
    ):
        answer = await dependencies.answer_client.generate_general(
            understanding.normalized_question
        )
        record = _add_record(
            session=session,
            qa_session=qa_session,
            trace_id=trace_id,
            question=question,
            understanding=understanding,
            answer=answer,
            answer_type=AnswerType.general_llm,
            confidence=understanding.confidence,
            latency_ms=_latency_ms(start),
            decision_extra={
                "route": "general_llm",
                "used_knowledge_base": False,
                "refusal_reason": None,
            },
        )
        session.commit()
        return _response_from_record(record, understanding.intent.value, [])

    search_query = understanding.search_query or understanding.normalized_question
    evidence = await dependencies.retriever.retrieve(search_query)
    top_score = _top_rerank_score(evidence)

    if top_score is None or top_score < min_rerank_score:
        answer = "当前知识库没有找到足够相关的依据，暂时无法可靠回答该问题。"
        record = _add_record(
            session=session,
            qa_session=qa_session,
            trace_id=trace_id,
            question=question,
            understanding=understanding,
            answer=answer,
            answer_type=AnswerType.refused,
            confidence=top_score,
            latency_ms=_latency_ms(start),
            decision_extra={
                "route": "refused",
                "used_knowledge_base": True,
                "refusal_reason": "low_confidence",
                "top1_rerank_score": top_score,
                "threshold": min_rerank_score,
            },
        )
        _add_unanswered(
            session=session,
            qa_session=qa_session,
            record=record,
            question=question,
            understanding=understanding,
            reason="low_confidence",
        )
        session.commit()
        return _response_from_record(record, understanding.intent.value, [])

    evidence_for_answer = evidence[:reference_top_k]
    cautious = top_score < strong_rerank_score
    answer = await dependencies.answer_client.generate_rag(
        question=understanding.normalized_question,
        evidence=evidence_for_answer,
        cautious=cautious,
    )
    record = _add_record(
        session=session,
        qa_session=qa_session,
        trace_id=trace_id,
        question=question,
        understanding=understanding,
        answer=answer,
        answer_type=AnswerType.rag,
        confidence=top_score,
        latency_ms=_latency_ms(start),
        decision_extra={
            "route": "rag",
            "used_knowledge_base": True,
            "refusal_reason": None,
            "top1_rerank_score": top_score,
            "threshold": min_rerank_score,
            "cautious": cautious,
        },
    )
    references = _add_references(session, record, evidence_for_answer)
    session.commit()
    return _response_from_record(record, understanding.intent.value, references)


def _get_or_create_session(
    session: Session,
    session_id: str | uuid.UUID | None,
) -> QaSession:
    if session_id:
        session_uuid = (
            session_id if isinstance(session_id, uuid.UUID) else uuid.UUID(session_id)
        )
        existing = session.get(QaSession, session_uuid)
        if existing is not None:
            return existing
        qa_session = QaSession(id=session_uuid)
    else:
        qa_session = QaSession()
    session.add(qa_session)
    session.flush()
    return qa_session


def _add_record(
    session: Session,
    qa_session: QaSession,
    trace_id: str,
    question: str,
    understanding: QueryUnderstandingResult,
    answer: str,
    answer_type: AnswerType,
    confidence: float | None,
    latency_ms: int,
    decision_extra: dict,
) -> QaRecord:
    decision_metadata = {
        "intent": understanding.intent.value,
        "normalized_question": understanding.normalized_question,
        "search_query": understanding.search_query,
        "should_use_knowledge_base": understanding.should_use_knowledge_base,
        "intent_confidence": understanding.confidence,
        "intent_reason": understanding.reason,
        **decision_extra,
    }
    record = QaRecord(
        session_id=qa_session.id,
        trace_id=trace_id,
        question=question,
        normalized_question=understanding.normalized_question,
        answer=answer,
        answer_type=answer_type,
        confidence=confidence,
        model_name=None,
        latency_ms=latency_ms,
        decision_metadata=decision_metadata,
    )
    session.add(record)
    session.flush()
    return record


def _add_references(
    session: Session,
    record: QaRecord,
    evidence: list[object],
) -> list[QaReferenceSchema]:
    references: list[QaReferenceSchema] = []
    for rank, item in enumerate(evidence, start=1):
        reference = QaReference(
            qa_record_id=record.id,
            document_id=_uuid_or_none(getattr(item, "document_id", None)),
            segment_id=_uuid_or_none(getattr(item, "segment_id", None)),
            rank=rank,
            relevance_score=getattr(item, "rerank_score", None),
            vector_score=getattr(item, "vector_score", None),
            keyword_score=getattr(item, "keyword_score", None),
            rrf_score=getattr(item, "rrf_score", None),
            excerpt=(getattr(item, "clean_text", "") or "")[:500],
            ref_metadata={"heading_path": getattr(item, "heading_path", "") or ""},
        )
        session.add(reference)
        references.append(_reference_schema(rank, item))
    return references


def _add_unanswered(
    session: Session,
    qa_session: QaSession,
    record: QaRecord,
    question: str,
    understanding: QueryUnderstandingResult,
    reason: str,
) -> None:
    session.add(
        QaUnanswered(
            session_id=qa_session.id,
            record_id=record.id,
            question=question,
            normalized_question=understanding.normalized_question,
            reason=reason,
        )
    )


def _response_from_record(
    record: QaRecord,
    intent: str,
    references: list[QaReferenceSchema],
) -> QaAskResponse:
    return QaAskResponse(
        trace_id=record.trace_id or "",
        answer_type=record.answer_type.value,
        intent=intent,
        answer=record.answer or "",
        confidence=record.confidence,
        references=references,
        decision=dict(record.decision_metadata or {}),
    )


def _reference_schema(rank: int, item: object) -> QaReferenceSchema:
    return QaReferenceSchema(
        rank=rank,
        segment_id=str(getattr(item, "segment_id", "") or "") or None,
        document_id=str(getattr(item, "document_id", "") or "") or None,
        heading_path=getattr(item, "heading_path", "") or "",
        excerpt=(getattr(item, "clean_text", "") or "")[:500],
        vector_score=getattr(item, "vector_score", None),
        keyword_score=getattr(item, "keyword_score", None),
        rrf_score=getattr(item, "rrf_score", None),
        rerank_score=getattr(item, "rerank_score", None),
    )


def _top_rerank_score(evidence: list[object]) -> float | None:
    if not evidence:
        return None
    score = getattr(evidence[0], "rerank_score", None)
    return float(score) if score is not None else None


def _latency_ms(start: float) -> int:
    return int((time.perf_counter() - start) * 1000)


def _uuid_or_none(value: object) -> uuid.UUID | None:
    if value is None:
        return None
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except ValueError:
        return None


def _refusal_message(understanding: QueryUnderstandingResult) -> str:
    if understanding.intent == Intent.invalid_input:
        return "请补充一个明确的问题。"
    if understanding.intent == Intent.realtime_external:
        return "当前系统未接入实时外部数据源，暂时无法回答该实时信息问题。"
    return "当前问题不在本系统支持范围内。"


_REFUSED_INTENTS = {
    Intent.invalid_input,
    Intent.realtime_external,
    Intent.out_of_scope,
}
