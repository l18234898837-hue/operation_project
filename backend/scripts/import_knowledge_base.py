from __future__ import annotations

import asyncio
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import httpx

from app.core.config import PROJECT_ROOT, settings
from app.db.session import SessionLocal
from app.services.ingest import import_markdown_document, load_markdown_documents
from app.services.siliconflow import SiliconFlowEmbeddingClient


async def main() -> None:
    source_dir = PROJECT_ROOT / "data" / "knowledge_base" / "markdown"
    documents = load_markdown_documents(source_dir)

    async with httpx.AsyncClient(
        base_url=settings.embedding_base_url,
        timeout=60,
    ) as http_client:
        embedding_client = SiliconFlowEmbeddingClient(
            client=http_client,
            api_key=settings.embedding_api_key,
            model=settings.embedding_model,
            dimension=settings.embedding_dimension,
        )

        with SessionLocal() as session:
            for document in documents:
                document_id = await import_markdown_document(
                    session=session,
                    document=document,
                    embedding_client=embedding_client,
                    embedding_model=settings.embedding_model,
                )
                print(f"imported {Path(document.path).name} -> {document_id}")


if __name__ == "__main__":
    asyncio.run(main())
