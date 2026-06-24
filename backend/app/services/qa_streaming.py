from __future__ import annotations

from collections.abc import AsyncIterator
import asyncio
import json
from typing import Any

from sqlalchemy.orm import Session

from app.schemas.qa import QaAskResponse
from app.services.qa_service import QaDependencies, answer_question

STATUS_UNDERSTANDING = "understanding"
STATUS_REWRITING = "rewriting"
STATUS_RETRIEVING = "retrieving"
STATUS_GENERATING = "generating"
STATUS_DONE = "done"
STATUS_ERROR = "error"


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
) -> AsyncIterator[str]:
    try:
        yield format_sse_event(
            "status",
            {"stage": STATUS_REWRITING, "message": "正在理解追问上下文"},
        )
        yield format_sse_event(
            "status",
            {"stage": STATUS_UNDERSTANDING, "message": "正在识别问题意图"},
        )
        yield format_sse_event(
            "status",
            {"stage": STATUS_RETRIEVING, "message": "正在检索知识库"},
        )
        yield format_sse_event(
            "status",
            {"stage": STATUS_GENERATING, "message": "正在生成答案"},
        )
        queue: asyncio.Queue[str | None] = asyncio.Queue()
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
            )
        )
        while True:
            if answer_task.done() and queue.empty():
                break
            try:
                chunk = await asyncio.wait_for(queue.get(), timeout=0.1)
            except asyncio.TimeoutError:
                continue
            if chunk is None:
                continue
            yield format_sse_event("answer_delta", {"text": chunk})

        response = await answer_task
        for event in _response_tail_events(response):
            yield event
    except Exception as exc:
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
    queue: asyncio.Queue[str | None],
) -> QaDependencies:
    return QaDependencies(
        understanding_client=dependencies.understanding_client,
        retriever=dependencies.retriever,
        answer_client=_StreamingAnswerClient(dependencies.answer_client, queue),
        context_rewriter=dependencies.context_rewriter,
        session_summarizer=dependencies.session_summarizer,
    )


class _StreamingAnswerClient:
    def __init__(self, wrapped: object, queue: asyncio.Queue[str | None]) -> None:
        self._wrapped = wrapped
        self._queue = queue

    async def generate_rag(
        self,
        question: str,
        evidence: list[object],
        cautious: bool,
    ) -> str:
        stream_rag = getattr(self._wrapped, "stream_rag", None)
        if stream_rag is None:
            answer = await self._wrapped.generate_rag(question, evidence, cautious)
            await self._queue.put(answer)
            await self._queue.put(None)
            return answer

        parts: list[str] = []
        async for chunk in stream_rag(question, evidence, cautious):
            parts.append(chunk)
            await self._queue.put(chunk)
        await self._queue.put(None)
        return "".join(parts)

    async def generate_general(self, question: str) -> str:
        answer = await self._wrapped.generate_general(question)
        await self._queue.put(answer)
        await self._queue.put(None)
        return answer
