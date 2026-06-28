from __future__ import annotations

from dataclasses import dataclass
import logging
import time
from typing import Awaitable, Callable, Protocol
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.rag import (
    AnswerType,
    KbDocument,
    QaRecord,
    QaReference,
    QaSession,
    QaUnanswered,
)
from app.schemas.qa import QaAskResponse, QaReferenceSchema
from app.services.conversation_context import (
    ConversationContext,
    build_conversation_context,
)
from app.services.conversation_rewrite import StandaloneQuestionResult
from app.services.evidence_filtering import (
    compress_evidence_for_generation,
    filter_evidence_for_answer,
    filter_references_for_response,
    select_evidence_compression_policy,
)
from app.services.evidence_alignment import check_evidence_directly_supports_question
from app.services.qa_debug_logging import log_qa_debug_event
from app.services.qa_error_handling import classify_qa_exception
from app.services.qa_trace import (
    QaTraceCollector,
    persist_trace_steps,
)
from app.services.query_understanding import (
    Intent,
    QueryUnderstandingResult,
    apply_intent_hard_rules,
)
from app.services.rag_confidence_policy import (
    effective_low_confidence_threshold,
    effective_strong_rag_threshold,
)

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[str, str, dict[str, object] | None], Awaitable[None]]


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

    async def generate_general(self, question: str, mode: str = "general") -> str:
        ...

    async def generate_low_confidence_rag(
        self,
        question: str,
        evidence: list[object],
        top_score: float | None,
    ) -> str:
        ...


class ContextRewriter(Protocol):
    async def rewrite(
        self,
        question: str,
        context: ConversationContext,
    ) -> StandaloneQuestionResult:
        ...


class SessionSummarizer(Protocol):
    async def update_if_needed(
        self,
        qa_session: QaSession,
        records: list[QaRecord],
    ) -> bool:
        ...


@dataclass(frozen=True)
class QaDependencies:
    understanding_client: UnderstandingClient
    retriever: Retriever
    answer_client: AnswerClient
    context_rewriter: ContextRewriter | None = None
    session_summarizer: SessionSummarizer | None = None
    progress_callback: ProgressCallback | None = None


@dataclass(frozen=True)
class QaDebugContext:
    enabled: bool = False
    preview_chars: int = 80
    evidence_preview_enabled: bool = False


@dataclass(frozen=True)
class QaSessionInitResult:
    qa_session: QaSession
    diagnostics: dict[str, object]


async def answer_question(
    session: Session,
    question: str,
    dependencies: QaDependencies,
    min_rerank_score: float,
    strong_rerank_score: float,
    reference_top_k: int,
    session_id: str | uuid.UUID | None = None,
    history_turns: int = 10,
    context_max_chars: int = 8000,
    answer_excerpt_chars: int = 500,
    qa_evidence_min_score: float = 0.3,
    qa_reference_min_score: float = 0.3,
    qa_reference_visible_top_k: int = 3,
    qa_reference_max_top_k: int = 5,
    qa_debug_log_enabled: bool = False,
    qa_debug_question_preview_chars: int = 80,
    qa_debug_evidence_preview_enabled: bool = False,
) -> QaAskResponse:
    start = time.perf_counter()
    trace_id = uuid.uuid4().hex
    trace = QaTraceCollector(trace_id=trace_id)
    timings: dict[str, int] = {}
    qa_session: QaSession | None = None
    debug_context = QaDebugContext(
        enabled=qa_debug_log_enabled,
        preview_chars=qa_debug_question_preview_chars,
        evidence_preview_enabled=qa_debug_evidence_preview_enabled,
    )
    try:
        _log_debug(
            debug_context,
            "qa.request.start",
            trace_id=trace_id,
            session_id=session_id,
            question=question,
            question_length=len(question),
        )
        step_start = time.perf_counter()
        session_init = _get_or_create_session(session, session_id)
        qa_session = session_init.qa_session
        _record_timing(timings, trace, "get_or_create_session", step_start)
        _merge_timing_diagnostics(timings, "get_or_create_session", session_init.diagnostics)
        _log_debug(
            debug_context,
            "qa.session.ready",
            trace_id=trace_id,
            session_id=qa_session.id,
            duration_ms=timings.get("get_or_create_session_ms"),
            diagnostics=session_init.diagnostics,
        )
        return await _answer_question_inner(
            session=session,
            qa_session=qa_session,
            question=question,
            dependencies=dependencies,
            min_rerank_score=min_rerank_score,
            strong_rerank_score=strong_rerank_score,
            reference_top_k=reference_top_k,
            history_turns=history_turns,
            context_max_chars=context_max_chars,
            answer_excerpt_chars=answer_excerpt_chars,
            qa_evidence_min_score=qa_evidence_min_score,
            qa_reference_min_score=qa_reference_min_score,
            qa_reference_visible_top_k=qa_reference_visible_top_k,
            qa_reference_max_top_k=qa_reference_max_top_k,
            trace_id=trace_id,
            trace=trace,
            start=start,
            timings=timings,
            debug_context=debug_context,
        )
    except Exception as exc:
        _log_debug(
            debug_context,
            "qa.exception",
            trace_id=trace_id,
            session_id=getattr(qa_session, "id", session_id),
            error_type=type(exc).__name__,
            error=str(exc),
        )
        step_start = time.perf_counter()
        session.rollback()
        _record_timing(timings, trace, "rollback", step_start)
        fallback_session_id = session_id or getattr(qa_session, "id", None)
        step_start = time.perf_counter()
        session_init = _get_or_create_session(session, fallback_session_id)
        qa_session = session_init.qa_session
        _record_timing(timings, trace, "fallback_session", step_start)
        _merge_timing_diagnostics(timings, "fallback_session", session_init.diagnostics)
        decision = classify_qa_exception(exc)
        understanding = QueryUnderstandingResult(
            intent=Intent.out_of_scope,
            confidence=0.0,
            should_use_knowledge_base=False,
            normalized_question=question,
            search_query="",
            refusal_reason=decision.reason,
            reason=decision.reason,
        )
        record = _add_record(
            session=session,
            qa_session=qa_session,
            trace_id=trace_id,
            question=question,
            understanding=understanding,
            answer=decision.user_message,
            answer_type=AnswerType.refused,
            confidence=None,
            latency_ms=_latency_ms(start),
            decision_extra={
                "route": "refused",
                "used_knowledge_base": False,
                "refusal_reason": decision.reason,
                "error_status_code": decision.status_code,
                "timings_ms": _timings_snapshot(start, timings),
            },
        )
        trace.record_step(
            step_name="qa_exception",
            duration_ms=_latency_ms(start),
            status="failed",
            error_message=str(exc)[:1000],
            metadata={"reason": decision.reason},
        )
        if decision.should_record_unanswered:
            _add_unanswered(
                session=session,
                qa_session=qa_session,
                record=record,
                question=question,
                understanding=understanding,
                reason=decision.reason,
            )
        trace.record_step(
            step_name="db_commit",
            duration_ms=0,
            metadata={"route": "refused"},
        )
        persist_trace_steps(session=session, record_id=record.id, collector=trace)
        step_start = time.perf_counter()
        session.commit()
        timings["db_commit_ms"] = _elapsed_ms(step_start)
        timings["total_ms"] = _latency_ms(start)
        _log_timing(
            trace_id=trace_id,
            session_id=qa_session.id,
            route="refused",
            timings=timings,
            error_reason=decision.reason,
        )
        _log_debug(
            debug_context,
            "qa.request.finish",
            trace_id=trace_id,
            session_id=qa_session.id,
            route="refused",
            answer_type=AnswerType.refused.value,
            intent=understanding.intent.value,
            error_reason=decision.reason,
            total_ms=timings.get("total_ms"),
            timings_ms=timings,
        )
        return _response_from_record(record, understanding.intent.value, [])


