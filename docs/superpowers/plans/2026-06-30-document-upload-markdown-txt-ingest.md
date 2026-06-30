# Document Upload Markdown TXT Ingest Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a real upload path for document management so admins can upload Markdown/TXT files into the knowledge base and see unsupported PDF/Word/Excel uploads represented clearly in the document list.

**Architecture:** Extend the existing `/api/documents` backend with a multipart upload endpoint that saves the original file under ignored runtime storage, then dispatches supported text files through the existing Markdown chunking/embedding ingest path. Keep this stage synchronous and small: Markdown/TXT uploads are processed during the request, while PDF/Word/Excel are persisted as `failed` records with a clear unsupported-parser message. The frontend replaces the disabled upload placeholder with a file picker and calls the new endpoint, then inserts or refreshes the returned document item.

**Tech Stack:** FastAPI multipart upload, SQLAlchemy 2.0, Pydantic, existing `import_markdown_document`/SiliconFlow embedding client, pytest, Vue 3, Pinia, TypeScript, Vite.

---

## Scope

This plan implements:

- A backend upload endpoint: `POST /api/documents/upload`.
- Runtime file storage under `backend/uploads/documents`.
- Markdown and TXT content import into `kb_document`, `parse_task`, and `kb_document_segment`.
- Unsupported PDF/Word/Excel records with `parseStatus="failed"` and a user-readable failure reason.
- Frontend upload interaction using a real file input.
- Focused backend and frontend verification.

This plan does not implement:

- PDF/Word/Excel real parsing.
- Background workers or queued asynchronous parsing.
- Upload progress bars.
- Multi-file batch upload.
- Deleting uploaded source files.

## File Structure

- Modify `backend/app/core/config.py`: add upload directory and upload size settings.
- Modify `.env.example`: document upload settings.
- Create `backend/app/services/document_uploads.py`: filename sanitization, file saving, supported-type detection, Markdown/TXT conversion to `MarkdownDocument`, unsupported record creation, and upload orchestration.
- Modify `backend/app/services/ingest.py`: expose a small helper to import already-loaded text documents without requiring `.md` extension, only if needed by `document_uploads.py`.
- Modify `backend/app/api/documents.py`: add `POST /documents/upload`, build embedding client from settings, return `DocumentItemSchema`.
- Modify `backend/app/services/document_management.py`: reuse mapping and possibly support upload-specific metadata/category if needed.
- Create `backend/tests/test_document_uploads.py`: service-level tests for sanitization, supported text ingest, unsupported format records, duplicate SHA behavior, and size/type checks.
- Modify `backend/tests/test_documents_api.py`: API test for upload endpoint dependency override.
- Modify `frontend/src/api/documents.ts`: add `uploadDocument(file: File): Promise<DocumentItem>`.
- Modify `frontend/src/stores/documents.ts`: add upload pending state and `uploadDocumentFile(file)` action.
- Modify `frontend/src/documents/documentStore.contract.ts`: update store contract.
- Modify `frontend/src/views/DocumentManageView.vue`: wire upload button to hidden file input, show selected upload state, refresh list after upload.
- Modify `frontend/src/styles/main.css`: style upload pending/disabled state if existing classes are insufficient.

## API Contract

### Upload Request

```http
POST /api/documents/upload
Content-Type: multipart/form-data

file=<uploaded file>
```

### Upload Response

Returns a `DocumentItemSchema`:

```json
{
  "id": "document-uuid",
  "name": "新上传运维资料.md",
  "type": "Markdown",
  "category": "uncategorized",
  "parseStatus": "ready",
  "enableStatus": "enabled",
  "updatedAt": "2026-06-30 15:30:00",
  "failureReason": null,
  "progress": 100
}
```

Unsupported files return `200` with a failed document record, not `4xx`, because the upload itself succeeded and the page should show the failure row:

```json
{
  "name": "设备资料.pdf",
  "type": "PDF",
  "parseStatus": "failed",
  "enableStatus": "disabled",
  "failureReason": "当前阶段暂不支持解析 PDF 文件，请先上传 Markdown 或 TXT 文本文件。",
  "progress": null
}
```

Bad requests use `4xx` only for request-level problems:

- Missing file.
- Empty filename.
- File over configured size limit.
- Binary decode failure for Markdown/TXT.

## Data Rules

- Upload storage root: `settings.upload_storage_dir`, default `PROJECT_ROOT / "backend" / "uploads" / "documents"`.
- Allowed extensions: `.md`, `.markdown`, `.txt`, `.pdf`, `.doc`, `.docx`, `.xls`, `.xlsx`.
- Supported ingest extensions: `.md`, `.markdown`, `.txt`.
- Unsupported-but-recorded extensions: `.pdf`, `.doc`, `.docx`, `.xls`, `.xlsx`.
- Uploaded source files are saved as `<sha256>_<safe_original_name>` to avoid collisions.
- SHA256 duplicate behavior:
  - If a supported text file hash already exists, return the existing document item.
  - If an unsupported file hash already exists, return the existing document item.
- TXT ingest should reuse Markdown chunking by creating `MarkdownDocument(title=<filename stem>, content=<decoded text>)`; plain text with no headings is allowed if the chunker can produce chunks. If chunking fails, preserve the normal failed document status from `import_markdown_document`.
- Uploaded documents default to `category="uncategorized"` through metadata.

## Implementation Tasks

### Task 1: Upload Settings and Schemas

**Files:**

- Modify: `backend/app/core/config.py`
- Modify: `.env.example`
- Modify: `backend/app/schemas/documents.py`
- Test: `backend/tests/test_document_uploads.py`

- [ ] **Step 1: Write failing settings/schema tests**

Create `backend/tests/test_document_uploads.py`:

```python
from pathlib import Path

from app.core.config import PROJECT_ROOT, Settings
from app.schemas.documents import DocumentUploadErrorSchema


def test_default_upload_settings_point_to_ignored_backend_uploads():
    settings = Settings()

    assert settings.upload_storage_dir == PROJECT_ROOT / "backend" / "uploads" / "documents"
    assert settings.upload_max_bytes == 20 * 1024 * 1024


def test_document_upload_error_schema_contains_message():
    error = DocumentUploadErrorSchema(message="文件过大")

    assert error.message == "文件过大"
```

- [ ] **Step 2: Run the focused test to verify it fails**

Run:

```powershell
backend\.venv\Scripts\python.exe -c "import sys, pathlib, pytest; root=pathlib.Path.cwd(); sys.path[:0]=[str(root), str(root / 'backend')]; raise SystemExit(pytest.main(['backend/tests/test_document_uploads.py::test_default_upload_settings_point_to_ignored_backend_uploads', '-q']))"
```

Expected: failure because `upload_storage_dir` is not defined.

- [ ] **Step 3: Add upload settings**

In `backend/app/core/config.py`, add these fields inside `Settings` after the Redis settings:

```python
    upload_storage_dir: Path = PROJECT_ROOT / "backend" / "uploads" / "documents"
    upload_max_bytes: int = 20 * 1024 * 1024
```

Ensure `Path` is already imported from `pathlib`.

- [ ] **Step 4: Add upload error schema**

In `backend/app/schemas/documents.py`, append:

```python
class DocumentUploadErrorSchema(BaseModel):
    message: str
```

- [ ] **Step 5: Document `.env.example` settings**

Add to `.env.example` near other backend settings:

```env
# 上传文件保存目录和大小限制
UPLOAD_STORAGE_DIR=backend/uploads/documents
UPLOAD_MAX_BYTES=20971520
```

- [ ] **Step 6: Run tests**

Run:

