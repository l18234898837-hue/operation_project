from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.rag import DocumentStatus, KbDocument, ParseTask, ParseTaskStatus
from app.schemas.documents import DocumentItemSchema


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


def retry_document_parse(
    session: Session,
    document_id: uuid.UUID,
) -> DocumentItemSchema | None:
    document = session.get(KbDocument, document_id)
    if document is None:
        return None

    metadata = _metadata(document.document_metadata)
    if (
        document.status == DocumentStatus.processing
        and metadata.get("retry_placeholder") is True
    ):
        return map_document_item(document)

    metadata["progress"] = 15
    metadata["retry_placeholder"] = True

    document.status = DocumentStatus.processing
    document.enabled = False
    document.error_message = None
    document.document_metadata = metadata
    session.add(
        ParseTask(
            document_id=document.id,
            status=ParseTaskStatus.pending,
            parser_name="manual-retry-placeholder",
            retry_count=_next_retry_count(session, document.id),
            error_message=None,
            task_metadata={
                "placeholder": True,
                "message": "Retry requested from document management page.",
            },
        )
    )
    session.commit()
    session.refresh(document)
    return map_document_item(document)


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


def _next_retry_count(session: Session, document_id: uuid.UUID) -> int:
    retry_counts = list(
        session.execute(
            select(ParseTask.retry_count).where(ParseTask.document_id == document_id)
        ).scalars()
    )
    return max([0, *retry_counts]) + 1
