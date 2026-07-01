# Document Parse Workflow Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the current document retry placeholder into a real synchronous parse retry for Markdown/TXT documents, while keeping PDF/Word/Excel as clear unsupported failures.

**Architecture:** Keep this stage deliberately small. Add one backend parsing service that reparses an existing document from its saved `source_path`, replaces segments, records a `ParseTask`, and returns the existing `DocumentItemSchema`; wire the retry endpoint to it; make the frontend notice/refresh behavior match the real returned status.

**Tech Stack:** FastAPI, SQLAlchemy 2.0, existing Markdown chunker/embedding path, pytest, Vue 3, Pinia, TypeScript, Vite.

---

## Scope

This plan implements:

- Real `POST /api/documents/{id}/retry` behavior for `.md`, `.markdown`, and `.txt`.
- Segment replacement on successful retry.
- `ParseTask` records for success and failure.
- Clear failed retry records for unsupported PDF/Word/Excel.
- Frontend retry notices based on the actual returned status.
- A light processing refresh hook if a document remains `processing`.

This plan does not implement:

- Background queues/workers.
- Progress streaming.
- PDF/Word/Excel real parsing.
- OCR/table extraction.
- Delete/category edit/segment preview.

## Current State

- Upload already stores files and sets `source_path`.
- Markdown/TXT upload already uses the existing RAG ingest path.
- PDF/Word/Excel upload records failed placeholder documents.
- `backend/app/services/document_management.py::retry_document_parse` is currently a placeholder.
- Frontend already calls `/api/documents/{id}/retry` and replaces the returned row.

## Files

- Create `backend/app/services/document_parsing.py`
  - One service function: `retry_document_parse(session, document_id, embedding_client, embedding_model)`.
  - Helpers can live in the same file.
- Modify `backend/app/api/documents.py`
  - Add parser dependency similar to uploader.
  - Retry endpoint calls real async parser.
- Modify `backend/app/services/document_management.py`
  - Remove placeholder retry code.
- Add `backend/tests/test_document_parse_workflow.py`
  - Focused tests for supported retry, unsupported retry, and failure.
- Modify `backend/tests/test_documents_api.py`
  - Retry endpoint dependency override tests.
- Modify `backend/tests/test_document_management.py`
  - Remove placeholder-specific tests.
- Modify `frontend/src/stores/documents.ts`
  - Retry notices and optional refresh action.
- Modify `frontend/src/documents/documentStore.contract.ts`
  - Store contract references if new fields are added.
- Modify `frontend/src/views/DocumentManageView.vue`
  - Optional polling hook and copy/button state, only if needed.

## Behavior

- Supported text retry:
  - Reads `document.source_path`.
  - Decodes UTF-8.
  - Chunks with existing `chunk_markdown`.
  - Embeds with existing embedding client.
  - Deletes old segments for that document.
  - Inserts new segments.
  - Sets document `ready`, `enabled=True`, `segment_count`, `error_message=None`.
  - Writes `ParseTask(status=success, parser_name="manual-retry-text")`.
- Unsupported retry:
  - Does not attempt parsing.
  - Keeps document failed/disabled.
  - Writes `ParseTask(status=failed, parser_name="unsupported-retry-placeholder")`.
  - Returns a user-readable unsupported message.
- Failed supported retry:
  - Sets document failed/disabled.
  - Saves error on document and task.
  - Returns failed `DocumentItemSchema`.

## Implementation Tasks

### Task 1: Backend Real Retry Service

**Files:**
- Create: `backend/app/services/document_parsing.py`
- Create: `backend/tests/test_document_parse_workflow.py`

- [ ] **Step 1: Add focused failing tests**

Create `backend/tests/test_document_parse_workflow.py` with three tests:

```python
import uuid
from datetime import UTC, datetime

import pytest

from app.models.rag import DocumentStatus, KbDocument, KbDocumentSegment, ParseTask, ParseTaskStatus


class _ScalarResult:
    def __init__(self, values):
        self._values = values

    def scalars(self):
        return iter(self._values)


class _ParseSession:
    def __init__(self, document=None, retry_counts=None):
        self.document = document
        self.retry_counts = retry_counts or []
        self.added = []
        self.executed = []
        self.commits = 0
        self.rollbacks = 0
        self.refreshed = []

    def get(self, model_type, item_id):
        if model_type is KbDocument and self.document is not None and self.document.id == item_id:
            return self.document
        return None

    def execute(self, statement):
        self.executed.append(statement)
        return _ScalarResult(self.retry_counts)

    def add(self, item):
        if getattr(item, "id", None) is None:
            item.id = uuid.uuid4()
        if getattr(item, "updated_at", None) is None:
            item.updated_at = datetime(2026, 6, 30, 16, 0, 0, tzinfo=UTC)
        self.added.append(item)

    def flush(self):
        for item in self.added:
            if getattr(item, "id", None) is None:
                item.id = uuid.uuid4()

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def refresh(self, item):
        self.refreshed.append(item)


class _FakeEmbeddingClient:
    async def embed(self, texts):
        return [[0.1, 0.2] for _ in texts]


class _FailingEmbeddingClient:
    async def embed(self, texts):
        raise RuntimeError("embedding unavailable")


@pytest.mark.asyncio
async def test_retry_document_parse_rebuilds_markdown_segments(tmp_path):
    from app.services.document_parsing import retry_document_parse

    source = tmp_path / "manual.md"
    source.write_text("# Manual\n\n## Step\n\nCheck inverter status.", encoding="utf-8")
    document = KbDocument(
        id=uuid.uuid4(),
        title="Manual",
        source_path=str(source),
        file_name="manual.md",
        file_type="markdown",
        file_sha256="a" * 64,
        status=DocumentStatus.failed,
        enabled=False,
        segment_count=0,
        error_message="old failure",
        document_metadata={"source_file_name": "manual.md", "category": "manual"},
        updated_at=datetime(2026, 6, 30, 16, 0, 0, tzinfo=UTC),
    )
    session = _ParseSession(document=document, retry_counts=[1])

    item = await retry_document_parse(
        session=session,
        document_id=document.id,
        embedding_client=_FakeEmbeddingClient(),
        embedding_model="test-embedding",
    )

    task = next(item for item in session.added if isinstance(item, ParseTask))
    segments = [item for item in session.added if isinstance(item, KbDocumentSegment)]

    assert item.parseStatus == "ready"
    assert item.enableStatus == "enabled"
    assert item.progress == 100
    assert document.status == DocumentStatus.ready
    assert document.enabled is True
    assert document.error_message is None
    assert document.segment_count == len(segments)
    assert task.status == ParseTaskStatus.success
    assert task.parser_name == "manual-retry-text"
    assert task.retry_count == 2
    assert segments
    assert session.commits == 1


@pytest.mark.asyncio
async def test_retry_document_parse_records_unsupported_pdf_failure(tmp_path):
    from app.services.document_parsing import retry_document_parse

    source = tmp_path / "case.pdf"
    source.write_bytes(b"%PDF dummy")
    document = KbDocument(
        id=uuid.uuid4(),
        title="Case",
        source_path=str(source),
        file_name="case.pdf",
        file_type="pdf",
        file_sha256="b" * 64,
        status=DocumentStatus.failed,
        enabled=False,
        segment_count=0,
        error_message="old failure",
        document_metadata={"source_file_name": "case.pdf", "category": "cases"},
        updated_at=datetime(2026, 6, 30, 16, 0, 0, tzinfo=UTC),
    )
    session = _ParseSession(document=document)

    item = await retry_document_parse(
        session=session,
        document_id=document.id,
        embedding_client=_FakeEmbeddingClient(),
        embedding_model="test-embedding",
    )

    task = next(item for item in session.added if isinstance(item, ParseTask))

    assert item.parseStatus == "failed"
    assert item.enableStatus == "disabled"
    assert "暂不支持解析 PDF" in item.failureReason
    assert task.status == ParseTaskStatus.failed
    assert task.parser_name == "unsupported-retry-placeholder"
    assert document.enabled is False
    assert session.commits == 1


@pytest.mark.asyncio
async def test_retry_document_parse_marks_failed_when_embedding_fails(tmp_path):
    from app.services.document_parsing import retry_document_parse

    source = tmp_path / "manual.md"
    source.write_text("# Manual\n\nbody", encoding="utf-8")
    document = KbDocument(
        id=uuid.uuid4(),
        title="Manual",
        source_path=str(source),
        file_name="manual.md",
        file_type="markdown",
        file_sha256="c" * 64,
        status=DocumentStatus.failed,
        enabled=False,
        segment_count=0,
        error_message="old failure",
        document_metadata={"source_file_name": "manual.md"},
        updated_at=datetime(2026, 6, 30, 16, 0, 0, tzinfo=UTC),
    )
    session = _ParseSession(document=document)

    item = await retry_document_parse(
        session=session,
        document_id=document.id,
        embedding_client=_FailingEmbeddingClient(),
        embedding_model="test-embedding",
    )

    task = next(item for item in session.added if isinstance(item, ParseTask))

    assert item.parseStatus == "failed"
    assert item.enableStatus == "disabled"
    assert item.failureReason == "embedding unavailable"
    assert document.status == DocumentStatus.failed
    assert document.enabled is False
    assert task.status == ParseTaskStatus.failed
    assert task.error_message == "embedding unavailable"
    assert session.commits == 1
```