async def _answer_question_inner(
    session: Session,
    qa_session: QaSession,
    question: str,
    dependencies: QaDependencies,
    min_rerank_score: float,
    strong_rerank_score: float,
    reference_top_k: int,
    history_turns: int,
    context_max_chars: int,
    answer_excerpt_chars: int,
    qa_evidence_min_score: float,
    qa_reference_min_score: float,
    qa_reference_visible_top_k: int,
    qa_reference_max_top_k: int,
    trace_id: str,
    trace: QaTraceCollector,
    start: float,
    timings: dict[str, int],
    debug_context: QaDebugContext,
) -> QaAskResponse:
    await _emit_progress(
        dependencies,
        "understanding",
        "正在理解你的问题...",
    )
    hard_rule_understanding = apply_intent_hard_rules(question)
    if (
        hard_rule_understanding is not None
        and hard_rule_understanding.intent
        in {Intent.chitchat, Intent.invalid_input, Intent.realtime_external}
    ):
        _log_debug(
            debug_context,
            "qa.intent.hard_rule",
            trace_id=trace_id,
            session_id=qa_session.id,
            intent=hard_rule_understanding.intent.value,
            should_use_knowledge_base=hard_rule_understanding.should_use_knowledge_base,
            normalized_question=hard_rule_understanding.normalized_question,
            search_query=hard_rule_understanding.search_query,
            reason=hard_rule_understanding.reason,
            skip_rewrite=True,
            skip_llm_intent=True,
        )
        trace.record_step(
            step_name="pre_route",
            duration_ms=0,
            metadata={
                "intent": hard_rule_understanding.intent.value,
                "reason": hard_rule_understanding.reason,
                "skip_rewrite": True,
                "skip_llm_intent": True,
            },
        )
        if hard_rule_understanding.intent == Intent.chitchat:
            await _emit_progress(
                dependencies,
                "quick_reply",
                "收到，马上回复...",
            )
            return await _answer_general_route(
                session=session,
                dependencies=dependencies,
                qa_session=qa_session,
                previous_records=[],
                question=question,
                understanding=hard_rule_understanding,
                rewrite_metadata=_skipped_rewrite_metadata(question, "pre_route_chitchat"),
                mode="chitchat",
                route="chitchat",
                trace_id=trace_id,
                trace=trace,
                start=start,
                timings=timings,
                debug_context=debug_context,
            )
        if hard_rule_understanding.intent == Intent.invalid_input:
            return await _answer_refused_route(
                session=session,
                dependencies=dependencies,
                qa_session=qa_session,
                previous_records=[],
                question=question,
                understanding=hard_rule_understanding,
                rewrite_metadata=_skipped_rewrite_metadata(question, "pre_route_invalid_input"),
                reason=hard_rule_understanding.refusal_reason or hard_rule_understanding.intent.value,
                trace_id=trace_id,
                trace=trace,
                start=start,
                timings=timings,
                debug_context=debug_context,
            )
        if hard_rule_understanding.intent == Intent.realtime_external:
            await _emit_progress(
                dependencies,
                "generating",
                "当前未接入实时数据源，正在整理通用建议...",
            )
            return await _answer_general_route(
                session=session,
                dependencies=dependencies,
                qa_session=qa_session,
                previous_records=[],
                question=question,
                understanding=hard_rule_understanding,
                rewrite_metadata=_skipped_rewrite_metadata(question, "pre_route_realtime_external"),
                mode="realtime_external",
                route="realtime_external",
                trace_id=trace_id,
                trace=trace,
                start=start,
                timings=timings,
                debug_context=debug_context,
            )

    step_start = time.perf_counter()
    await _emit_progress(
        dependencies,
        "context",
        "正在整理会话上下文...",
    )
    previous_records = _list_session_records(session, qa_session.id)
    _record_timing(timings, trace, "load_history", step_start)
    _log_debug(
        debug_context,
        "qa.history.loaded",
        trace_id=trace_id,
        session_id=qa_session.id,
        records_count=len(previous_records),
        duration_ms=timings.get("load_history_ms"),
    )

    step_start = time.perf_counter()
    context = build_conversation_context(
        records=previous_records,
        session_metadata=qa_session.session_metadata,
        history_turns=history_turns,
        answer_excerpt_chars=answer_excerpt_chars,
        max_chars=context_max_chars,
    )
    _record_timing(timings, trace, "build_context", step_start)
    _log_debug(
        debug_context,
        "qa.context.built",
        trace_id=trace_id,
        session_id=qa_session.id,
        used_history=context.used_history,
        recent_turns_count=len(context.recent_turns),
        has_summary=bool(context.session_summary),
        duration_ms=timings.get("build_context_ms"),
    )

    step_start = time.perf_counter()
    if context.used_history:
        await _emit_progress(
            dependencies,
            "rewriting",
            "正在结合本轮会话上下文...",
        )
    rewrite_result = await _rewrite_question(question, context, dependencies)
    _record_timing(timings, trace, "rewrite_question", step_start)
    question_for_understanding = rewrite_result.standalone_question
    _log_debug(
        debug_context,
        "qa.question.rewritten",
        trace_id=trace_id,
        session_id=qa_session.id,
        standalone_question=question_for_understanding,
        used_history=rewrite_result.used_history,
        is_follow_up=rewrite_result.is_follow_up,
        reason=rewrite_result.reason,
        duration_ms=timings.get("rewrite_question_ms"),
    )

    step_start = time.perf_counter()
    await _emit_progress(
        dependencies,
        "understanding",
        "正在判断是否需要查询知识库...",
    )
    hard_rule_understanding = apply_intent_hard_rules(question_for_understanding)
    if hard_rule_understanding is not None:
        understanding = hard_rule_understanding
    else:
        understanding = await dependencies.understanding_client.understand(
            question_for_understanding
        )
    _record_timing(timings, trace, "understand_intent", step_start)
    rewrite_metadata = _rewrite_metadata(question, rewrite_result)
    _log_debug(
        debug_context,
        "qa.intent.understood",
        trace_id=trace_id,
        session_id=qa_session.id,
        intent=understanding.intent.value,
        intent_confidence=understanding.confidence,
        should_use_knowledge_base=understanding.should_use_knowledge_base,
        normalized_question=understanding.normalized_question,
        search_query=understanding.search_query,
        reason=understanding.reason,
        duration_ms=timings.get("understand_intent_ms"),
    )

    if (
        understanding.intent == Intent.chitchat
        and not understanding.should_use_knowledge_base
    ):
        await _emit_progress(
            dependencies,
            "quick_reply",
            "收到，马上回复...",
        )
        return await _answer_general_route(
            session=session,
            dependencies=dependencies,
            qa_session=qa_session,
            previous_records=previous_records,
            question=question,
            understanding=understanding,
            rewrite_metadata=rewrite_metadata,
            mode="chitchat",
            route="chitchat",
            trace_id=trace_id,
            trace=trace,
            start=start,
            timings=timings,
            debug_context=debug_context,
        )

    if (
        understanding.intent == Intent.realtime_external
        and not understanding.should_use_knowledge_base
    ):
        await _emit_progress(
            dependencies,
            "generating",
            "当前未接入实时数据源，正在整理通用建议...",
        )
        return await _answer_general_route(
            session=session,
            dependencies=dependencies,
            qa_session=qa_session,
            previous_records=previous_records,
            question=question,
            understanding=understanding,
            rewrite_metadata=rewrite_metadata,
            mode="realtime_external",
            route="realtime_external",
            trace_id=trace_id,
            trace=trace,
            start=start,
            timings=timings,
            debug_context=debug_context,
        )

    if understanding.intent in _REFUSED_INTENTS:
        return await _answer_refused_route(
            session=session,
            dependencies=dependencies,
            qa_session=qa_session,
            previous_records=previous_records,
            question=question,
            understanding=understanding,
            rewrite_metadata=rewrite_metadata,
            reason=understanding.refusal_reason or understanding.intent.value,
            trace_id=trace_id,
            trace=trace,
            start=start,
            timings=timings,
            debug_context=debug_context,
        )

    if (
        understanding.intent == Intent.general_explanation
        and not understanding.should_use_knowledge_base
    ):
        return await _answer_general_route(
            session=session,
            dependencies=dependencies,
            qa_session=qa_session,
            previous_records=previous_records,
            question=question,
            understanding=understanding,
            rewrite_metadata=rewrite_metadata,
            mode="general",
            route="general_llm",
            trace_id=trace_id,
            trace=trace,
            start=start,
            timings=timings,
            debug_context=debug_context,
        )

    return await _answer_rag_route(
        session=session,
        dependencies=dependencies,
        qa_session=qa_session,
        previous_records=previous_records,
        question=question,
        understanding=understanding,
        rewrite_metadata=rewrite_metadata,
        min_rerank_score=min_rerank_score,
        strong_rerank_score=strong_rerank_score,
        qa_evidence_min_score=qa_evidence_min_score,
        qa_reference_min_score=qa_reference_min_score,
        qa_reference_visible_top_k=qa_reference_visible_top_k,
        qa_reference_max_top_k=qa_reference_max_top_k,
        trace_id=trace_id,
        trace=trace,
        start=start,
        timings=timings,
        debug_context=debug_context,
    )


