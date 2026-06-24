from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
import httpx

from app.core.config import settings
from app.db.session import SessionLocal
from app.schemas.qa import QaAskRequest, QaAskResponse
from app.services.qa_dependencies import build_qa_dependencies
from app.services.qa_service import answer_question
from app.services.qa_streaming import stream_qa_events
from app.services.siliconflow import (
    SiliconFlowChatClient,
    SiliconFlowEmbeddingClient,
    SiliconFlowRerankClient,
)

router = APIRouter(prefix="/qa", tags=["qa"])
QaAnswerer = Callable[[QaAskRequest], Awaitable[QaAskResponse]]
QaStreamer = Callable[[QaAskRequest], AsyncIterator[str]]


def get_qa_answerer() -> QaAnswerer:
    async def _answer(request: QaAskRequest) -> QaAskResponse:
        timeout = httpx.Timeout(settings.model_api_timeout_seconds)
        async with (
            httpx.AsyncClient(base_url=settings.llm_base_url, timeout=timeout) as llm_http,
            httpx.AsyncClient(
                base_url=settings.embedding_base_url,
                timeout=timeout,
            ) as embedding_http,
            httpx.AsyncClient(
                base_url=settings.rerank_base_url,
                timeout=timeout,
            ) as rerank_http,
        ):
            intent_chat_client = SiliconFlowChatClient(
                client=llm_http,
                api_key=settings.llm_api_key,
                model=settings.qa_intent_model,
            )
            answer_chat_client = SiliconFlowChatClient(
                client=llm_http,
                api_key=settings.llm_api_key,
                model=settings.qa_chat_model,
            )
            embedding_client = SiliconFlowEmbeddingClient(
                client=embedding_http,
                api_key=settings.embedding_api_key,
                model=settings.embedding_model,
                dimension=settings.embedding_dimension,
            )
            rerank_client = (
                SiliconFlowRerankClient(
                    client=rerank_http,
                    api_key=settings.rerank_api_key,
                    model=settings.rerank_model,
                )
                if settings.rerank_enabled
                else None
            )
            with SessionLocal() as session:
                return await answer_question(
                    session=session,
                    question=request.question,
                    session_id=request.session_id,
                    dependencies=build_qa_dependencies(
                        session=session,
                        intent_chat_client=intent_chat_client,
                        answer_chat_client=answer_chat_client,
                        embedding_client=embedding_client,
                        rerank_client=rerank_client,
                    ),
                    min_rerank_score=settings.qa_rerank_min_score,
                    strong_rerank_score=settings.qa_rerank_strong_score,
                    reference_top_k=settings.qa_reference_top_k,
                    history_turns=settings.conversation_history_turns,
                    context_max_chars=settings.conversation_context_max_chars,
                    answer_excerpt_chars=settings.conversation_answer_excerpt_chars,
                    qa_evidence_min_score=settings.qa_evidence_min_score,
                    qa_reference_min_score=settings.qa_reference_min_score,
                    qa_reference_visible_top_k=settings.qa_reference_visible_top_k,
                    qa_reference_max_top_k=settings.qa_reference_max_top_k,
                )

    return _answer


def get_qa_streamer() -> QaStreamer:
    async def _stream(request: QaAskRequest) -> AsyncIterator[str]:
        timeout = httpx.Timeout(settings.model_api_timeout_seconds)
        async with (
            httpx.AsyncClient(base_url=settings.llm_base_url, timeout=timeout) as llm_http,
            httpx.AsyncClient(
                base_url=settings.embedding_base_url,
                timeout=timeout,
            ) as embedding_http,
            httpx.AsyncClient(
                base_url=settings.rerank_base_url,
                timeout=timeout,
            ) as rerank_http,
        ):
            intent_chat_client = SiliconFlowChatClient(
                client=llm_http,
                api_key=settings.llm_api_key,
                model=settings.qa_intent_model,
            )
            answer_chat_client = SiliconFlowChatClient(
                client=llm_http,
                api_key=settings.llm_api_key,
                model=settings.qa_chat_model,
            )
            embedding_client = SiliconFlowEmbeddingClient(
                client=embedding_http,
                api_key=settings.embedding_api_key,
                model=settings.embedding_model,
                dimension=settings.embedding_dimension,
            )
            rerank_client = (
                SiliconFlowRerankClient(
                    client=rerank_http,
                    api_key=settings.rerank_api_key,
                    model=settings.rerank_model,
                )
                if settings.rerank_enabled
                else None
            )
            with SessionLocal() as session:
                async for event in stream_qa_events(
                    session=session,
                    question=request.question,
                    session_id=request.session_id,
                    dependencies=build_qa_dependencies(
                        session=session,
                        intent_chat_client=intent_chat_client,
                        answer_chat_client=answer_chat_client,
                        embedding_client=embedding_client,
                        rerank_client=rerank_client,
                    ),
                    min_rerank_score=settings.qa_rerank_min_score,
                    strong_rerank_score=settings.qa_rerank_strong_score,
                    reference_top_k=settings.qa_reference_top_k,
                    history_turns=settings.conversation_history_turns,
                    context_max_chars=settings.conversation_context_max_chars,
                    answer_excerpt_chars=settings.conversation_answer_excerpt_chars,
                    qa_evidence_min_score=settings.qa_evidence_min_score,
                    qa_reference_min_score=settings.qa_reference_min_score,
                    qa_reference_visible_top_k=settings.qa_reference_visible_top_k,
                    qa_reference_max_top_k=settings.qa_reference_max_top_k,
                ):
                    yield event

    return _stream


@router.post("/ask", response_model=QaAskResponse)
async def ask_question(
    request: QaAskRequest,
    answerer: QaAnswerer = Depends(get_qa_answerer),
) -> QaAskResponse:
    return await answerer(request)


@router.post("/ask/stream")
async def ask_question_stream(
    request: QaAskRequest,
    streamer: QaStreamer = Depends(get_qa_streamer),
) -> StreamingResponse:
    return StreamingResponse(
        streamer(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
