from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import httpx

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import settings
from app.db.session import SessionLocal
from app.services.qa_dependencies import build_qa_dependencies
from app.services.qa_service import answer_question
from app.services.siliconflow import (
    SiliconFlowChatClient,
    SiliconFlowEmbeddingClient,
    SiliconFlowRerankClient,
)


async def main() -> None:
    question = " ".join(sys.argv[1:]).strip()
    if not question:
        raise SystemExit(
            "Usage: python scripts/ask_question.py <question> "
            "(from backend) or python backend/scripts/ask_question.py <question> "
            "(from project root)"
        )

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

        try:
            with SessionLocal() as session:
                response = await answer_question(
                    session=session,
                    question=question,
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
                )
        except httpx.TimeoutException as exc:
            raise SystemExit(
                "Model API request timed out. You can retry, check SiliconFlow "
                "service/network/proxy status, or increase MODEL_API_TIMEOUT_SECONDS "
                "in .env."
            ) from exc

    print(response.model_dump_json(indent=2))


if __name__ == "__main__":
    asyncio.run(main())