async def _answer_general_route(
    session: Session,
    dependencies: QaDependencies,
    qa_session: QaSession,
    previous_records: list[QaRecord],
    question: str,
    understanding: QueryUnderstandingResult,
    rewrite_metadata: dict[str, object],
    mode: str,
    route: str,
    trace_id: str,
    trace: QaTraceCollector,
    start: float,
    timings: dict[str, int],
    debug_context: QaDebugContext,
) -> QaAskResponse:
    step_start = time.perf_counter()
    answer = await dependencies.answer_client.generate_general(
        understanding.normalized_question,
        mode=mode,
    )
    _record_timing(timings, trace, "answer_generation", step_start)
    answer_diagnostics = _answer_diagnostics(dependencies.answer_client)
    _merge_timing_diagnostics(timings, "answer_generation", answer_diagnostics)
    _log_debug(
        debug_context,
        "qa.answer.generated",
        trace_id=trace_id,
        session_id=qa_session.id,
        route=route,
        diagnostics=answer_diagnostics,
        duration_ms=timings.get("answer_generation_ms"),
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
            **rewrite_metadata,
            "route": route,
            "used_knowledge_base": False,
            "refusal_reason": None,
            "answer_mode": mode,
            "timings_ms": _timings_snapshot(start, timings),
        },
    )
    return await _finalize_response(
        session=session,
        dependencies=dependencies,
        qa_session=qa_session,
        records=[*previous_records, record],
        record=record,
        intent=understanding.intent.value,
        references=[],
        trace_id=trace_id,
        trace=trace,
        start=start,
        timings=timings,
        route=route,
        debug_context=debug_context,
    )


