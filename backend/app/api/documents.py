from __future__ import annotations

from collections.abc import Iterator
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.schemas.documents import DocumentEnableRequest, DocumentItemSchema
from app.services.document_management import (
    list_document_items,
    retry_document_parse,
    set_document_enabled,
)

router = APIRouter(prefix="/documents", tags=["documents"])


def get_db_session() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session


class DocumentManager:
    def __init__(self, session: Session):
        self._session = session

    def list_documents(self) -> list[DocumentItemSchema]:
        return list_document_items(self._session)

    def set_enabled(
        self,
        document_id: uuid.UUID,
        enabled: bool,
    ) -> DocumentItemSchema | None:
        return set_document_enabled(self._session, document_id, enabled)

    def retry_parse(self, document_id: uuid.UUID) -> DocumentItemSchema | None:
        return retry_document_parse(self._session, document_id)


def get_document_manager(
    session: Session = Depends(get_db_session),
) -> DocumentManager:
    return DocumentManager(session)


@router.get("", response_model=list[DocumentItemSchema])
async def list_documents(
    manager: DocumentManager = Depends(get_document_manager),
) -> list[DocumentItemSchema]:
    return manager.list_documents()


@router.patch("/{document_id}/enabled", response_model=DocumentItemSchema)
async def update_document_enabled(
    document_id: uuid.UUID,
    request: DocumentEnableRequest,
    manager: DocumentManager = Depends(get_document_manager),
) -> DocumentItemSchema:
    document = manager.set_enabled(document_id, request.enabled)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return document


@router.post("/{document_id}/retry", response_model=DocumentItemSchema)
async def retry_document(
    document_id: uuid.UUID,
    manager: DocumentManager = Depends(get_document_manager),
) -> DocumentItemSchema:
    document = manager.retry_parse(document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return document
