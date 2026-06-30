from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePath

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.rag import DocumentStatus, KbDocument, ParseTask, ParseTaskStatus
from app.schemas.documents import DocumentItemSchema, DocumentTypeLiteral
from app.services.document_management import map_document_item
from app.services.ingest import (
    EmbeddingClient,
    MarkdownDocument,
    import_markdown_document_with_result,
)


SUPPORTED_TEXT_EXTENSIONS = {".md", ".markdown", ".txt"}
UNSUPPORTED_RECORDED_EXTENSIONS = {".pdf", ".doc", ".docx", ".xls", ".xlsx"}
ALLOWED_EXTENSIONS = SUPPORTED_TEXT_EXTENSIONS | UNSUPPORTED_RECORDED_EXTENSIONS
WINDOWS_RESERVED_BASENAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{number}" for number in range(1, 10)),
    *(f"LPT{number}" for number in range(1, 10)),
}


@dataclass(frozen=True)
class UploadedFileData:
    filename: str
    content: bytes


def safe_upload_filename(filename: str) -> str:
    name = PurePath(filename.replace("\\", "/")).name.strip()
    if not name:
        raise ValueError("\u6587\u4ef6\u540d\u4e0d\u80fd\u4e3a\u7a7a")
    _raise_if_windows_reserved(PurePath(name).stem, strip_unsafe=True)
    safe_name = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff._-]+", "_", name)
    _raise_if_windows_reserved(PurePath(safe_name).stem)
    return safe_name


def file_sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def file_extension(filename: str) -> str:
    return PurePath(filename).suffix.lower()


def is_supported_text_file(filename: str) -> bool:
    return file_extension(filename) in SUPPORTED_TEXT_EXTENSIONS


def document_type_from_filename(filename: str) -> DocumentTypeLiteral:
    extension = file_extension(filename)
    if extension == ".pdf":
        return "PDF"
    if extension in {".doc", ".docx"}:
        return "Word"
    if extension in {".xls", ".xlsx"}:
        return "Excel"
    if extension in {".md", ".markdown"}:
        return "Markdown"
    if extension == ".txt":
        return "TXT"
    raise ValueError("不支持的文件类型")


def validate_upload_file(file_data: UploadedFileData, max_bytes: int) -> str:
    safe_name = safe_upload_filename(file_data.filename)
    if len(file_data.content) == 0:
        raise ValueError("\u6587\u4ef6\u5185\u5bb9\u4e3a\u7a7a")
    if len(file_data.content) > max_bytes:
        raise ValueError("\u6587\u4ef6\u8d85\u8fc7\u5927\u5c0f\u9650\u5236")
    if file_extension(safe_name) not in ALLOWED_EXTENSIONS:
        raise ValueError("\u4e0d\u652f\u6301\u7684\u6587\u4ef6\u7c7b\u578b")
    return safe_name


def _raise_if_windows_reserved(basename: str, *, strip_unsafe: bool = False) -> None:
    candidate = re.sub(r"[^0-9A-Za-z]+", "", basename) if strip_unsafe else basename
    if candidate.upper() in WINDOWS_RESERVED_BASENAMES:
        raise ValueError("文件名不能使用 Windows 保留名称")


async def upload_document_file(
    session: Session,
    file_data: UploadedFileData,
    upload_dir: Path,
    max_bytes: int,
    embedding_client: EmbeddingClient,
    embedding_model: str,
) -> DocumentItemSchema:
    safe_name = validate_upload_file(file_data, max_bytes=max_bytes)
    sha256 = file_sha256(file_data.content)

    existing = session.execute(
        select(KbDocument).where(KbDocument.file_sha256 == sha256)
    ).scalar_one_or_none()
    if existing is not None:
        return map_document_item(existing)

    if is_supported_text_file(safe_name):
        content = _decode_text_upload(file_data.content)
        upload_dir.mkdir(parents=True, exist_ok=True)
        saved_path = upload_dir / f"{sha256}_{safe_name}"
        saved_path.write_bytes(file_data.content)
        return await _upload_supported_text_document(
            session=session,
            content=content,
            safe_name=safe_name,
            saved_path=saved_path,
            sha256=sha256,
            embedding_client=embedding_client,
            embedding_model=embedding_model,
        )

    upload_dir.mkdir(parents=True, exist_ok=True)
    saved_path = upload_dir / f"{sha256}_{safe_name}"
    saved_path.write_bytes(file_data.content)
    return _create_unsupported_document_record(
        session=session,
        safe_name=safe_name,
        saved_path=saved_path,
        sha256=sha256,
    )