async def _answer_refused_route(
    session: Session,
    dependencies: QaDependencies,
    qa_session: QaSession,
    previous_records: list[QaRecord],
    question: str,
    understanding: QueryUnderstandingResult,
    rewrite_metadata: dict[str, object],
    reason: str,
    trace_id: str,
    trace: QaTraceCollector,
    start: float,
    timings: dict[str, int],
    debug_context: QaDebugContext,
) -> QaAskResponse:
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
            **rewrite_metadata,
            "route": "refused",
            "used_knowledge_base": False,
            "refusal_reason": reason,
            "timings_ms": _timings_snapshot(start, timings),
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
    return await _finalize_response(
        session=session,
        dependencies=dependencies,
        qa_session=qa_session,
        records=[*previous_records, record],
        record=record,
        intent=understanding.intent.value,
        references=[],
        trace_id=trace_id,
        trace=trace,
        start=start,
        timings=timings,
        route="refused",
        debug_context=debug_context,
    )


async def _answer_low_confidence_supplement_route(
    session: Session,
    dependencies: QaDependencies,
    qa_session: QaSession,
    previous_records: list[QaRecord],
    question: str,
    understanding: QueryUnderstandingResult,
    rewrite_metadata: dict[str, object],
    evidence: list[object],
    top_score: float | None,
    min_rerank_score: float,
    configured_min_rerank_score: float,
    intent: str,
    trace_id: str,
    trace: QaTraceCollector,
    start: float,
    timings: dict[str, int],
    debug_context: QaDebugContext,
) -> QaAskResponse:
    step_start = time.perf_counter()
    low_confidence_evidence = compress_evidence_for_generation(
        evidence[:4],
        max_chars_per_item=500,
    )
    await _emit_progress(
        dependencies,
        "low_confidence",
        "知识库资料不够充分，正在结合可参考片段和通用运维经验整理建议...",
        {
            "top1_rerank_score": top_score,
            "generation_evidence_count": len(low_confidence_evidence),
        },
    )
    answer = await dependencies.answer_client.generate_low_confidence_rag(
        question=understanding.normalized_question,
        evidence=low_confidence_evidence,
        top_score=top_score,
    )
    _record_timing(timings, trace, "answer_generation", step_start)
    answer_diagnostics = _answer_diagnostics(dependencies.answer_client)
    _merge_timing_diagnostics(timings, "answer_generation", answer_diagnostics)
    _log_debug(
        debug_context,
        "qa.answer.generated",
        trace_id=trace_id,
        session_id=qa_session.id,
        route="rag_low_confidence_supplement",
        diagnostics=answer_diagnostics,
        duration_ms=timings.get("answer_generation_ms"),
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
            **rewrite_metadata,
            "route": "rag_low_confidence_supplement",
            "used_knowledge_base": True,
            "refusal_reason": None,
            "answer_mode": "low_confidence_supplement",
            "top1_rerank_score": top_score,
            "threshold": min_rerank_score,
            "configured_low_confidence_threshold": configured_min_rerank_score,
            "effective_low_confidence_threshold": min_rerank_score,
            "generation_evidence_count": len(low_confidence_evidence),
            "generation_evidence_chars": _evidence_chars(low_confidence_evidence),
            "timings_ms": _timings_snapshot(start, timings),
        },
    )
    references = _add_references(
        session=session,
        record=record,
        evidence=evidence[:4],
        visible_top_k=min(3, len(evidence[:4])),
        usage_note="仅作相关片段参考",
    )
    return await _finalize_response(
        session=session,
        dependencies=dependencies,
        qa_session=qa_session,
        records=[*previous_records, record],
        record=record,
        intent=intent,
        references=references,
        trace_id=trace_id,
        trace=trace,
        start=start,
        timings=timings,
        route="rag_low_confidence_supplement",
        debug_context=debug_context,
    )


