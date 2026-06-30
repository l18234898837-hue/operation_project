from __future__ import annotations

from collections.abc import Iterator
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse
import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal
from app.schemas.documents import (
    DocumentEnableRequest,
    DocumentItemSchema,
    DocumentUploadErrorSchema,
)
from app.services.document_management import (
    list_document_items,
    retry_document_parse,
    set_document_enabled,
)
from app.services.document_uploads import UploadedFileData, upload_document_file
from app.services.siliconflow import SiliconFlowEmbeddingClient

router = APIRouter(prefix="/documents", tags=["documents"])
UPLOAD_READ_CHUNK_SIZE = 1024 * 1024


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


class DocumentUploader:
    def __init__(self, session: Session):
        self._session = session

    async def upload(self, file: UploadFile) -> DocumentItemSchema:
        content = await self._read_capped(file, settings.upload_max_bytes)
        async with httpx.AsyncClient(
            base_url=settings.embedding_base_url,
            timeout=httpx.Timeout(settings.model_api_timeout_seconds),
        ) as client:
            embedding_client = SiliconFlowEmbeddingClient(
                client=client,
                api_key=settings.embedding_api_key,
                model=settings.embedding_model,
                dimension=settings.embedding_dimension,
            )
            return await upload_document_file(
                session=self._session,
                file_data=UploadedFileData(
                    filename=file.filename or "",
                    content=content,
                ),
                upload_dir=settings.upload_storage_dir,
                max_bytes=settings.upload_max_bytes,
                embedding_client=embedding_client,
                embedding_model=settings.embedding_model,
            )

    async def _read_capped(self, file: UploadFile, max_bytes: int) -> bytes:
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = await file.read(UPLOAD_READ_CHUNK_SIZE)
            if not chunk:
                return b"".join(chunks)
            total += len(chunk)
            if total > max_bytes:
                raise ValueError("文件超过大小限制")
            chunks.append(chunk)


def get_document_manager(
    session: Session = Depends(get_db_session),
) -> DocumentManager:
    return DocumentManager(session)


def get_document_uploader(
    session: Session = Depends(get_db_session),
) -> DocumentUploader:
    return DocumentUploader(session)


@router.get("", response_model=list[DocumentItemSchema])
async def list_documents(
    manager: DocumentManager = Depends(get_document_manager),
) -> list[DocumentItemSchema]:
    return manager.list_documents()


@router.post(
    "/upload",
    response_model=DocumentItemSchema,
    responses={400: {"model": DocumentUploadErrorSchema}},
)
async def upload_document(
    file: UploadFile = File(...),
    uploader: DocumentUploader = Depends(get_document_uploader),
) -> DocumentItemSchema | JSONResponse:
    try:
        return await uploader.upload(file)
    except ValueError as exc:
        return JSONResponse(status_code=400, content={"message": str(exc)})


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