```powershell
backend\.venv\Scripts\python.exe -c "import sys, pathlib, pytest; root=pathlib.Path.cwd(); sys.path[:0]=[str(root), str(root / 'backend')]; raise SystemExit(pytest.main(['backend/tests/test_document_uploads.py', '-q']))"
```

Expected: `2 passed`.

- [ ] **Step 7: Commit**

```powershell
git add backend/app/core/config.py backend/app/schemas/documents.py backend/tests/test_document_uploads.py .env.example
git commit -m "feat: add document upload settings"
```

### Task 2: Upload Service File Saving and Type Rules

**Files:**

- Create: `backend/app/services/document_uploads.py`
- Modify: `backend/tests/test_document_uploads.py`

- [ ] **Step 1: Add failing service utility tests**

Append to `backend/tests/test_document_uploads.py`:

```python
import pytest

from app.services.document_uploads import (
    UploadedFileData,
    document_type_from_filename,
    safe_upload_filename,
    validate_upload_file,
)


def test_safe_upload_filename_removes_path_and_unsafe_characters():
    assert safe_upload_filename("..\\逆变器 运维手册.md") == "逆变器_运维手册.md"
    assert safe_upload_filename("../../bad name?.txt") == "bad_name_.txt"


def test_document_type_from_filename_maps_supported_extensions():
    assert document_type_from_filename("a.pdf") == "PDF"
    assert document_type_from_filename("a.docx") == "Word"
    assert document_type_from_filename("a.xlsx") == "Excel"
    assert document_type_from_filename("a.markdown") == "Markdown"
    assert document_type_from_filename("a.txt") == "TXT"


def test_validate_upload_file_rejects_empty_and_oversized_files():
    with pytest.raises(ValueError, match="文件内容为空"):
        validate_upload_file(UploadedFileData(filename="a.md", content=b""), max_bytes=10)

    with pytest.raises(ValueError, match="文件超过大小限制"):
        validate_upload_file(UploadedFileData(filename="a.md", content=b"123456"), max_bytes=5)


def test_validate_upload_file_rejects_unknown_extension():
    with pytest.raises(ValueError, match="不支持的文件类型"):
        validate_upload_file(UploadedFileData(filename="a.exe", content=b"hello"), max_bytes=100)
```

- [ ] **Step 2: Run utility tests to verify they fail**

Run:

```powershell
backend\.venv\Scripts\python.exe -c "import sys, pathlib, pytest; root=pathlib.Path.cwd(); sys.path[:0]=[str(root), str(root / 'backend')]; raise SystemExit(pytest.main(['backend/tests/test_document_uploads.py::test_safe_upload_filename_removes_path_and_unsafe_characters', '-q']))"
```

Expected: failure because `app.services.document_uploads` does not exist.

- [ ] **Step 3: Implement upload utility service**

Create `backend/app/services/document_uploads.py`:

```python
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import PurePath

from app.schemas.documents import DocumentTypeLiteral


SUPPORTED_TEXT_EXTENSIONS = {".md", ".markdown", ".txt"}
UNSUPPORTED_RECORDED_EXTENSIONS = {".pdf", ".doc", ".docx", ".xls", ".xlsx"}
ALLOWED_EXTENSIONS = SUPPORTED_TEXT_EXTENSIONS | UNSUPPORTED_RECORDED_EXTENSIONS


@dataclass(frozen=True)
class UploadedFileData:
    filename: str
    content: bytes


def safe_upload_filename(filename: str) -> str:
    name = PurePath(filename.replace("\\", "/")).name.strip()
    if not name:
        raise ValueError("文件名不能为空")
    return re.sub(r"[^0-9A-Za-z\u4e00-\u9fff._-]+", "_", name)


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
    return "TXT"


def validate_upload_file(file_data: UploadedFileData, max_bytes: int) -> str:
    safe_name = safe_upload_filename(file_data.filename)
    if len(file_data.content) == 0:
        raise ValueError("文件内容为空")
    if len(file_data.content) > max_bytes:
        raise ValueError("文件超过大小限制")
    if file_extension(safe_name) not in ALLOWED_EXTENSIONS:
        raise ValueError("不支持的文件类型")
    return safe_name
```