async def _upload_supported_text_document(
    session: Session,
    content: str,
    safe_name: str,
    saved_path: Path,
    sha256: str,
    embedding_client: EmbeddingClient,
    embedding_model: str,
) -> DocumentItemSchema:
    try:
        document_id, created = await import_markdown_document_with_result(
            session=session,
            document=MarkdownDocument(
                path=saved_path,
                title=Path(safe_name).stem,
                content=content,
                file_sha256=sha256,
            ),
            embedding_client=embedding_client,
            embedding_model=embedding_model,
        )
    except IntegrityError:
        _rollback_if_available(session)
        existing = _document_by_sha256(session, sha256)
        if existing is None:
            raise
        _unlink_if_not_document_source(saved_path, existing)
        return map_document_item(existing)

    document = session.get(KbDocument, document_id)
    if document is None:
        raise RuntimeError("上传文档入库后未找到记录")
    if not created:
        _unlink_if_not_document_source(saved_path, document)
        return map_document_item(document)

    metadata = dict(document.document_metadata or {})
    metadata["source_file_name"] = safe_name
    metadata.setdefault("category", "uncategorized")
    document.file_name = safe_name
    document.file_type = "markdown" if file_extension(safe_name) in {".md", ".markdown"} else "txt"
    document.source_path = str(saved_path)
    document.document_metadata = metadata
    session.commit()
    session.refresh(document)
    return map_document_item(document)


def _decode_text_upload(content: bytes) -> str:
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("文本文件必须使用 UTF-8 编码") from exc


def _create_unsupported_document_record(
    session: Session,
    safe_name: str,
    saved_path: Path,
    sha256: str,
) -> DocumentItemSchema:
    document_type = document_type_from_filename(safe_name)
    error_message = (
        f"当前阶段暂不支持解析 {document_type} 文件，请先上传 Markdown 或 TXT 文本文件。"
    )
    document = KbDocument(
        title=Path(safe_name).stem,
        source_path=str(saved_path),
        file_name=safe_name,
        file_type=file_extension(safe_name).lstrip("."),
        file_sha256=sha256,
        status=DocumentStatus.failed,
        enabled=False,
        segment_count=0,
        error_message=error_message,
        document_metadata={
            "source_file_name": safe_name,
            "category": "uncategorized",
            "unsupported_upload": True,
        },
    )
    try:
        session.add(document)
        session.flush()
        finished_at = datetime.now(UTC)
        task = ParseTask(
            document_id=document.id,
            status=ParseTaskStatus.failed,
            parser_name="unsupported-upload-placeholder",
            retry_count=0,
            error_message=error_message,
            started_at=finished_at,
            finished_at=finished_at,
            task_metadata={"unsupported_upload": True},
        )
        session.add(task)
        session.commit()
        session.refresh(document)
        return map_document_item(document)
    except IntegrityError:
        _rollback_if_available(session)
        existing = _document_by_sha256(session, sha256)
        if existing is None:
            raise
        _unlink_if_not_document_source(saved_path, existing)
        return map_document_item(existing)


def _document_by_sha256(session: Session, sha256: str) -> KbDocument | None:
    return session.execute(
        select(KbDocument).where(KbDocument.file_sha256 == sha256)
    ).scalar_one_or_none()


def _rollback_if_available(session: Session) -> None:
    rollback = getattr(session, "rollback", None)
    if rollback is not None:
        rollback()


def _unlink_if_exists(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except FileNotFoundError:
        pass


def _unlink_if_not_document_source(path: Path, document: KbDocument) -> None:
    source_path = document.source_path
    if source_path and _same_filesystem_path(path, Path(source_path)):
        return
    _unlink_if_exists(path)


def _same_filesystem_path(left: Path, right: Path) -> bool:
    try:
        return left.resolve(strict=False) == right.resolve(strict=False)
    except OSError:
        return left.absolute() == right.absolute()
