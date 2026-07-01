from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.rag import (
    DocumentStatus,
    KbDocument,
    KbDocumentSegment,
    ParseTask,
)
from app.schemas.documents import (
    DocumentDetailSchema,
    DocumentItemSchema,
    ParseTaskSummarySchema,
    SegmentPreviewSchema,
)


KNOWN_CATEGORIES = {
    "inverter",
    "inspection",
    "grid-quality",
    "modules",
    "manual",
    "cases",
    "standards",
    "uncategorized",
}


def list_document_items(session: Session) -> list[DocumentItemSchema]:
    documents = (
        session.execute(select(KbDocument).order_by(KbDocument.updated_at.desc()))
        .scalars()
        .all()
    )
    return [map_document_item(document) for document in documents]


def set_document_enabled(
    session: Session,
    document_id: uuid.UUID,
    enabled: bool,
) -> DocumentItemSchema | None:
    document = session.get(KbDocument, document_id)
    if document is None:
        return None

    document.enabled = enabled
    session.commit()
    session.refresh(document)
    return map_document_item(document)


def get_document_detail(
    session: Session,
    document_id: uuid.UUID,
) -> DocumentDetailSchema | None:
    document = session.get(KbDocument, document_id)
    if document is None:
        return None

    tasks = (
        session.execute(
            select(ParseTask)
            .where(ParseTask.document_id == document_id)
            .order_by(
                ParseTask.started_at.desc().nullslast(),
                ParseTask.created_at.desc(),
            )
            .limit(5)
        )
        .scalars()
        .all()
    )
    segments = (
        session.execute(
            select(KbDocumentSegment)
            .where(KbDocumentSegment.document_id == document_id)
            .order_by(KbDocumentSegment.chunk_index.asc())
            .limit(3)
        )
        .scalars()
        .all()
    )
    recent_tasks = [_map_parse_task_summary(task) for task in tasks]

    return DocumentDetailSchema(
        item=map_document_item(document),
        sourcePath=document.source_path,
        markdownPath=document.markdown_path,
        fileSha256=document.file_sha256,
        segmentCount=document.segment_count,
        metadata=_metadata(document.document_metadata),
        latestTask=recent_tasks[0] if recent_tasks else None,
        recentTasks=recent_tasks,
        segmentPreview=[_map_segment_preview(segment) for segment in segments],
    )


def map_document_item(document: KbDocument) -> DocumentItemSchema:
    metadata = _metadata(document.document_metadata)
    source_file_name = metadata.get("source_file_name")
    name = document.file_name or (
        source_file_name if isinstance(source_file_name, str) and source_file_name else None
    ) or document.title
    status = document.status
    parse_status = DocumentStatus.ready if status == DocumentStatus.disabled else status

    return DocumentItemSchema(
        id=document.id,
        name=name,
        type=_document_type(document.file_type, name),
        category=_category(metadata.get("category")),
        parseStatus=parse_status.value,
        enableStatus="enabled" if document.enabled else "disabled",
        updatedAt=document.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
        failureReason=document.error_message,
        progress=_progress(status, metadata),
    )


def _document_type(file_type: str | None, name: str) -> str:
    source = (file_type or Path(name).suffix.lstrip(".")).lower()
    if source == "pdf":
        return "PDF"
    if source in {"doc", "docx", "word"}:
        return "Word"
    if source in {"xls", "xlsx", "excel"}:
        return "Excel"
    if source in {"md", "markdown"}:
        return "Markdown"
    return "TXT"


def _metadata(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    return {}


def _category(value: Any) -> str:
    if isinstance(value, str) and value in KNOWN_CATEGORIES:
        return value
    return "uncategorized"


def _progress(status: DocumentStatus, metadata: dict[str, Any]) -> int | None:
    if status == DocumentStatus.uploaded:
        return 0
    if status == DocumentStatus.processing:
        value = metadata.get("progress")
        if isinstance(value, int) and 0 <= value <= 100:
            return value
        return 15
    if status in {DocumentStatus.ready, DocumentStatus.disabled}:
        return 100
    return None


def _map_parse_task_summary(task: ParseTask) -> ParseTaskSummarySchema:
    return ParseTaskSummarySchema(
        id=task.id,
        status=task.status.value,
        parserName=task.parser_name,
        retryCount=task.retry_count,
        durationMs=task.duration_ms,
        errorMessage=task.error_message,
        startedAt=_format_datetime(task.started_at),
        finishedAt=_format_datetime(task.finished_at),
    )


def _map_segment_preview(segment: KbDocumentSegment) -> SegmentPreviewSchema:
    return SegmentPreviewSchema(
        id=segment.id,
        chunkIndex=segment.chunk_index,
        headingPath=segment.heading_path,
        sectionTitle=segment.section_title,
        charCount=segment.char_count,
        hasEmbedding=segment.embedding is not None,
    )


def _format_datetime(value: Any) -> str | None:
    if value is None:
        return None
    return value.strftime("%Y-%m-%d %H:%M:%S")