- [ ] **Step 4: Run upload utility tests**

Run:

```powershell
backend\.venv\Scripts\python.exe -c "import sys, pathlib, pytest; root=pathlib.Path.cwd(); sys.path[:0]=[str(root), str(root / 'backend')]; raise SystemExit(pytest.main(['backend/tests/test_document_uploads.py', '-q']))"
```

Expected: all current upload tests pass.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/services/document_uploads.py backend/tests/test_document_uploads.py
git commit -m "feat: validate document uploads"
```

### Task 3: Upload Service Orchestration

**Files:**

- Modify: `backend/app/services/document_uploads.py`
- Modify: `backend/tests/test_document_uploads.py`

- [ ] **Step 1: Add failing orchestration tests**

Append to `backend/tests/test_document_uploads.py`:

```python
import uuid
from datetime import UTC, datetime

import pytest

from app.models.rag import DocumentStatus, KbDocument, ParseTask, ParseTaskStatus
from app.services.document_uploads import upload_document_file


class _ScalarResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class _UploadSession:
    def __init__(self, existing_document=None):
        self.existing_document = existing_document
        self.added = []
        self.commits = 0
        self.flushes = 0
        self.refreshed = []

    def execute(self, statement):
        return _ScalarResult(self.existing_document)

    def add(self, item):
        self.added.append(item)

    def flush(self):
        self.flushes += 1
        for item in self.added:
            if getattr(item, "id", None) is None:
                item.id = uuid.uuid4()
            if getattr(item, "updated_at", None) is None:
                item.updated_at = datetime(2026, 6, 30, 15, 0, 0, tzinfo=UTC)

    def commit(self):
        self.commits += 1

    def refresh(self, item):
        self.refreshed.append(item)


class _FakeEmbeddingClient:
    async def embed(self, texts):
        return [[0.1, 0.2] for _ in texts]


@pytest.mark.asyncio
async def test_upload_document_file_returns_existing_duplicate_document(tmp_path):
    existing = KbDocument(
        id=uuid.uuid4(),
        title="已有文档",
        file_name="existing.md",
        file_type="markdown",
        file_sha256=file_sha256(b"# Existing\n\ncontent"),
        status=DocumentStatus.ready,
        enabled=True,
        segment_count=1,
        document_metadata={"source_file_name": "existing.md"},
        updated_at=datetime(2026, 6, 30, 15, 0, 0, tzinfo=UTC),
    )
    session = _UploadSession(existing_document=existing)

    item = await upload_document_file(
        session=session,
        file_data=UploadedFileData(filename="existing.md", content=b"# Existing\n\ncontent"),
        upload_dir=tmp_path,
        max_bytes=1000,
        embedding_client=_FakeEmbeddingClient(),
        embedding_model="test-embedding",
    )

    assert item.id == existing.id
    assert item.name == "existing.md"
    assert session.added == []


@pytest.mark.asyncio
async def test_upload_document_file_creates_failed_record_for_unsupported_pdf(tmp_path):
    session = _UploadSession()

    item = await upload_document_file(
        session=session,
        file_data=UploadedFileData(filename="设备资料.pdf", content=b"%PDF test"),
        upload_dir=tmp_path,
        max_bytes=1000,
        embedding_client=_FakeEmbeddingClient(),
        embedding_model="test-embedding",
    )

    document = next(item for item in session.added if isinstance(item, KbDocument))
    task = next(item for item in session.added if isinstance(item, ParseTask))

    assert document.file_name == "设备资料.pdf"
    assert document.file_type == "pdf"
    assert document.status == DocumentStatus.failed
    assert document.enabled is False
    assert "暂不支持解析 PDF" in document.error_message
    assert task.status == ParseTaskStatus.failed
    assert item.parseStatus == "failed"
    assert item.enableStatus == "disabled"
    assert item.failureReason == document.error_message
    assert (tmp_path / f"{document.file_sha256}_设备资料.pdf").exists()
