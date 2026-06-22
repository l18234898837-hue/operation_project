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
from app.services.retrieval import retrieve_evidence
from app.services.siliconflow import SiliconFlowEmbeddingClient, SiliconFlowRerankClient


async def main() -> None:
    query = " ".join(sys.argv[1:]).strip()
    if not query:
        raise SystemExit("Usage: python backend/scripts/query_knowledge_base.py <query>")

    async with (
        httpx.AsyncClient(base_url=settings.embedding_base_url, timeout=60) as embedding_http,
        httpx.AsyncClient(base_url=settings.rerank_base_url, timeout=60) as rerank_http,
    ):
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
            evidence = await retrieve_evidence(
                session=session,
                query=query,
                embedding_client=embedding_client,
                rerank_client=rerank_client,
                vector_top_k=settings.retrieval_vector_top_k,
                keyword_top_k=settings.retrieval_keyword_top_k,
                rrf_top_k=settings.retrieval_rrf_top_k,
                final_top_k=settings.retrieval_final_top_k,
                rrf_k=settings.retrieval_rrf_k,
            )

    for index, chunk in enumerate(evidence, start=1):
        excerpt = chunk.clean_text[:300].replace("\n", " ")
        print(f"[{index}] {chunk.heading_path}")
        print(f"segment_id={chunk.segment_id} document_id={chunk.document_id}")
        print(
            "vector_score="
            f"{chunk.vector_score} keyword_score={chunk.keyword_score} "
            f"rrf_score={chunk.rrf_score} rerank_score={chunk.rerank_score}"
        )
        print(excerpt)
        print()


if __name__ == "__main__":
    asyncio.run(main())