async def _answer_rag_route(
    session: Session,
    dependencies: QaDependencies,
    qa_session: QaSession,
    previous_records: list[QaRecord],
    question: str,
    understanding: QueryUnderstandingResult,
    rewrite_metadata: dict[str, object],
    min_rerank_score: float,
    strong_rerank_score: float,
    qa_evidence_min_score: float,
    qa_reference_min_score: float,
    qa_reference_visible_top_k: int,
    qa_reference_max_top_k: int,
    trace_id: str,
    trace: QaTraceCollector,
    start: float,
    timings: dict[str, int],
    debug_context: QaDebugContext,
) -> QaAskResponse:
    search_query = understanding.search_query or understanding.normalized_question
    low_confidence_threshold = effective_low_confidence_threshold(min_rerank_score)
    strong_rag_threshold = effective_strong_rag_threshold(strong_rerank_score)
    step_start = time.perf_counter()
    await _emit_progress(
        dependencies,
        "retrieving",
        "正在查找光伏运维知识库...",
    )
    evidence = await dependencies.retriever.retrieve(search_query)
    _record_timing(timings, trace, "retrieve_evidence", step_start)
    retrieval_diagnostics = _retrieval_diagnostics(dependencies.retriever)
    _merge_timing_diagnostics(timings, "retrieve_evidence", retrieval_diagnostics)
    top_score = _top_rerank_score(evidence)
    _log_debug(
        debug_context,
        "qa.evidence.retrieved",
        trace_id=trace_id,
        session_id=qa_session.id,
        search_query=search_query,
        evidence=evidence,
        evidence_count=len(evidence),
        top1_rerank_score=top_score,
        diagnostics=retrieval_diagnostics,
        duration_ms=timings.get("retrieve_evidence_ms"),
    )

    if top_score is None:
        await _emit_progress(
            dependencies,
            "low_confidence",
            "知识库匹配度较低，正在判断是否可以可靠回答...",
            {
                "top1_rerank_score": top_score,
            },
        )
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
                **rewrite_metadata,
                "route": "refused",
                "used_knowledge_base": True,
                "refusal_reason": "low_confidence",
                "top1_rerank_score": top_score,
                "threshold": low_confidence_threshold,
                "configured_low_confidence_threshold": min_rerank_score,
                "effective_low_confidence_threshold": low_confidence_threshold,
                "timings_ms": _timings_snapshot(start, timings),
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
        return await _finalize_response(
            session=session,
            dependencies=dependencies,
            qa_session=qa_session,
            records=[*previous_records, record],
            record=record,
            intent=understanding.intent.value,
            references=[],
            trace_id=trace_id,
            trace=trace,
            start=start,
            timings=timings,
            route="refused",
            debug_context=debug_context,
        )

    if top_score < low_confidence_threshold:
        return await _answer_low_confidence_supplement_route(
            session=session,
            dependencies=dependencies,
            qa_session=qa_session,
            previous_records=previous_records,
            question=question,
            understanding=understanding,
            rewrite_metadata=rewrite_metadata,
            evidence=evidence,
            top_score=top_score,
            min_rerank_score=low_confidence_threshold,
            configured_min_rerank_score=min_rerank_score,
            intent=understanding.intent.value,
            trace_id=trace_id,
            trace=trace,
            start=start,
            timings=timings,
            debug_context=debug_context,
        )

    step_start = time.perf_counter()
    compression_policy = select_evidence_compression_policy(evidence)
    evidence_for_answer = filter_evidence_for_answer(
        evidence=evidence,
        min_rerank_score=qa_evidence_min_score,
        max_items=compression_policy.max_items,
    )
    evidence_for_generation = compress_evidence_for_generation(
        evidence_for_answer,
        max_chars_per_item=compression_policy.max_chars_per_item,
    )
    evidence_for_response = filter_references_for_response(
        evidence=evidence,
        min_rerank_score=qa_reference_min_score,
        max_items=qa_reference_max_top_k,
    )
    _record_timing(timings, trace, "filter_evidence", step_start)
    await _emit_progress(
        dependencies,
        "evidence_ready",
        _evidence_ready_message(
            evidence_count=len(evidence_for_generation),
            compression_reason=compression_policy.reason,
        ),
        {
            "evidence_count": len(evidence_for_generation),
            "reference_count": len(evidence_for_response),
            "generation_evidence_chars": _evidence_chars(evidence_for_generation),
            "evidence_compression_reason": compression_policy.reason,
        },
    )
    _log_debug(
        debug_context,
        "qa.evidence.filtered",
        trace_id=trace_id,
        session_id=qa_session.id,
        evidence_for_answer_count=len(evidence_for_answer),
        generation_evidence_count=len(evidence_for_generation),
        generation_evidence_chars=_evidence_chars(evidence_for_generation),
        evidence_compression_reason=compression_policy.reason,
        evidence_max_chars_per_item=compression_policy.max_chars_per_item,
        reference_count=len(evidence_for_response),
        evidence_min_score=qa_evidence_min_score,
        reference_min_score=qa_reference_min_score,
        duration_ms=timings.get("filter_evidence_ms"),
    )
    if not evidence_for_answer:
        await _emit_progress(
            dependencies,
            "low_confidence",
            "知识库匹配度较低，正在结合资料和通用运维经验整理建议...",
        )
        return await _answer_low_confidence_supplement_route(
            session=session,
            dependencies=dependencies,
            qa_session=qa_session,
            previous_records=previous_records,
            question=question,
            understanding=understanding,
            rewrite_metadata=rewrite_metadata,
            evidence=evidence,
            top_score=top_score,
            min_rerank_score=low_confidence_threshold,
            configured_min_rerank_score=min_rerank_score,
            intent=understanding.intent.value,
            trace_id=trace_id,
            trace=trace,
            start=start,
            timings=timings,
            debug_context=debug_context,
        )

    alignment = check_evidence_directly_supports_question(
        understanding.normalized_question,
        evidence_for_answer,
    )
    if not alignment.directly_supported:
        await _emit_progress(
            dependencies,
            "low_confidence",
            "找到的资料与问题主题不完全匹配，正在结合可参考片段和通用运维经验整理建议...",
            {
                "top1_rerank_score": top_score,
                "evidence_alignment": alignment.to_metadata(),
            },
        )
        return await _answer_low_confidence_supplement_route(
            session=session,
            dependencies=dependencies,
            qa_session=qa_session,
            previous_records=previous_records,
            question=question,
            understanding=understanding,
            rewrite_metadata={
                **rewrite_metadata,
                "evidence_alignment": alignment.to_metadata(),
            },
            evidence=evidence,
            top_score=top_score,
            min_rerank_score=low_confidence_threshold,
            configured_min_rerank_score=min_rerank_score,
            intent=understanding.intent.value,
            trace_id=trace_id,
            trace=trace,
            start=start,
            timings=timings,
            debug_context=debug_context,
        )

    cautious = top_score < strong_rag_threshold
    step_start = time.perf_counter()
    await _emit_progress(
        dependencies,
        "generating",
        "正在根据资料生成回答...",
    )
    answer = await dependencies.answer_client.generate_rag(
        question=understanding.normalized_question,
        evidence=evidence_for_generation,
        cautious=cautious,
    )
    _record_timing(timings, trace, "answer_generation", step_start)
    answer_diagnostics = _answer_diagnostics(dependencies.answer_client)
    _merge_timing_diagnostics(timings, "answer_generation", answer_diagnostics)
    _log_debug(
        debug_context,
        "qa.answer.generated",
        trace_id=trace_id,
        session_id=qa_session.id,
        route="rag",
        diagnostics=answer_diagnostics,
        duration_ms=timings.get("answer_generation_ms"),
    )

    step_start = time.perf_counter()
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
            **rewrite_metadata,
            "route": "rag",
            "used_knowledge_base": True,
            "refusal_reason": None,
            "top1_rerank_score": top_score,
            "threshold": low_confidence_threshold,
            "configured_low_confidence_threshold": min_rerank_score,
            "effective_low_confidence_threshold": low_confidence_threshold,
            "configured_strong_rag_threshold": strong_rerank_score,
            "effective_strong_rag_threshold": strong_rag_threshold,
            "evidence_min_score": qa_evidence_min_score,
            "reference_min_score": qa_reference_min_score,
            "reference_visible_top_k": qa_reference_visible_top_k,
            "reference_max_top_k": qa_reference_max_top_k,
            "cautious": cautious,
            "evidence_for_answer_count": len(evidence_for_answer),
            "generation_evidence_count": len(evidence_for_generation),
            "generation_evidence_chars": _evidence_chars(evidence_for_generation),
            "evidence_compression_reason": compression_policy.reason,
            "evidence_max_chars_per_item": compression_policy.max_chars_per_item,
            "reference_count": len(evidence_for_response),
            "timings_ms": _timings_snapshot(start, timings),
        },
    )
    references = _add_references(
        session,
        record,
        evidence_for_response,
        visible_top_k=qa_reference_visible_top_k,
    )
    _record_timing(timings, trace, "db_write_record", step_start)
    return await _finalize_response(
        session=session,
        dependencies=dependencies,
        qa_session=qa_session,
        records=[*previous_records, record],
        record=record,
        intent=understanding.intent.value,
        references=references,
        trace_id=trace_id,
        trace=trace,
        start=start,
        timings=timings,
        route="rag",
        debug_context=debug_context,
    )