- [ ] **Step 2: Run the tests and confirm they fail**

Run:

```powershell
backend\.venv\Scripts\python.exe -c "import sys, pathlib, pytest; root=pathlib.Path.cwd(); sys.path[:0]=[str(root), str(root / 'backend')]; raise SystemExit(pytest.main(['backend/tests/test_document_parse_workflow.py', '-q']))"
```

Expected: fail because `app.services.document_parsing` does not exist.

- [ ] **Step 3: Implement the parse service**

Create `backend/app/services/document_parsing.py`:

```python
from __future__ import annotations

import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.rag import DocumentStatus, KbDocument, KbDocumentSegment, ParseTask, ParseTaskStatus
from app.schemas.documents import DocumentItemSchema
from app.services.document_management import map_document_item
from app.services.ingest import EmbeddingClient
from app.services.keyword_index import build_keyword_text
from app.services.markdown_chunker import chunk_markdown

SUPPORTED_TEXT_EXTENSIONS = {".md", ".markdown", ".txt"}
UNSUPPORTED_TYPES = {
    ".pdf": "PDF",
    ".doc": "Word",
    ".docx": "Word",
    ".xls": "Excel",
    ".xlsx": "Excel",
}


async def retry_document_parse(
    session: Session,
    document_id: uuid.UUID,
    embedding_client: EmbeddingClient,
    embedding_model: str,
) -> DocumentItemSchema | None:
    document = session.get(KbDocument, document_id)
    if document is None:
        return None

    source_path = Path(document.source_path) if document.source_path else None
    extension = _extension(document, source_path)
    retry_count = _next_retry_count(session, document.id)

    if extension in UNSUPPORTED_TYPES:
        return _fail_without_processing(
            session,
            document,
            retry_count,
            "unsupported-retry-placeholder",
            f"当前阶段暂不支持解析 {UNSUPPORTED_TYPES[extension]} 文件，请先上传 Markdown 或 TXT 文本文件。",
        )

    if extension not in SUPPORTED_TEXT_EXTENSIONS:
        return _fail_without_processing(
            session,
            document,
            retry_count,
            "manual-retry-text",
            "当前阶段仅支持重新解析 Markdown 或 TXT 文本文件。",
        )

    if source_path is None or not source_path.is_file():
        return _fail_without_processing(
            session,
            document,
            retry_count,
            "manual-retry-text",
            "源文件不存在，无法重新解析。",
        )

    return await _retry_text_document(
        session=session,
        document=document,
        source_path=source_path,
        extension=extension,
        retry_count=retry_count,
        embedding_client=embedding_client,
        embedding_model=embedding_model,
    )


async def _retry_text_document(
    session: Session,
    document: KbDocument,
    source_path: Path,
    extension: str,
    retry_count: int,
    embedding_client: EmbeddingClient,
    embedding_model: str,
) -> DocumentItemSchema:
    started = time.perf_counter()
    task = _start_task(session, document, retry_count)

    try:
        content = source_path.read_bytes().decode("utf-8")
        chunks = chunk_markdown(content, source_title=document.title)
        if not chunks:
            raise ValueError(f"No chunks produced for {source_path.name}")

        embeddings = await embedding_client.embed([chunk.indexed_text for chunk in chunks])
        if len(embeddings) != len(chunks):
            raise ValueError(f"Expected {len(chunks)} embeddings, got {len(embeddings)}")

        session.execute(delete(KbDocumentSegment).where(KbDocumentSegment.document_id == document.id))
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

        metadata = _metadata(document.document_metadata)
        metadata["progress"] = 100
        metadata.pop("retry_placeholder", None)
        metadata.setdefault("source_file_name", document.file_name or source_path.name)
        metadata.setdefault("category", "uncategorized")

        document.status = DocumentStatus.ready
        document.enabled = True
        document.error_message = None
        document.segment_count = len(chunks)
        document.file_type = "markdown" if extension in {".md", ".markdown"} else "txt"
        document.document_metadata = metadata
        task.status = ParseTaskStatus.success
        task.error_message = None
        task.finished_at = datetime.now(UTC)
        task.duration_ms = _duration_ms(started)
        session.commit()
        session.refresh(document)
        return map_document_item(document)
    except Exception as exc:
        _mark_failed(session, document, task, str(exc), started)
        session.refresh(document)
        return map_document_item(document)


def _start_task(session: Session, document: KbDocument, retry_count: int) -> ParseTask:
    metadata = _metadata(document.document_metadata)
    metadata["progress"] = 15
    metadata.pop("retry_placeholder", None)
    document.status = DocumentStatus.processing
    document.enabled = False
    document.error_message = None
    document.document_metadata = metadata
    task = ParseTask(
        document_id=document.id,
        status=ParseTaskStatus.running,
        parser_name="manual-retry-text",
        retry_count=retry_count,
        started_at=datetime.now(UTC),
        task_metadata={"manual_retry": True},
    )
    session.add(task)
    session.flush()
    return task


def _fail_without_processing(
    session: Session,
    document: KbDocument,
    retry_count: int,
    parser_name: str,
    error_message: str,
) -> DocumentItemSchema:
    finished_at = datetime.now(UTC)
    metadata = _metadata(document.document_metadata)
    metadata.pop("progress", None)
    metadata.pop("retry_placeholder", None)
    document.status = DocumentStatus.failed
    document.enabled = False
    document.error_message = error_message
    document.document_metadata = metadata
    session.add(
        ParseTask(
            document_id=document.id,
            status=ParseTaskStatus.failed,
            parser_name=parser_name,
            retry_count=retry_count,
            error_message=error_message,
            started_at=finished_at,
            finished_at=finished_at,
            task_metadata={"manual_retry": True},
        )
    )
    session.commit()
    session.refresh(document)
    return map_document_item(document)


def _mark_failed(
    session: Session,
    document: KbDocument,
    task: ParseTask,
    error_message: str,
    started: float,
) -> None:
    metadata = _metadata(document.document_metadata)
    metadata.pop("progress", None)
    metadata.pop("retry_placeholder", None)
    document.status = DocumentStatus.failed
    document.enabled = False
    document.error_message = error_message
    document.document_metadata = metadata
    task.status = ParseTaskStatus.failed
    task.error_message = error_message
    task.finished_at = datetime.now(UTC)
    task.duration_ms = _duration_ms(started)
    try:
        session.commit()
    except Exception:
        rollback = getattr(session, "rollback", None)
        if rollback is not None:
            rollback()
        raise


def _extension(document: KbDocument, source_path: Path | None) -> str:
    if source_path is not None and source_path.suffix:
        return source_path.suffix.lower()
    if document.file_name:
        suffix = Path(document.file_name).suffix.lower()
        if suffix:
            return suffix
    file_type = (document.file_type or "").lower()
    if file_type in {"markdown", "md"}:
        return ".md"
    if file_type == "txt":
        return ".txt"
    if file_type in {"pdf", "doc", "docx", "xls", "xlsx"}:
        return f".{file_type}"
    return ""


def _metadata(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _next_retry_count(session: Session, document_id: uuid.UUID) -> int:
    retry_counts = list(
        session.execute(
            select(ParseTask.retry_count).where(ParseTask.document_id == document_id)
        ).scalars()
    )
    return max([0, *retry_counts]) + 1


def _duration_ms(started: float) -> int:
    return max(0, int((time.perf_counter() - started) * 1000))
```

