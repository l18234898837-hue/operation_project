from __future__ import annotations

from collections.abc import AsyncIterator
import asyncio
from contextlib import suppress
import json
import logging
import time
from typing import Any

from sqlalchemy.orm import Session

from app.schemas.qa import QaAskResponse
from app.services.qa_debug_logging import log_qa_debug_event
from app.services.qa_service import QaDependencies, answer_question

logger = logging.getLogger(__name__)

STATUS_UNDERSTANDING = "understanding"
STATUS_REWRITING = "rewriting"
STATUS_RETRIEVING = "retrieving"
STATUS_GENERATING = "generating"
STATUS_CONTEXT = "context"
STATUS_EVIDENCE_READY = "evidence_ready"
STATUS_LOW_CONFIDENCE = "low_confidence"
STATUS_QUICK_REPLY = "quick_reply"
STATUS_DONE = "done"
STATUS_ERROR = "error"
QUEUE_DONE = "__done__"


def format_sse_event(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def stream_qa_events(
    session: Session,
    question: str,
    dependencies: QaDependencies,
    min_rerank_score: float,
    strong_rerank_score: float,
    reference_top_k: int,
    session_id=None,
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
) -> AsyncIterator[str]:
    start = time.perf_counter()
    first_delta_sent = False
    _log_stream_debug(
        enabled=qa_debug_log_enabled,
        event="qa.sse.start",
        preview_chars=qa_debug_question_preview_chars,
        evidence_preview_enabled=qa_debug_evidence_preview_enabled,
        session_id=session_id,
        question=question,
        question_length=len(question),
    )
    try:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        streaming_dependencies = _with_streaming_answer_client(dependencies, queue)
        answer_task = asyncio.create_task(
            answer_question(
                session=session,
                question=question,
                session_id=session_id,
                dependencies=streaming_dependencies,
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
                qa_debug_log_enabled=qa_debug_log_enabled,
                qa_debug_question_preview_chars=qa_debug_question_preview_chars,
                qa_debug_evidence_preview_enabled=qa_debug_evidence_preview_enabled,
            )
        )
        while True:
            if answer_task.done() and queue.empty():
                break

            get_task = asyncio.create_task(queue.get())
            done, _ = await asyncio.wait(
                {get_task, answer_task},
                return_when=asyncio.FIRST_COMPLETED,
            )
            if get_task not in done:
                get_task.cancel()
                with suppress(asyncio.CancelledError):
                    await get_task
                continue

            item = get_task.result()
            if item.get("event") == QUEUE_DONE:
                continue
            if item.get("event") == "status":
                yield format_sse_event(
                    "status",
                    {
                        "stage": item.get("stage"),
                        "message": item.get("message"),
                        **dict(item.get("extra") or {}),
                    },
                )
                continue
            chunk = str(item.get("text") or "")
            if not chunk:
                continue
            if not first_delta_sent:
                first_delta_sent = True
                _log_stream_debug(
                    enabled=qa_debug_log_enabled,
                    event="qa.sse.first_delta",
                    preview_chars=qa_debug_question_preview_chars,
                    evidence_preview_enabled=qa_debug_evidence_preview_enabled,
                    session_id=session_id,
                    first_delta_ms=_elapsed_ms(start),
                )
            yield format_sse_event("answer_delta", {"text": chunk})

        response = await answer_task
        _log_stream_debug(
            enabled=qa_debug_log_enabled,
            event="qa.sse.finish",
            preview_chars=qa_debug_question_preview_chars,
            evidence_preview_enabled=qa_debug_evidence_preview_enabled,
            trace_id=response.trace_id,
            session_id=response.session_id,
            route=response.decision.get("route"),
            answer_type=response.answer_type,
            answer=response.answer,
            references_count=len(response.references),
            total_ms=_elapsed_ms(start),
        )
        for event in _response_tail_events(response):
            yield event
    except Exception as exc:
        _log_stream_debug(
            enabled=qa_debug_log_enabled,
            event="qa.sse.error",
            preview_chars=qa_debug_question_preview_chars,
            evidence_preview_enabled=qa_debug_evidence_preview_enabled,
            session_id=session_id,
            error_type=type(exc).__name__,
            error=str(exc),
            total_ms=_elapsed_ms(start),
        )
        yield format_sse_event(
            "error",
            {"stage": STATUS_ERROR, "message": "问答服务处理异常", "error": str(exc)},
        )


async def stream_response_events(response: QaAskResponse) -> AsyncIterator[str]:
    for event in _response_events(response):
        yield event


def _response_events(response: QaAskResponse) -> list[str]:
    return [
        format_sse_event("answer_delta", {"text": response.answer}),
        *_response_tail_events(response),
    ]


def _response_tail_events(response: QaAskResponse) -> list[str]:
    return [
        format_sse_event(
            "references",
            {
                "references": [
                    reference.model_dump(mode="json")
                    for reference in response.references
                ]
            },
        ),
        format_sse_event("done", response.model_dump(mode="json")),
    ]


def _with_streaming_answer_client(
    dependencies: QaDependencies,
    queue: asyncio.Queue[dict[str, Any]],
) -> QaDependencies:
    return QaDependencies(
        understanding_client=dependencies.understanding_client,
        retriever=dependencies.retriever,
        answer_client=_StreamingAnswerClient(dependencies.answer_client, queue),
        context_rewriter=dependencies.context_rewriter,
        session_summarizer=dependencies.session_summarizer,
        progress_callback=_progress_callback(queue),
    )


def _progress_callback(queue: asyncio.Queue[dict[str, Any]]):
    async def _callback(
        stage: str,
        message: str,
        extra: dict[str, object] | None = None,
    ) -> None:
        await queue.put(
            {
                "event": "status",
                "stage": stage,
                "message": message,
                "extra": extra or {},
            }
        )

    return _callback


class _StreamingAnswerClient:
    def __init__(self, wrapped: object, queue: asyncio.Queue[dict[str, Any]]) -> None:
        self._wrapped = wrapped
        self._queue = queue

    @property
    def last_diagnostics(self) -> dict[str, object]:
        diagnostics = getattr(self._wrapped, "last_diagnostics", None)
        return diagnostics if isinstance(diagnostics, dict) else {}

    async def generate_rag(
        self,
        question: str,
        evidence: list[object],
        cautious: bool,
    ) -> str:
        stream_rag = getattr(self._wrapped, "stream_rag", None)
        if stream_rag is None:
            answer = await self._wrapped.generate_rag(question, evidence, cautious)
            await self._queue.put({"event": "answer_delta", "text": answer})
            await self._queue.put({"event": QUEUE_DONE})
            return answer

        parts: list[str] = []
        async for chunk in stream_rag(question, evidence, cautious):
            parts.append(chunk)
            await self._queue.put({"event": "answer_delta", "text": chunk})
        await self._queue.put({"event": QUEUE_DONE})
        return "".join(parts)

    async def generate_general(self, question: str, mode: str = "general") -> str:
        stream_general = getattr(self._wrapped, "stream_general", None)
        if stream_general is not None:
            parts: list[str] = []
            async for chunk in stream_general(question, mode=mode):
                parts.append(chunk)
                await self._queue.put({"event": "answer_delta", "text": chunk})
            await self._queue.put({"event": QUEUE_DONE})
            return "".join(parts)

        answer = await self._wrapped.generate_general(question, mode=mode)
        await self._queue.put({"event": "answer_delta", "text": answer})
        await self._queue.put({"event": QUEUE_DONE})
        return answer

    async def generate_low_confidence_rag(
        self,
        question: str,
        evidence: list[object],
        top_score: float | None,
    ) -> str:
        stream_low_confidence = getattr(self._wrapped, "stream_low_confidence_rag", None)
        if stream_low_confidence is not None:
            parts: list[str] = []
            async for chunk in stream_low_confidence(question, evidence, top_score):
                parts.append(chunk)
                await self._queue.put({"event": "answer_delta", "text": chunk})
            await self._queue.put({"event": QUEUE_DONE})
            return "".join(parts)

        answer = await self._wrapped.generate_low_confidence_rag(
            question,
            evidence,
            top_score,
        )
        await self._queue.put({"event": "answer_delta", "text": answer})
        await self._queue.put({"event": QUEUE_DONE})
        return answer


def _log_stream_debug(
    enabled: bool,
    event: str,
    preview_chars: int,
    evidence_preview_enabled: bool,
    **fields: object,
) -> None:
    log_qa_debug_event(
        logger=logger,
        enabled=enabled,
        event=event,
        preview_chars=preview_chars,
        evidence_preview_enabled=evidence_preview_enabled,
        **fields,
    )


def _elapsed_ms(start: float) -> int:
    return int((time.perf_counter() - start) * 1000)