def _get_or_create_session(
    session: Session,
    session_id: str | uuid.UUID | None,
) -> QaSessionInitResult:
    diagnostics: dict[str, object] = {
        "has_input_session_id": bool(session_id),
        "connection_checkout_ms": 0,
        "connection_checkout_skipped": not hasattr(session, "connection"),
        "parse_session_id_ms": 0,
        "session_get_ms": 0,
        "session_get_skipped": not bool(session_id) or not hasattr(session, "get"),
        "session_found": False,
        "session_add_ms": 0,
        "session_flush_ms": 0,
        "created": False,
    }

    if hasattr(session, "connection"):
        step_start = time.perf_counter()
        session.connection()
        diagnostics["connection_checkout_ms"] = _elapsed_ms(step_start)

    if session_id:
        step_start = time.perf_counter()
        session_uuid = (
            session_id if isinstance(session_id, uuid.UUID) else uuid.UUID(str(session_id))
        )
        diagnostics["parse_session_id_ms"] = _elapsed_ms(step_start)
        if hasattr(session, "get"):
            step_start = time.perf_counter()
            existing = session.get(QaSession, session_uuid)
            diagnostics["session_get_ms"] = _elapsed_ms(step_start)
        else:
            existing = None
        if existing is not None:
            diagnostics["session_found"] = True
            return QaSessionInitResult(existing, diagnostics)
        qa_session = QaSession(id=session_uuid)
    else:
        qa_session = QaSession()
    step_start = time.perf_counter()
    session.add(qa_session)
    diagnostics["session_add_ms"] = _elapsed_ms(step_start)
    step_start = time.perf_counter()
    session.flush()
    diagnostics["session_flush_ms"] = _elapsed_ms(step_start)
    diagnostics["created"] = True
    return QaSessionInitResult(qa_session, diagnostics)