- [ ] **Step 4: Run tests**

Run:

```powershell
backend\.venv\Scripts\python.exe -c "import sys, pathlib, pytest; root=pathlib.Path.cwd(); sys.path[:0]=[str(root), str(root / 'backend')]; raise SystemExit(pytest.main(['backend/tests/test_document_parse_workflow.py', '-q']))"
```

Expected: pass. If the fake session needs a small adjustment for `delete(...)`, keep it in the same test file and rerun.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/services/document_parsing.py backend/tests/test_document_parse_workflow.py
git commit -m "feat: add document retry parsing"
```

### Task 2: Wire Retry Endpoint to the Parser

**Files:**
- Modify: `backend/app/api/documents.py`
- Modify: `backend/app/services/document_management.py`
- Modify: `backend/tests/test_documents_api.py`
- Modify: `backend/tests/test_document_management.py`

- [ ] **Step 1: Update API tests**

In `backend/tests/test_documents_api.py`, replace the retry test fake manager with parser dependency override:

```python
def test_retry_document_endpoint_returns_parser_item():
    app = create_app()
    document_id = uuid.uuid4()
    retry_item = DocumentItemSchema(
        id=document_id,
        name="manual.md",
        type="Markdown",
        category="manual",
        parseStatus="ready",
        enableStatus="enabled",
        updatedAt="2026-06-30 10:00:00",
        failureReason=None,
        progress=100,
    )

    from app.api.documents import get_document_parser

    class FakeParser:
        async def retry_parse(self, target_id):
            assert target_id == document_id
            return retry_item

    app.dependency_overrides[get_document_parser] = lambda: FakeParser()
    client = TestClient(app)

    response = client.post(f"/api/documents/{document_id}/retry")

    assert response.status_code == 200
    assert response.json()["parseStatus"] == "ready"