```

- [ ] **Step 2: Run orchestration tests to verify they fail**

Run:

```powershell
backend\.venv\Scripts\python.exe -c "import sys, pathlib, pytest; root=pathlib.Path.cwd(); sys.path[:0]=[str(root), str(root / 'backend')]; raise SystemExit(pytest.main(['backend/tests/test_document_uploads.py::test_upload_document_file_creates_failed_record_for_unsupported_pdf', '-q']))"
```

Expected: failure because `upload_document_file` is missing.

- [ ] **Step 3: Implement upload orchestration**

Add these imports to `backend/app/services/document_uploads.py`:

```python
from datetime import UTC, datetime
from pathlib import Path
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.rag import DocumentStatus, KbDocument, ParseTask, ParseTaskStatus
from app.schemas.documents import DocumentItemSchema
from app.services.document_management import map_document_item
from app.services.ingest import EmbeddingClient, MarkdownDocument, import_markdown_document
```

Append:

```python
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

    upload_dir.mkdir(parents=True, exist_ok=True)
    saved_path = upload_dir / f"{sha256}_{safe_name}"
    saved_path.write_bytes(file_data.content)

    if is_supported_text_file(safe_name):
        return await _upload_supported_text_document(
            session=session,
            file_data=file_data,
            safe_name=safe_name,
            saved_path=saved_path,
            sha256=sha256,
            embedding_client=embedding_client,
            embedding_model=embedding_model,
        )

    return _create_unsupported_document_record(
        session=session,
        safe_name=safe_name,
        saved_path=saved_path,
        sha256=sha256,
    )