def _list_session_records(session: Session, session_id: uuid.UUID) -> list[QaRecord]:
    if hasattr(session, "execute"):
        result = session.execute(
            select(QaRecord)
            .where(QaRecord.session_id == session_id)
            .order_by(QaRecord.created_at.asc(), QaRecord.id.asc())
        )
        return list(result.scalars().all())

    added = getattr(session, "added", [])
    return [
        item
        for item in added
        if isinstance(item, QaRecord) and item.session_id == session_id
    ]


async def _rewrite_question(
    question: str,
    context: ConversationContext,
    dependencies: QaDependencies,
) -> StandaloneQuestionResult:
    if dependencies.context_rewriter is None:
        return StandaloneQuestionResult(
            standalone_question=question,
            is_follow_up=False,
            used_history=False,
            reason="rewriter_disabled",
        )
    return await dependencies.context_rewriter.rewrite(question, context)


def _rewrite_metadata(
    question: str,
    rewrite_result: StandaloneQuestionResult,
) -> dict[str, object]:
    return {
        "original_question": question,
        "standalone_question": rewrite_result.standalone_question,
        "is_follow_up": rewrite_result.is_follow_up,
        "used_history": rewrite_result.used_history,
        "rewrite_reason": rewrite_result.reason,
    }


def _skipped_rewrite_metadata(question: str, reason: str) -> dict[str, object]:
    return {
        "original_question": question,
        "standalone_question": question,
        "is_follow_up": False,
        "used_history": False,
        "rewrite_reason": reason,
    }


async def _finalize_response(
    session: Session,
    dependencies: QaDependencies,
    qa_session: QaSession,
    records: list[QaRecord],
    record: QaRecord,
    intent: str,
    references: list[QaReferenceSchema],
    trace_id: str,
    trace: QaTraceCollector,
    start: float,
    timings: dict[str, int],
    route: str,
    debug_context: QaDebugContext,
) -> QaAskResponse:
    step_start = time.perf_counter()
    await _maybe_update_summary(
        dependencies=dependencies,
        qa_session=qa_session,
        records=records,
        record=record,
    )
    _record_timing(timings, trace, "summary_update", step_start)

    trace.record_step(
        step_name="db_commit",
        duration_ms=0,
        metadata={"route": route},
    )
    persist_trace_steps(session=session, record_id=record.id, collector=trace)
    step_start = time.perf_counter()
    session.commit()
    timings["db_commit_ms"] = _elapsed_ms(step_start)

    timings["total_ms"] = _latency_ms(start)
    metadata = dict(record.decision_metadata or {})
    metadata["timings_ms"] = dict(timings)
    record.decision_metadata = metadata
    _log_timing(
        trace_id=trace_id,
        session_id=qa_session.id,
        route=route,
        timings=timings,
    )
    _log_debug(
        debug_context,
        "qa.request.finish",
        trace_id=trace_id,
        session_id=qa_session.id,
        route=route,
        answer_type=record.answer_type.value,
        intent=intent,
        answer=record.answer,
        confidence=record.confidence,
        references_count=len(references),
        total_ms=timings.get("total_ms"),
        timings_ms=timings,
    )
    return _response_from_record(record, intent, references)


async def _maybe_update_summary(
    dependencies: QaDependencies,
    qa_session: QaSession,
    records: list[QaRecord],
    record: QaRecord,
) -> None:
    if dependencies.session_summarizer is None:
        return
    try:
        updated = await dependencies.session_summarizer.update_if_needed(
            qa_session=qa_session,
            records=records,
        )
    except Exception:
        metadata = dict(record.decision_metadata or {})
        metadata["summary_update_error"] = True
        record.decision_metadata = metadata
        return
    metadata = dict(record.decision_metadata or {})
    metadata["summary_updated"] = updated
    record.decision_metadata = metadata


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
    visible_top_k: int,
    usage_note: str | None = None,
) -> list[QaReferenceSchema]:
    references: list[QaReferenceSchema] = []
    document_file_names = _document_file_names(session, evidence)
    for rank, item in enumerate(evidence, start=1):
        ref_metadata = {"heading_path": getattr(item, "heading_path", "") or ""}
        if usage_note is not None:
            ref_metadata["usage_note"] = usage_note
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
            ref_metadata=ref_metadata,
        )
        session.add(reference)
        document_id = _document_file_name_key(getattr(item, "document_id", None))
        references.append(
            _reference_schema(
                rank,
                item,
                visible=rank <= visible_top_k,
                document_file_name=document_file_names.get(document_id),
                usage_note=usage_note,
            )
        )
    return references