```

Add:

```python
def test_retry_document_endpoint_returns_404_for_missing_document():
    app = create_app()
    document_id = uuid.uuid4()

    from app.api.documents import get_document_parser

    class FakeParser:
        async def retry_parse(self, target_id):
            assert target_id == document_id
            return None

    app.dependency_overrides[get_document_parser] = lambda: FakeParser()
    client = TestClient(app)

    response = client.post(f"/api/documents/{document_id}/retry")

    assert response.status_code == 404
```

- [ ] **Step 2: Run API tests and confirm failure**

Run:

```powershell
backend\.venv\Scripts\python.exe -c "import sys, pathlib, pytest; root=pathlib.Path.cwd(); sys.path[:0]=[str(root), str(root / 'backend')]; raise SystemExit(pytest.main(['backend/tests/test_documents_api.py::test_retry_document_endpoint_returns_parser_item', '-q']))"
```

Expected: failure because `get_document_parser` does not exist.

- [ ] **Step 3: Wire parser dependency in API**

In `backend/app/api/documents.py`:

- Remove `retry_document_parse` import from `app.services.document_management`.
- Add:

```python
from app.services.document_parsing import retry_document_parse
```

Add after `DocumentUploader`:

```python
class DocumentParser:
    def __init__(self, session: Session):
        self._session = session

    async def retry_parse(self, document_id: uuid.UUID) -> DocumentItemSchema | None:
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
            return await retry_document_parse(
                session=self._session,
                document_id=document_id,
                embedding_client=embedding_client,
                embedding_model=settings.embedding_model,
            )