async def _upload_supported_text_document(
    session: Session,
    file_data: UploadedFileData,
    safe_name: str,
    saved_path: Path,
    sha256: str,
    embedding_client: EmbeddingClient,
    embedding_model: str,
) -> DocumentItemSchema:
    try:
        content = file_data.content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("文本文件必须使用 UTF-8 编码") from exc

    document_id = await import_markdown_document(
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
    document = session.get(KbDocument, document_id)
    if document is None:
        raise RuntimeError("上传文档入库后未找到记录")

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


def _create_unsupported_document_record(
    session: Session,
    safe_name: str,
    saved_path: Path,
    sha256: str,
) -> DocumentItemSchema:
    document_type = document_type_from_filename(safe_name)
    error_message = f"当前阶段暂不支持解析 {document_type} 文件，请先上传 Markdown 或 TXT 文本文件。"
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
    session.add(document)
    session.flush()
    task = ParseTask(
        document_id=document.id,
        status=ParseTaskStatus.failed,
        parser_name="unsupported-upload-placeholder",
        retry_count=0,
        error_message=error_message,
        started_at=datetime.now(UTC),
        finished_at=datetime.now(UTC),
        task_metadata={"unsupported_upload": True},
    )
    session.add(task)
    session.commit()
    session.refresh(document)
    return map_document_item(document)
```

- [ ] **Step 4: Add supported text integration test**

Append:

```python
@pytest.mark.asyncio
async def test_upload_document_file_imports_markdown_text(tmp_path):
    session = _UploadSession()

    item = await upload_document_file(
        session=session,
        file_data=UploadedFileData(
            filename="新上传运维资料.md",
            content="# 新上传运维资料\n\n## 检查步骤\n\n检查逆变器运行状态。",
        ),
        upload_dir=tmp_path,
        max_bytes=2000,
        embedding_client=_FakeEmbeddingClient(),
        embedding_model="test-embedding",
    )

    document = next(item for item in session.added if isinstance(item, KbDocument))

    assert document.file_name == "新上传运维资料.md"
    assert document.file_type == "markdown"
    assert document.status == DocumentStatus.ready
    assert document.enabled is True
    assert document.document_metadata["category"] == "uncategorized"
    assert item.parseStatus == "ready"
    assert item.enableStatus == "enabled"
```

- [ ] **Step 5: Run upload service tests**

Run:

```powershell
backend\.venv\Scripts\python.exe -c "import sys, pathlib, pytest; root=pathlib.Path.cwd(); sys.path[:0]=[str(root), str(root / 'backend')]; raise SystemExit(pytest.main(['backend/tests/test_document_uploads.py', '-q']))"
```

Expected: upload service tests pass.

- [ ] **Step 6: Commit**

```powershell
git add backend/app/services/document_uploads.py backend/tests/test_document_uploads.py
git commit -m "feat: ingest uploaded text documents"
```

### Task 4: Upload API Endpoint

**Files:**

- Modify: `backend/app/api/documents.py`
- Modify: `backend/tests/test_documents_api.py`

- [ ] **Step 1: Add failing API upload test**

Append to `backend/tests/test_documents_api.py`:

```python
def test_upload_document_endpoint_returns_document_item():
    app = create_app()
    expected = _item()

    from app.api.documents import get_document_uploader

    class FakeUploader:
        async def upload(self, file):
            assert file.filename == "新上传运维资料.md"
            return expected

    app.dependency_overrides[get_document_uploader] = lambda: FakeUploader()
    client = TestClient(app)

    response = client.post(
        "/api/documents/upload",
        files={"file": ("新上传运维资料.md", b"# Title\n\nbody", "text/markdown")},
    )

    assert response.status_code == 200
    assert response.json()["id"] == str(expected.id)
```

- [ ] **Step 2: Run API upload test to verify it fails**

Run:

```powershell
backend\.venv\Scripts\python.exe -c "import sys, pathlib, pytest; root=pathlib.Path.cwd(); sys.path[:0]=[str(root), str(root / 'backend')]; raise SystemExit(pytest.main(['backend/tests/test_documents_api.py::test_upload_document_endpoint_returns_document_item', '-q']))"
```

Expected: failure because `get_document_uploader` or endpoint is missing.

- [ ] **Step 3: Implement API uploader dependency**

Modify `backend/app/api/documents.py` imports:

```python
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
import httpx

from app.core.config import settings
from app.services.document_uploads import UploadedFileData, upload_document_file
from app.services.siliconflow import SiliconFlowEmbeddingClient
```

Add:

```python
class DocumentUploader:
    def __init__(self, session: Session):
        self._session = session

    async def upload(self, file: UploadFile) -> DocumentItemSchema:
        content = await file.read()
        timeout = httpx.Timeout(settings.model_api_timeout_seconds)
        async with httpx.AsyncClient(
            base_url=settings.embedding_base_url,
            timeout=timeout,
        ) as http_client:
            embedding_client = SiliconFlowEmbeddingClient(
                client=http_client,
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


def get_document_uploader(
    session: Session = Depends(get_db_session),
) -> DocumentUploader:
    return DocumentUploader(session)
```

Add endpoint:

```python
@router.post("/upload", response_model=DocumentItemSchema)
async def upload_document(
    file: UploadFile = File(...),
    uploader: DocumentUploader = Depends(get_document_uploader),
) -> DocumentItemSchema:
    try:
        return await uploader.upload(file)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
```

- [ ] **Step 4: Ensure multipart dependency is installed**

Run:

```powershell
backend\.venv\Scripts\python.exe -c "import multipart; print('multipart ok')"
```

Expected: `multipart ok`.

If it fails, add `python-multipart` to `backend/requirements.txt`, install it, and rerun the import check.

- [ ] **Step 5: Run API upload tests**

Run:

```powershell
backend\.venv\Scripts\python.exe -c "import sys, pathlib, pytest; root=pathlib.Path.cwd(); sys.path[:0]=[str(root), str(root / 'backend')]; raise SystemExit(pytest.main(['backend/tests/test_documents_api.py', '-q']))"
```

Expected: document API tests pass.

- [ ] **Step 6: Commit**

```powershell
git add backend/app/api/documents.py backend/tests/test_documents_api.py backend/requirements.txt
git commit -m "feat: add document upload endpoint"
```

### Task 5: Frontend Upload API and Store

**Files:**

- Modify: `frontend/src/api/documents.ts`
- Modify: `frontend/src/stores/documents.ts`
- Modify: `frontend/src/documents/documentStore.contract.ts`

- [ ] **Step 1: Add upload API client**

In `frontend/src/api/documents.ts`, add:

```typescript
export async function uploadDocument(file: File): Promise<DocumentItem> {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch("/api/documents/upload", {
    method: "POST",
    body: formData
  });

  return parseDocumentResponse(response);
}
```

- [ ] **Step 2: Add upload state and action to store**

In `frontend/src/stores/documents.ts`, update imports:

```typescript
import { listDocuments, retryDocumentParse, setDocumentEnabled, uploadDocument } from "../api/documents";
```

Add refs near existing loading state:

```typescript
  const isUploading = ref(false);
```

Add action:

```typescript
  async function uploadDocumentFile(file: File) {
    if (isUploading.value || isLoading.value || hasPendingDocumentActions.value) {
      return;
    }

    isUploading.value = true;
    errorMessage.value = "";

    try {
      const uploaded = await uploadDocument(file);
      documents.value = [uploaded, ...documents.value.filter((document) => document.id !== uploaded.id)];
      resetPage();
      lastNotice.value =
        uploaded.parseStatus === "failed"
          ? `文档已上传，但解析失败：${uploaded.failureReason ?? "当前格式暂不支持"}`
          : "文档已上传并完成入库。";
    } catch (error) {
      errorMessage.value = error instanceof Error ? error.message : "文档上传失败";
    } finally {
      isUploading.value = false;
    }
  }
```

Return `isUploading` and `uploadDocumentFile`.

- [ ] **Step 3: Update contract**

In `frontend/src/documents/documentStore.contract.ts`, add:

```typescript
void store.isUploading;
void store.uploadDocumentFile(new File(["# 标题\n\n内容"], "上传资料.md", { type: "text/markdown" }));
```

- [ ] **Step 4: Run frontend build to catch type errors**

Run:

```powershell
cd frontend
npm run build
```

Expected: build passes after Task 6 view wiring, or fails now because the view has not consumed the new store action. If it fails only due to unused symbols, continue to Task 6 before committing.

### Task 6: Frontend Upload UI

**Files:**

- Modify: `frontend/src/views/DocumentManageView.vue`
- Modify: `frontend/src/styles/main.css`

- [ ] **Step 1: Add file input refs and upload handler**

In `frontend/src/views/DocumentManageView.vue`, add after `selectedFailure`:

```typescript
const uploadInput = ref<HTMLInputElement | null>(null);

function openUploadPicker() {
  if (documentStore.isUploading || documentStore.isLoading || documentStore.hasPendingDocumentActions) {
    return;
  }
  uploadInput.value?.click();
}

async function handleUploadChange(event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  input.value = "";
  if (!file) {
    return;
  }
  await documentStore.uploadDocumentFile(file);
}
```

- [ ] **Step 2: Replace disabled upload button**

Replace the header upload button with:

```vue
        <input
          ref="uploadInput"
          class="document-hidden-file"
          type="file"
          accept=".md,.markdown,.txt,.pdf,.doc,.docx,.xls,.xlsx"
          @change="handleUploadChange"
        />
        <button
          class="document-upload-primary"
          type="button"
          :disabled="documentStore.isUploading || documentStore.isLoading || documentStore.hasPendingDocumentActions"
          @click="openUploadPicker"
        >
          <Upload aria-hidden="true" />
          {{ documentStore.isUploading ? "上传中" : "上传文档" }}
        </button>
```

- [ ] **Step 3: Update upload strip copy**

Replace the upload strip text with:

```vue
          <strong>支持 Markdown / TXT 真实入库</strong>
          <span>PDF、Word、Excel 会先保存并显示为解析失败，完整解析器将在后续阶段接入。</span>
```

- [ ] **Step 4: Add hidden file style**

In `frontend/src/styles/main.css`, add:

```css
.document-hidden-file {
  display: none;
}
```

- [ ] **Step 5: Run frontend build**

Run:

```powershell
cd frontend
npm run build
```

Expected: build succeeds.

- [ ] **Step 6: Commit**

```powershell
git add frontend/src/api/documents.ts frontend/src/stores/documents.ts frontend/src/documents/documentStore.contract.ts frontend/src/views/DocumentManageView.vue frontend/src/styles/main.css
git commit -m "feat: upload documents from management page"
```

### Task 7: Full Verification and Manual Smoke

**Files:**

- No new files unless verification exposes defects.

- [ ] **Step 1: Run backend upload tests**

Run:

```powershell
backend\.venv\Scripts\python.exe -c "import sys, pathlib, pytest; root=pathlib.Path.cwd(); sys.path[:0]=[str(root), str(root / 'backend')]; raise SystemExit(pytest.main(['backend/tests/test_document_uploads.py', 'backend/tests/test_documents_api.py', '-q']))"
```

Expected: upload and document API tests pass.

- [ ] **Step 2: Run existing document management tests**

Run:

```powershell
backend\.venv\Scripts\python.exe -c "import sys, pathlib, pytest; root=pathlib.Path.cwd(); sys.path[:0]=[str(root), str(root / 'backend')]; raise SystemExit(pytest.main(['backend/tests/test_document_management.py', '-q']))"
```

Expected: document management service tests pass.

- [ ] **Step 3: Run frontend build**

Run:

```powershell
cd frontend
npm run build
```

Expected: build succeeds.

- [ ] **Step 4: Manual Markdown upload smoke**

Start backend:

```powershell
cd backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

In another terminal, create a tiny Markdown test file under a temporary directory and upload with PowerShell:

```powershell
$path = "$env:TEMP\pv-upload-smoke.md"
Set-Content -LiteralPath $path -Encoding UTF8 -Value "# 上传烟测`n`n## 检查步骤`n`n检查逆变器运行状态。"
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/documents/upload -Form @{ file = Get-Item -LiteralPath $path }
```

Expected:

- Response has `parseStatus` equal to `ready` if embedding config/API is available.
- If embedding API is unavailable, response or request may fail with the current model-provider error; record the exact error. Do not hide provider failures.

- [ ] **Step 5: Manual unsupported file smoke**

Upload a dummy PDF-like file:

```powershell
$path = "$env:TEMP\pv-upload-smoke.pdf"
Set-Content -LiteralPath $path -Encoding ASCII -Value "%PDF dummy"
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/documents/upload -Form @{ file = Get-Item -LiteralPath $path }
```

Expected:

- Response has `type="PDF"`.
- Response has `parseStatus="failed"`.
- `failureReason` explains PDF parsing is not supported yet.

## Self-Review

- Spec coverage: Covers backend upload settings, file validation/storage, Markdown/TXT ingest, unsupported format records, upload API, frontend upload UI, and verification.
- Placeholder scan: No unresolved placeholders. Unsupported PDF/Word/Excel behavior is explicit and user-visible for this stage.
- Type consistency: Backend response remains `DocumentItemSchema`; frontend continues using `DocumentItem`; upload client/store/action names are `uploadDocument`, `uploadDocumentFile`, and `/api/documents/upload`.
