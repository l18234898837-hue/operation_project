from __future__ import annotations

import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.rag import (
    DocumentStatus,
    KbDocument,
    KbDocumentSegment,
    ParseTask,
    ParseTaskStatus,
)
from app.schemas.documents import DocumentItemSchema
from app.services.document_conversion import (
    MarkdownConverter,
    TEXT_EXTENSIONS,
    convert_document_to_markdown,
)
from app.services.document_management import map_document_item
from app.services.ingest import EmbeddingClient
from app.services.keyword_index import build_keyword_text
from app.services.markdown_chunker import chunk_markdown


SUPPORTED_EXTENSIONS = TEXT_EXTENSIONS | {".pdf", ".doc", ".docx", ".xls", ".xlsx"}


async def retry_document_parse(
    session: Session,
    document_id: uuid.UUID,
    embedding_client: EmbeddingClient,
    embedding_model: str,
    markdown_storage_dir: Path,
    converter: MarkdownConverter | None = None,
) -> DocumentItemSchema | None:
    document = session.get(KbDocument, document_id)
    if document is None:
        return None

    extension = _document_extension(document)
    if extension not in SUPPORTED_EXTENSIONS:
        return _record_failed_placeholder(
            session,
            document,
            "Unsupported file type for retry parsing",
            _parser_name_for_extension(extension),
        )

    source_path = Path(document.source_path or "")
    if not document.source_path or not source_path.is_file():
        return _record_failed_placeholder(
            session,
            document,
            "Source file does not exist, cannot retry parsing",
            _parser_name_for_extension(extension),
        )

    started = time.perf_counter()
    parser_name = _parser_name_for_extension(extension)
    markdown_path = _markdown_path_for_retry(document, source_path, markdown_storage_dir)
    task = ParseTask(
        document_id=document.id,
        status=ParseTaskStatus.running,
        parser_name=parser_name,
        retry_count=_next_retry_count(session, document.id),
        error_message=None,
        started_at=datetime.now(UTC),
    )
    session.add(task)
    rebuild_started = False

    try:
        convert_document_to_markdown(source_path, markdown_path, converter=converter)
        content = markdown_path.read_text(encoding="utf-8")
        chunks = chunk_markdown(content, source_title=document.title)
        if not chunks:
            raise ValueError(f"No chunks produced for {source_path.name}")

        embeddings = await embedding_client.embed([chunk.indexed_text for chunk in chunks])
        if len(embeddings) != len(chunks):
            raise ValueError(
                f"Expected {len(chunks)} embeddings, got {len(embeddings)}"
            )

        session.execute(
            delete(KbDocumentSegment).where(KbDocumentSegment.document_id == document.id)
        )
        rebuild_started = True
        for chunk_index, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            session.add(
                KbDocumentSegment(
                    document_id=document.id,
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

        document.status = DocumentStatus.ready
        document.enabled = True
        document.segment_count = len(chunks)
        document.error_message = None
        document.markdown_path = str(markdown_path)
        _set_metadata_progress(document, 100)
        task.status = ParseTaskStatus.success
        task.error_message = None
        task.finished_at = datetime.now(UTC)
        task.duration_ms = _duration_ms(started)
        session.commit()
    except Exception as exc:
        error_message = str(exc)
        if rebuild_started:
            _rollback_if_available(session)
            return _record_failed_retry(
                session,
                document,
                error_message,
                started,
                parser_name,
            )
        _mark_failed(document, task, error_message, started)
        session.commit()

    session.refresh(document)
    return map_document_item(document)


def _record_failed_retry(
    session: Session,
    document: KbDocument,
    error_message: str,
    started: float,
    parser_name: str,
) -> DocumentItemSchema:
    task = ParseTask(
        document_id=document.id,
        status=ParseTaskStatus.failed,
        parser_name=parser_name,
        retry_count=_next_retry_count(session, document.id),
        error_message=error_message,
        started_at=datetime.now(UTC),
    )
    session.add(task)
    _mark_failed(document, task, error_message, started)
    session.commit()
    session.refresh(document)
    return map_document_item(document)


def _mark_failed(
    document: KbDocument,
    task: ParseTask,
    error_message: str,
    started: float,
) -> None:
    document.status = DocumentStatus.failed
    document.enabled = False
    document.error_message = error_message
    _set_metadata_progress(document, None)
    task.status = ParseTaskStatus.failed
    task.error_message = error_message
    task.finished_at = datetime.now(UTC)
    task.duration_ms = _duration_ms(started)


def _rollback_if_available(session: Session) -> None:
    rollback = getattr(session, "rollback", None)
    if rollback is not None:
        rollback()


def _record_failed_placeholder(
    session: Session,
    document: KbDocument,
    reason: str,
    parser_name: str,
) -> DocumentItemSchema:
    started = time.perf_counter()
    task = ParseTask(
        document_id=document.id,
        status=ParseTaskStatus.failed,
        parser_name=parser_name,
        retry_count=_next_retry_count(session, document.id),
        error_message=reason,
        started_at=datetime.now(UTC),
        finished_at=datetime.now(UTC),
        duration_ms=_duration_ms(started),
    )
    document.status = DocumentStatus.failed
    document.enabled = False
    document.error_message = reason
    _set_metadata_progress(document, None)
    session.add(task)
    session.commit()
    session.refresh(document)
    return map_document_item(document)


def _document_extension(document: KbDocument) -> str:
    for value in (document.source_path, document.file_name):
        if value:
            suffix = Path(value).suffix.lower()
            if suffix:
                return suffix

    file_type = (document.file_type or "").strip().lower()
    if not file_type:
        return ""
    if file_type.startswith("."):
        return file_type
    aliases = {
        "markdown": ".md",
        "md": ".md",
        "txt": ".txt",
        "text": ".txt",
        "pdf": ".pdf",
        "word": ".docx",
        "doc": ".doc",
        "docx": ".docx",
        "excel": ".xlsx",
        "xls": ".xls",
        "xlsx": ".xlsx",
    }
    return aliases.get(file_type, f".{file_type}")


def _parser_name_for_extension(extension: str) -> str:
    return "manual-retry-text" if extension in TEXT_EXTENSIONS else "markitdown-retry"


def _markdown_path_for_retry(
    document: KbDocument,
    source_path: Path,
    markdown_storage_dir: Path,
) -> Path:
    if document.markdown_path:
        return Path(document.markdown_path)
    qualifier = document.file_sha256 or str(document.id)
    return markdown_storage_dir / f"{qualifier}_{source_path.stem}.md"


def _next_retry_count(session: Session, document_id: uuid.UUID) -> int:
    retry_counts = list(
        session.execute(
            select(ParseTask.retry_count).where(ParseTask.document_id == document_id)
        ).scalars()
    )
    return max([0, *retry_counts]) + 1


def _set_metadata_progress(document: KbDocument, progress: int | None) -> None:
    metadata = (
        dict(document.document_metadata)
        if isinstance(document.document_metadata, dict)
        else {}
    )
    if progress is None:
        metadata.pop("progress", None)
    else:
        metadata["progress"] = progress
    document.document_metadata = metadata


def _duration_ms(started: float) -> int:
    return max(0, int((time.perf_counter() - started) * 1000))