```

Add:

```python
def get_document_parser(
    session: Session = Depends(get_db_session),
) -> DocumentParser:
    return DocumentParser(session)
```

Change retry endpoint to:

```python
@router.post("/{document_id}/retry", response_model=DocumentItemSchema)
async def retry_document(
    document_id: uuid.UUID,
    parser: DocumentParser = Depends(get_document_parser),
) -> DocumentItemSchema:
    document = await parser.retry_parse(document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return document
```

- [ ] **Step 4: Remove placeholder retry service and tests**

In `backend/app/services/document_management.py`:

- Delete `retry_document_parse()`.
- Delete `_next_retry_count()`.
- Remove `ParseTask` and `ParseTaskStatus` imports.

In `backend/tests/test_document_management.py`:

- Remove placeholder retry tests:
  - `test_retry_document_parse_skips_duplicate_placeholder_task`
  - `test_retry_document_parse_adds_one_placeholder_task_on_first_retry`
  - `test_retry_document_parse_increments_retry_count_from_existing_tasks`
  - `test_retry_document_parse_returns_none_for_missing_document`
- Remove unused `ParseTask`, `ParseTaskStatus`, and `retry_document_parse` imports.

- [ ] **Step 5: Run backend tests**

Run:

```powershell
backend\.venv\Scripts\python.exe -c "import sys, pathlib, pytest; root=pathlib.Path.cwd(); sys.path[:0]=[str(root), str(root / 'backend')]; raise SystemExit(pytest.main(['backend/tests/test_document_parse_workflow.py', 'backend/tests/test_documents_api.py', 'backend/tests/test_document_management.py', '-q']))"
```

Expected: pass.

- [ ] **Step 6: Commit**

```powershell
git add backend/app/api/documents.py backend/app/services/document_management.py backend/tests/test_documents_api.py backend/tests/test_document_management.py
git commit -m "feat: wire document retry endpoint"
```

### Task 3: Frontend Retry Feedback

**Files:**
- Modify: `frontend/src/stores/documents.ts`
- Modify: `frontend/src/documents/documentStore.contract.ts`
- Modify: `frontend/src/views/DocumentManageView.vue`

- [ ] **Step 1: Improve retry notice**

In `frontend/src/stores/documents.ts`, replace retry success notice:

```typescript
      lastNotice.value = "已提交重新解析请求，文档已进入解析队列。";
```

with:

```typescript
      if (updated.parseStatus === "ready") {
        lastNotice.value = "文档已重新解析并完成入库。";
      } else if (updated.parseStatus === "failed") {
        lastNotice.value = `文档重新解析失败：${updated.failureReason ?? "请查看失败原因"}`;
      } else {
        lastNotice.value = "文档已进入解析流程，稍后刷新状态。";
      }
```

- [ ] **Step 2: Add lightweight processing refresh**

In `frontend/src/stores/documents.ts`, add:

```typescript
  const hasProcessingDocuments = computed(() =>
    documents.value.some((document) => document.parseStatus === "processing")
  );
```

Add:

```typescript
  async function refreshProcessingDocuments() {
    if (isLoading.value || isUploading.value || hasPendingDocumentActions.value) {
      return;
    }

    await loadDocuments();
  }
```

Return both:

```typescript
    hasProcessingDocuments,
    refreshProcessingDocuments,
```

- [ ] **Step 3: Update contract**

In `frontend/src/documents/documentStore.contract.ts`, add:

```typescript
void store.hasProcessingDocuments;
void store.refreshProcessingDocuments();
```

- [ ] **Step 4: Add simple polling in view**

In `frontend/src/views/DocumentManageView.vue`, change import:

```typescript
import { computed, onMounted, ref } from "vue";
```

to:

```typescript
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
```

Add after `uploadInput`:

```typescript
let processingRefreshTimer: number | undefined;

function stopProcessingRefresh() {
  if (processingRefreshTimer !== undefined) {
    window.clearInterval(processingRefreshTimer);
    processingRefreshTimer = undefined;
  }
}

function startProcessingRefresh() {
  if (processingRefreshTimer !== undefined) {
    return;
  }

  processingRefreshTimer = window.setInterval(() => {
    if (documentStore.hasProcessingDocuments) {
      void documentStore.refreshProcessingDocuments();
    } else {
      stopProcessingRefresh();
    }
  }, 5000);
}
```

Add after `onMounted`:

```typescript
watch(
  () => documentStore.hasProcessingDocuments,
  (hasProcessingDocuments) => {
    if (hasProcessingDocuments) {
      startProcessingRefresh();
    } else {
      stopProcessingRefresh();
    }
  }
);

onUnmounted(() => {
  stopProcessingRefresh();
});
```

- [ ] **Step 5: Disable retry while processing**

In `frontend/src/views/DocumentManageView.vue`, change failed-row retry button disabled condition to:

```vue
:disabled="documentStore.isDocumentPending(document.id) || document.parseStatus === 'processing'"
```

If the retry button only renders for `failed`, this change is harmless and future-proof.

- [ ] **Step 6: Run frontend build**

Run:

```powershell
npm run build
```

with workdir:

```text
D:\桌面\文件\operation_project\frontend
```

Expected: build passes.

- [ ] **Step 7: Commit**

```powershell
git add frontend/src/stores/documents.ts frontend/src/documents/documentStore.contract.ts frontend/src/views/DocumentManageView.vue
git commit -m "feat: improve document retry feedback"
```

### Task 4: Final Verification

**Files:**
- No new files unless verification exposes defects.

- [ ] **Step 1: Run backend retry/upload/document tests**

Run:

```powershell
backend\.venv\Scripts\python.exe -c "import sys, pathlib, pytest; root=pathlib.Path.cwd(); sys.path[:0]=[str(root), str(root / 'backend')]; raise SystemExit(pytest.main(['backend/tests/test_document_parse_workflow.py', 'backend/tests/test_document_uploads.py', 'backend/tests/test_documents_api.py', 'backend/tests/test_document_management.py', '-q']))"
```

Expected: pass.

- [ ] **Step 2: Run frontend build**

Run:

```powershell
npm run build
```

with workdir:

```text
D:\桌面\文件\operation_project\frontend
```

Expected: build passes. Existing Vite large chunk warning is acceptable.

- [ ] **Step 3: Optional manual smoke**

Only if local DB and embedding provider config are available:

1. Start backend.
2. Upload Markdown/TXT from the document page.
3. Click retry.
4. Confirm returned row becomes ready or failed with a real reason.
5. Upload PDF and click retry.
6. Confirm it stays failed with unsupported parser reason.

- [ ] **Step 4: Final review**

Run one final read-only code review over the changed backend and frontend files.

Expected: reviewer returns `APPROVED`.

## Self-Review

- Spec coverage: Covers real Markdown/TXT retry, unsupported retry failure, task records, API wiring, frontend notices, and verification.
- Scope check: Reduced to four tasks. No background worker, no PDF parser, no broad UI redesign.
- Placeholder scan: Unsupported formats are explicit behavior, not a TODO.
- Type consistency: Backend public retry function is `retry_document_parse(...)`; frontend additions are `hasProcessingDocuments` and `refreshProcessingDocuments`.