def _document_file_name_key(document_id: object) -> str | None:
    parsed = _uuid_or_none(document_id)
    return str(parsed) if parsed is not None else None


def _document_file_names(session: Session, evidence: list[object]) -> dict[str, str]:
    document_ids = {
        parsed
        for item in evidence
        if (parsed := _uuid_or_none(getattr(item, "document_id", None))) is not None
    }
    if not document_ids:
        return {}

    rows = session.execute(
        select(KbDocument.id, KbDocument.file_name, KbDocument.document_metadata).where(KbDocument.id.in_(document_ids))
    ).all()
    return {
        str(document_id): resolved_file_name
        for document_id, file_name, metadata in rows
        if (resolved_file_name := _document_file_name_from_row(file_name, metadata)) is not None
    }


def _document_file_name_from_row(file_name: str | None, metadata: dict | None) -> str | None:
    if file_name and file_name.strip():
        return file_name.strip()

    source_file_name = (metadata or {}).get("source_file_name")
    if isinstance(source_file_name, str) and source_file_name.strip():
        return source_file_name.strip()

    return None


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
        session_id=record.session_id,
        trace_id=record.trace_id or "",
        answer_type=record.answer_type.value,
        intent=intent,
        answer=record.answer or "",
        confidence=record.confidence,
        references=references,
        decision=dict(record.decision_metadata or {}),
    )


def _reference_schema(
    rank: int,
    item: object,
    visible: bool = True,
    document_file_name: str | None = None,
    usage_note: str | None = None,
) -> QaReferenceSchema:
    return QaReferenceSchema(
        rank=rank,
        segment_id=str(getattr(item, "segment_id", "") or "") or None,
        document_id=str(getattr(item, "document_id", "") or "") or None,
        document_file_name=document_file_name,
        heading_path=getattr(item, "heading_path", "") or "",
        excerpt=(getattr(item, "clean_text", "") or "")[:500],
        vector_score=getattr(item, "vector_score", None),
        keyword_score=getattr(item, "keyword_score", None),
        rrf_score=getattr(item, "rrf_score", None),
        rerank_score=getattr(item, "rerank_score", None),
        visible=visible,
        usage_note=usage_note,
    )


def _top_rerank_score(evidence: list[object]) -> float | None:
    if not evidence:
        return None
    score = getattr(evidence[0], "rerank_score", None)
    return float(score) if score is not None else None


def _latency_ms(start: float) -> int:
    return int((time.perf_counter() - start) * 1000)


def _elapsed_ms(start: float) -> int:
    return int((time.perf_counter() - start) * 1000)


def _record_timing(
    timings: dict[str, int],
    trace: QaTraceCollector,
    step_name: str,
    start: float,
) -> int:
    duration_ms = _elapsed_ms(start)
    timings[f"{step_name}_ms"] = duration_ms
    trace.record_step(step_name=step_name, duration_ms=duration_ms)
    return duration_ms


def _merge_timing_diagnostics(
    timings: dict[str, int],
    prefix: str,
    diagnostics: dict[str, object],
) -> None:
    for key, value in diagnostics.items():
        if key.endswith("_ms") and isinstance(value, int) and not isinstance(value, bool):
            timings[f"{prefix}_{key}"] = value


def _retrieval_diagnostics(retriever: Retriever) -> dict[str, object]:
    diagnostics = getattr(retriever, "last_diagnostics", None)
    return dict(diagnostics) if isinstance(diagnostics, dict) else {}


def _answer_diagnostics(answer_client: AnswerClient) -> dict[str, object]:
    diagnostics = getattr(answer_client, "last_diagnostics", None)
    return dict(diagnostics) if isinstance(diagnostics, dict) else {}


async def _emit_progress(
    dependencies: QaDependencies,
    stage: str,
    message: str,
    extra: dict[str, object] | None = None,
) -> None:
    if dependencies.progress_callback is None:
        return
    await dependencies.progress_callback(stage, message, extra)


def _evidence_ready_message(evidence_count: int, compression_reason: str) -> str:
    if evidence_count <= 0:
        return "知识库匹配度较低，正在判断是否可以可靠回答..."
    if compression_reason == "high_confidence_top2":
        return f"已找到 {evidence_count} 条高相关资料，正在组织答案..."
    if compression_reason == "medium_confidence_top3":
        return f"已找到 {evidence_count} 条相关资料，正在组织答案..."
    return f"已找到 {evidence_count} 条可参考资料，正在谨慎组织答案..."


def _evidence_chars(evidence: list[object]) -> int:
    return sum(len(getattr(item, "clean_text", "") or "") for item in evidence)


def _timings_snapshot(start: float, timings: dict[str, int]) -> dict[str, int]:
    snapshot = dict(timings)
    snapshot["total_ms"] = _latency_ms(start)
    return snapshot


def _log_timing(
    trace_id: str,
    session_id: uuid.UUID,
    route: str,
    timings: dict[str, int],
    error_reason: str | None = None,
) -> None:
    logger.info(
        "qa_timing trace_id=%s session_id=%s route=%s error_reason=%s timings_ms=%s",
        trace_id,
        session_id,
        route,
        error_reason,
        dict(timings),
    )


def _log_debug(
    context: QaDebugContext,
    event: str,
    **fields: object,
) -> None:
    log_qa_debug_event(
        logger=logger,
        enabled=context.enabled,
        event=event,
        preview_chars=context.preview_chars,
        evidence_preview_enabled=context.evidence_preview_enabled,
        **fields,
    )


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
    Intent.out_of_scope,
}
