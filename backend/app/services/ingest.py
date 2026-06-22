from __future__ import annotations

import hashlib
import re
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.rag import (
    DocumentStatus,
    KbDocument,
    KbDocumentSegment,
    ParseTask,
    ParseTaskStatus,
)
from app.services.keyword_index import build_keyword_text
from app.services.markdown_chunker import chunk_markdown


@dataclass(frozen=True)
class MarkdownDocument:
    path: Path
    title: str
    content: str
    file_sha256: str


class EmbeddingClient(Protocol):
    async def embed(self, texts: list[str]) -> list[list[float]]:
        ...


_NUMERIC_PREFIX_RE = re.compile(r"^\d+[\s_.-]*")


def load_markdown_documents(directory: Path) -> list[MarkdownDocument]:
    documents: list[MarkdownDocument] = []

    for path in sorted(directory.glob("*.md")):
        if not path.is_file():
            continue
        content_bytes = path.read_bytes()
        documents.append(
            MarkdownDocument(
                path=path,
                title=_title_from_path(path),
                content=content_bytes.decode("utf-8"),
                file_sha256=hashlib.sha256(content_bytes).hexdigest(),
            )
        )

    return documents


async def import_markdown_document(
    session: Session,
    document: MarkdownDocument,
    embedding_client: EmbeddingClient,
    embedding_model: str,
) -> uuid.UUID:
    started = time.perf_counter()
    kb_document: KbDocument | None = None
    task: ParseTask | None = None
    can_persist_failure = False

    try:
        existing = session.execute(
            select(KbDocument).where(KbDocument.file_sha256 == document.file_sha256)
        ).scalar_one_or_none()
        if existing is not None:
            return existing.id

        kb_document = KbDocument(
            title=document.title,
            source_path=str(document.path),
            file_sha256=document.file_sha256,
            file_type="markdown",
            status=DocumentStatus.processing,
            enabled=True,
            error_message=None,
            document_metadata={"source_file_name": document.path.name},
        )
        session.add(kb_document)
        session.flush()

        task = ParseTask(
            document_id=kb_document.id,
            status=ParseTaskStatus.running,
            retry_count=0,
            error_message=None,
            started_at=datetime.now(UTC),
        )
        session.add(task)
        session.flush()
        can_persist_failure = True

        chunks = chunk_markdown(document.content, source_title=document.title)
        if not chunks:
            raise ValueError(f"No chunks produced for {document.path.name}")

        embeddings = await embedding_client.embed([chunk.indexed_text for chunk in chunks])
        if len(embeddings) != len(chunks):
            raise ValueError(
                f"Expected {len(chunks)} embeddings, got {len(embeddings)}"
            )

        for chunk_index, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            session.add(
                KbDocumentSegment(
                    document_id=kb_document.id,
                    chunk_index=chunk_index,
                    heading_path=chunk.heading_path,
                    section_title=chunk.section_title,
                    raw_text=chunk.raw_text,
                    clean_text=chunk.clean_text,
                    indexed_text=chunk.indexed_text,
                    keyword_text=build_keyword_text(chunk.indexed_text),
                    token_count=None,
                    char_count=chunk.char_count,
                    embedding_model=embedding_model,
                    embedding=embedding,
                    segment_metadata=chunk.metadata,
                )
            )

        kb_document.status = DocumentStatus.ready
        kb_document.segment_count = len(chunks)
        kb_document.error_message = None
        task.status = ParseTaskStatus.success
        task.error_message = None
        task.finished_at = datetime.now(UTC)
        task.duration_ms = _duration_ms(started)
        session.commit()
        return kb_document.id
    except Exception as exc:
        if not can_persist_failure or kb_document is None or task is None:
            _rollback_if_available(session)
            raise
        _mark_failed(
            session=session,
            kb_document=kb_document,
            task=task,
            error_message=str(exc),
            started=started,
        )
        raise


def _title_from_path(path: Path) -> str:
    return _NUMERIC_PREFIX_RE.sub("", path.stem).strip()


def _duration_ms(started: float) -> int:
    return max(0, int((time.perf_counter() - started) * 1000))


def _mark_failed(
    session: Session,
    kb_document: KbDocument,
    task: ParseTask,
    error_message: str,
    started: float,
) -> None:
    kb_document.status = DocumentStatus.failed
    kb_document.error_message = error_message
    task.status = ParseTaskStatus.failed
    task.error_message = error_message
    task.finished_at = datetime.now(UTC)
    task.duration_ms = _duration_ms(started)
    try:
        session.commit()
    except Exception:
        _rollback_if_available(session)


def _rollback_if_available(session: Session) -> None:
    rollback = getattr(session, "rollback", None)
    if rollback is not None:
        rollback()
