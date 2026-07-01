# Document Storage MarkItDown Floating Detail Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a document storage and detail-management loop where uploaded originals are preserved on disk, MarkItDown-derived Markdown is tracked separately, and clicking a document opens a closable floating detail panel.

**Architecture:** Keep the work in two vertical slices: first add a real document detail API and floating panel using existing data, then extend storage/parsing to preserve originals and generated Markdown. The database stores metadata and paths; files live under `data/knowledge_base`, and RAG still uses database segments and embeddings.

**Tech Stack:** FastAPI, SQLAlchemy 2.0, Alembic, pytest, MarkItDown, Vue 3, Pinia, TypeScript, Vite.

---

## File Structure

- `backend/app/schemas/documents.py`
  - Add detail response schemas for parse tasks and segment previews.
- `backend/app/services/document_management.py`
  - Add `get_document_detail(...)`, mapping parse tasks and segment previews.
- `backend/app/api/documents.py`
  - Add `GET /api/documents/{document_id}` and manager method.
- `backend/app/models/rag.py`
  - Add `markdown_path` to `KbDocument`.
- `backend/alembic/versions/20260701_0004_add_document_markdown_path.py`
  - Add/drop nullable `markdown_path` column.
- `backend/app/core/config.py`
  - Add knowledge-base storage directories and keep relative path resolution.
- `backend/app/services/document_conversion.py`
  - New small conversion boundary: original file to Markdown file.
- `backend/app/services/document_uploads.py`
  - Save originals under `originals`, save Markdown output under `markdown/generated`.
- `backend/app/services/document_parsing.py`
  - Retry from original source, regenerate Markdown, then rebuild segments.
- `backend/requirements.txt`
  - Add `markitdown`.
- `frontend/src/types/document.ts`
  - Add detail, parse task, and segment preview types.
- `frontend/src/api/documents.ts`
  - Add `getDocumentDetail(...)`.
- `frontend/src/stores/documents.ts`
  - Add selected detail state and refresh actions.
- `frontend/src/components/documents/DocumentDetailFloatingPanel.vue`
  - New floating panel component.
- `frontend/src/views/DocumentManageView.vue`
  - Open/close floating panel, row highlight, universal parse button.
- `frontend/src/styles/main.css`
  - Floating panel, selected row, and responsive adjustments.
- Tests:
  - `backend/tests/test_document_detail.py`
  - `backend/tests/test_document_conversion.py`
  - update existing document upload/parse/API tests.

## Implementation Tasks

### Task 1: Backend Document Detail API

**Files:**
- Modify: `backend/app/schemas/documents.py`
- Modify: `backend/app/services/document_management.py`
- Modify: `backend/app/api/documents.py`
- Create: `backend/tests/test_document_detail.py`
- Modify: `backend/tests/test_documents_api.py`

- [ ] **Step 1: Add failing service tests for document detail**

Create `backend/tests/test_document_detail.py` with tests that construct a fake session and assert detail mapping returns:

```python
import uuid
from datetime import UTC, datetime

from app.models.rag import (
    DocumentStatus,
    KbDocument,
    KbDocumentSegment,
    ParseTask,
    ParseTaskStatus,
)


class _ScalarResult:
    def __init__(self, values):
        self._values = values

    def scalars(self):
        return iter(self._values)


class _DetailSession:
    def __init__(self, document, tasks=None, segments=None):
        self.document = document
        self.tasks = tasks or []
        self.segments = segments or []
        self.executed = []

    def get(self, model_type, item_id):
        if model_type is KbDocument and self.document is not None and self.document.id == item_id:
            return self.document
        return None

    def execute(self, statement):
        self.executed.append(statement)
        text = str(statement)
        if "parse_task" in text:
            return _ScalarResult(self.tasks)
        return _ScalarResult(self.segments)


def test_get_document_detail_returns_tasks_and_segment_preview():
    from app.services.document_management import get_document_detail

    document_id = uuid.uuid4()
    document = KbDocument(
        id=document_id,
        title="Manual",
        source_path="data/knowledge_base/originals/hash_manual.md",
        markdown_path="data/knowledge_base/markdown/generated/hash_manual.md",
        file_name="manual.md",
        file_type="markdown",
        file_sha256="a" * 64,
        status=DocumentStatus.ready,
        enabled=True,
        segment_count=2,
        document_metadata={"category": "manual", "source_file_name": "manual.md"},
        updated_at=datetime(2026, 7, 1, 9, 30, tzinfo=UTC),
    )
    task = ParseTask(
        id=uuid.uuid4(),
        document_id=document_id,
        status=ParseTaskStatus.success,
        parser_name="manual-retry-text",
        retry_count=1,
        duration_ms=123,
        started_at=datetime(2026, 7, 1, 9, 29, tzinfo=UTC),
        finished_at=datetime(2026, 7, 1, 9, 30, tzinfo=UTC),
    )
    segment = KbDocumentSegment(
        id=uuid.uuid4(),
        document_id=document_id,
        chunk_index=0,
        heading_path="Manual > Safety",
        section_title="Safety",
        raw_text="Safety first",
        clean_text="Safety first",
        indexed_text="Safety first",
        keyword_text="safety first",
        char_count=12,
        embedding_model="test-embedding",
        embedding=[0.1, 0.2],
        segment_metadata={"level": 2},
    )
    session = _DetailSession(document=document, tasks=[task], segments=[segment])

    detail = get_document_detail(session, document_id)

    assert detail is not None
    assert detail.item.id == document_id
    assert detail.sourcePath == "data/knowledge_base/originals/hash_manual.md"
    assert detail.markdownPath == "data/knowledge_base/markdown/generated/hash_manual.md"
    assert detail.fileSha256 == "a" * 64
    assert detail.segmentCount == 2
    assert detail.latestTask is not None
    assert detail.latestTask.parserName == "manual-retry-text"
    assert detail.recentTasks[0].status == "success"
    assert detail.segmentPreview[0].headingPath == "Manual > Safety"
    assert detail.segmentPreview[0].hasEmbedding is True


def test_get_document_detail_returns_none_for_missing_document():
    from app.services.document_management import get_document_detail

    assert get_document_detail(_DetailSession(document=None), uuid.uuid4()) is None
```

- [ ] **Step 2: Run the new tests and confirm failure**

Run:

```powershell
backend\.venv\Scripts\python.exe -c "import sys, pathlib, pytest; root=pathlib.Path.cwd(); sys.path[:0]=[str(root), str(root / 'backend')]; raise SystemExit(pytest.main(['backend/tests/test_document_detail.py', '-q']))"
```

Expected: fail because `markdown_path`, schemas, and `get_document_detail` do not exist.

- [ ] **Step 3: Add backend schemas**

In `backend/app/schemas/documents.py`, add:

```python
class ParseTaskSummarySchema(BaseModel):
    id: uuid.UUID
    status: Literal["pending", "running", "success", "failed"]
    parserName: str | None
    retryCount: int
    durationMs: int | None
    errorMessage: str | None
    startedAt: str | None
    finishedAt: str | None


class SegmentPreviewSchema(BaseModel):
    id: uuid.UUID
    chunkIndex: int
    headingPath: str | None
    sectionTitle: str | None
    charCount: int
    hasEmbedding: bool


class DocumentDetailSchema(BaseModel):
    item: DocumentItemSchema
    sourcePath: str | None
    markdownPath: str | None
    fileSha256: str | None
    segmentCount: int
    metadata: dict
    latestTask: ParseTaskSummarySchema | None
    recentTasks: list[ParseTaskSummarySchema]
    segmentPreview: list[SegmentPreviewSchema]
```

- [ ] **Step 4: Add model field**

In `backend/app/models/rag.py`, add to `KbDocument` after `source_path`:

```python
    markdown_path: Mapped[str | None] = mapped_column(Text)
```

- [ ] **Step 5: Implement detail mapping**

In `backend/app/services/document_management.py`, import `KbDocumentSegment`, `ParseTask`, and new schemas, then add:

```python
def get_document_detail(session: Session, document_id: uuid.UUID) -> DocumentDetailSchema | None:
    document = session.get(KbDocument, document_id)
    if document is None:
        return None

    tasks = list(
        session.execute(
            select(ParseTask)
            .where(ParseTask.document_id == document_id)
            .order_by(ParseTask.started_at.desc().nullslast(), ParseTask.created_at.desc())
            .limit(5)
        ).scalars()
    )
    segments = list(
        session.execute(
            select(KbDocumentSegment)
            .where(KbDocumentSegment.document_id == document_id)
            .order_by(KbDocumentSegment.chunk_index.asc())
            .limit(3)
        ).scalars()
    )
    task_summaries = [_map_parse_task_summary(task) for task in tasks]
    return DocumentDetailSchema(
        item=map_document_item(document),
        sourcePath=document.source_path,
        markdownPath=document.markdown_path,
        fileSha256=document.file_sha256,
        segmentCount=document.segment_count,
        metadata=_metadata(document.document_metadata),
        latestTask=task_summaries[0] if task_summaries else None,
        recentTasks=task_summaries,
        segmentPreview=[_map_segment_preview(segment) for segment in segments],
    )


def _format_optional_datetime(value: Any) -> str | None:
    return value.strftime("%Y-%m-%d %H:%M:%S") if value is not None else None


def _map_parse_task_summary(task: ParseTask) -> ParseTaskSummarySchema:
    return ParseTaskSummarySchema(
        id=task.id,
        status=task.status.value,
        parserName=task.parser_name,
        retryCount=task.retry_count,
        durationMs=task.duration_ms,
        errorMessage=task.error_message,
        startedAt=_format_optional_datetime(task.started_at),
        finishedAt=_format_optional_datetime(task.finished_at),
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
```

- [ ] **Step 6: Wire API endpoint**

In `backend/app/api/documents.py`, import `DocumentDetailSchema` and `get_document_detail`, add `DocumentManager.get_detail`, then add before the patch/retry routes:

```python
@router.get("/{document_id}", response_model=DocumentDetailSchema)
async def get_document(
    document_id: uuid.UUID,
    manager: DocumentManager = Depends(get_document_manager),
) -> DocumentDetailSchema:
    detail = manager.get_detail(document_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return detail
```

- [ ] **Step 7: Add API tests**

In `backend/tests/test_documents_api.py`, add tests that override `get_document_manager` with a fake manager exposing `get_detail`, then assert `GET /api/documents/{id}` returns 200 for a fake `DocumentDetailSchema` and 404 for `None`.

- [ ] **Step 8: Run backend detail/API tests**

Run:

```powershell
backend\.venv\Scripts\python.exe -c "import sys, pathlib, pytest; root=pathlib.Path.cwd(); sys.path[:0]=[str(root), str(root / 'backend')]; raise SystemExit(pytest.main(['backend/tests/test_document_detail.py', 'backend/tests/test_documents_api.py', '-q']))"
```

Expected: pass.

- [ ] **Step 9: Commit**

```powershell
git add backend/app/schemas/documents.py backend/app/models/rag.py backend/app/services/document_management.py backend/app/api/documents.py backend/tests/test_document_detail.py backend/tests/test_documents_api.py
git commit -m "feat: add document detail api"
```

### Task 2: Frontend Floating Detail Panel

**Files:**
- Modify: `frontend/src/types/document.ts`
- Modify: `frontend/src/api/documents.ts`
- Modify: `frontend/src/stores/documents.ts`
- Create: `frontend/src/components/documents/DocumentDetailFloatingPanel.vue`
- Modify: `frontend/src/views/DocumentManageView.vue`
- Modify: `frontend/src/styles/main.css`
- Modify: `frontend/src/documents/documentStore.contract.ts`

- [ ] **Step 1: Add frontend types and API client**

In `frontend/src/types/document.ts`, add `ParseTaskSummary`, `SegmentPreview`, and `DocumentDetail` matching backend response fields. In `frontend/src/api/documents.ts`, add:

```typescript
export async function getDocumentDetail(id: string): Promise<DocumentDetail> {
  const response = await fetch(`/api/documents/${id}`);
  if (!response.ok) {
    throw new Error(await getDocumentErrorMessage(response));
  }
  return (await response.json()) as DocumentDetail;
}
```

- [ ] **Step 2: Extend Pinia store**

In `frontend/src/stores/documents.ts`, import `getDocumentDetail` and `DocumentDetail`, then add refs:

```typescript
  const selectedDocumentId = ref<string | null>(null);
  const selectedDocumentDetail = ref<DocumentDetail | null>(null);
  const isDetailOpen = ref(false);
  const isDetailLoading = ref(false);
```

Add methods:

```typescript
  async function loadDocumentDetail(id: string) {
    isDetailLoading.value = true;
    errorMessage.value = "";
    try {
      selectedDocumentDetail.value = await getDocumentDetail(id);
    } catch (error) {
      errorMessage.value = error instanceof Error ? error.message : "文档详情加载失败";
    } finally {
      isDetailLoading.value = false;
    }
  }

  async function openDocumentDetail(id: string) {
    selectedDocumentId.value = id;
    isDetailOpen.value = true;
    await loadDocumentDetail(id);
  }

  function closeDocumentDetail() {
    isDetailOpen.value = false;
    selectedDocumentId.value = null;
    selectedDocumentDetail.value = null;
  }

  async function refreshSelectedDocumentDetail() {
    if (!selectedDocumentId.value || !isDetailOpen.value) {
      return;
    }
    await loadDocumentDetail(selectedDocumentId.value);
  }
```

After `toggleDocumentEnabled` and `retryParse` succeed, call `await refreshSelectedDocumentDetail()` when the changed id equals `selectedDocumentId.value`.

- [ ] **Step 3: Add store contract references**

In `frontend/src/documents/documentStore.contract.ts`, reference the new fields and methods:

```typescript
void store.selectedDocumentId;
void store.selectedDocumentDetail;
void store.isDetailOpen;
void store.isDetailLoading;
void store.openDocumentDetail("doc-inverter-manual");
void store.closeDocumentDetail();
void store.loadDocumentDetail("doc-inverter-manual");
void store.refreshSelectedDocumentDetail();
```

- [ ] **Step 4: Create floating panel component**

Create `frontend/src/components/documents/DocumentDetailFloatingPanel.vue`. Props:

```typescript
const props = defineProps<{
  detail: DocumentDetail | null;
  loading: boolean;
  pending: boolean;
}>();

const emit = defineEmits<{
  close: [];
  toggleEnabled: [id: string];
  retryParse: [id: string];
}>();
```

Template should include:
- close button with accessible label
- loading state
- document title/status/type
- enable/retry buttons
- file info
- parse info
- recent task list
- segment preview list

- [ ] **Step 5: Wire panel into the document page**

In `frontend/src/views/DocumentManageView.vue`:
- import `DocumentDetailFloatingPanel`
- add `onKeydown` listener for Escape
- add a row click handler that opens detail unless the click came from a button/select/input/link
- add selected-row class when `documentStore.selectedDocumentId === document.id`
- render `<DocumentDetailFloatingPanel />` near the end of `<main>`
- keep existing failure dialog until the detail panel fully replaces it in a later cleanup

- [ ] **Step 6: Make parse button visible for all non-processing documents**

Replace the `v-if="document.parseStatus === 'failed'"` retry button with a button that renders for all rows, disabled while processing or pending. Use helper text:

```typescript
function parseActionLabel(document: DocumentItem) {
  if (documentStore.isDocumentPending(document.id)) {
    return "处理中";
  }
  if (document.parseStatus === "ready") {
    return "重新解析";
  }
  if (document.parseStatus === "failed") {
    return "重试解析";
  }
  if (document.parseStatus === "processing") {
    return "解析中";
  }
  return "开始解析";
}
```

Before calling retry, use `window.confirm("确认重新解析该文档？这会重建文档分段。")`.

- [ ] **Step 7: Add CSS**

In `frontend/src/styles/main.css`, add classes for:
- `.document-detail-floating-panel`
- `.document-detail-backdropless`
- `.document-table tr.selected`
- `.document-detail-section`
- `.document-detail-task`
- `.document-detail-segment`

Panel should be fixed, right aligned, no full-screen mask:

```css
.document-detail-floating-panel {
  position: fixed;
  top: 96px;
  right: 24px;
  bottom: 24px;
  width: min(460px, calc(100vw - 32px));
  z-index: 30;
  overflow: auto;
}
```

- [ ] **Step 8: Run frontend build**

Run:

```powershell
npm run build
```

Workdir:

```text
D:\桌面\文件\operation_project\frontend
```

Expected: pass, with existing Vite chunk warning allowed.

- [ ] **Step 9: Commit**

```powershell
git add frontend/src/types/document.ts frontend/src/api/documents.ts frontend/src/stores/documents.ts frontend/src/documents/documentStore.contract.ts frontend/src/components/documents/DocumentDetailFloatingPanel.vue frontend/src/views/DocumentManageView.vue frontend/src/styles/main.css
git commit -m "feat: add document floating detail panel"
```

### Task 3: Knowledge Base Storage Directories and Migration

**Files:**
- Modify: `backend/app/core/config.py`
- Create: `backend/alembic/versions/20260701_0004_add_document_markdown_path.py`
- Modify: `backend/tests/test_document_uploads.py`
- Modify: `backend/tests/test_document_parse_workflow.py`

- [ ] **Step 1: Add config test expectations to existing upload tests**

Update upload tests to pass separate `original_storage_dir` and `markdown_storage_dir` once the service signature changes. Expected paths should be under:

```text
data/knowledge_base/originals
data/knowledge_base/markdown/generated
```

- [ ] **Step 2: Add settings fields**

In `backend/app/core/config.py`, replace the upload-only storage default with:

```python
    knowledge_base_dir: Path = PROJECT_ROOT / "data" / "knowledge_base"
    original_storage_dir: Path | None = None
    markdown_storage_dir: Path | None = None
```

Add properties or validators so defaults resolve to:

```python
settings.knowledge_base_dir / "originals"
settings.knowledge_base_dir / "markdown" / "generated"
```

Keep `upload_storage_dir` as a compatibility property returning `original_storage_dir` if other code still imports it.

- [ ] **Step 3: Add Alembic migration**

Create `backend/alembic/versions/20260701_0004_add_document_markdown_path.py`:

```python
from alembic import op
import sqlalchemy as sa

revision = "20260701_0004"
down_revision = "20260624_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("kb_document", sa.Column("markdown_path", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("kb_document", "markdown_path")
```

- [ ] **Step 4: Run backend tests affected by model/config**

Run:

```powershell
backend\.venv\Scripts\python.exe -c "import sys, pathlib, pytest; root=pathlib.Path.cwd(); sys.path[:0]=[str(root), str(root / 'backend')]; raise SystemExit(pytest.main(['backend/tests/test_document_uploads.py', 'backend/tests/test_document_parse_workflow.py', 'backend/tests/test_document_detail.py', '-q']))"
```

Expected: fail until upload/parse service signatures are updated.

- [ ] **Step 5: Commit**

Commit only after Task 4 makes tests pass:

```powershell
git add backend/app/core/config.py backend/alembic/versions/20260701_0004_add_document_markdown_path.py backend/tests/test_document_uploads.py backend/tests/test_document_parse_workflow.py
git commit -m "feat: add knowledge base document storage paths"
```

### Task 4: MarkItDown Conversion and Unified Parse Flow

**Files:**
- Create: `backend/app/services/document_conversion.py`
- Modify: `backend/app/services/document_uploads.py`
- Modify: `backend/app/services/document_parsing.py`
- Modify: `backend/app/api/documents.py`
- Modify: `backend/requirements.txt`
- Create: `backend/tests/test_document_conversion.py`
- Modify: `backend/tests/test_document_uploads.py`
- Modify: `backend/tests/test_document_parse_workflow.py`
- Modify: `backend/tests/test_documents_api.py`

- [ ] **Step 1: Add conversion service tests**

Create `backend/tests/test_document_conversion.py` with tests for:
- text files write Markdown content to target path
- converter failure raises readable `DocumentConversionError`
- unsafe or missing source path fails before conversion

Use a fake converter object instead of invoking real MarkItDown in unit tests.

- [ ] **Step 2: Implement conversion service boundary**

Create `backend/app/services/document_conversion.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


class DocumentConversionError(RuntimeError):
    pass


class MarkdownConverter(Protocol):
    def convert(self, source_path: Path) -> str:
        ...


@dataclass(frozen=True)
class MarkItDownConverter:
    def convert(self, source_path: Path) -> str:
        from markitdown import MarkItDown

        result = MarkItDown().convert(str(source_path))
        text_content = getattr(result, "text_content", None)
        if not isinstance(text_content, str) or not text_content.strip():
            raise DocumentConversionError("MarkItDown did not produce Markdown text")
        return text_content


TEXT_EXTENSIONS = {".md", ".markdown", ".txt"}


def convert_document_to_markdown(
    source_path: Path,
    markdown_path: Path,
    converter: MarkdownConverter | None = None,
) -> Path:
    if not source_path.is_file():
        raise DocumentConversionError("源文件不存在，无法转换为 Markdown")
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    extension = source_path.suffix.lower()
    try:
        if extension in TEXT_EXTENSIONS:
            markdown_text = source_path.read_bytes().decode("utf-8")
        else:
            markdown_text = (converter or MarkItDownConverter()).convert(source_path)
    except UnicodeDecodeError as exc:
        raise DocumentConversionError("文本文件必须使用 UTF-8 编码") from exc
    except DocumentConversionError:
        raise
    except Exception as exc:
        raise DocumentConversionError(str(exc)) from exc

    markdown_path.write_text(markdown_text, encoding="utf-8")
    return markdown_path
```

- [ ] **Step 3: Add dependency**

Append to `backend/requirements.txt`:

```text
markitdown
```

- [ ] **Step 4: Update upload service signature**

Change `upload_document_file(...)` to accept:

```python
original_storage_dir: Path,
markdown_storage_dir: Path,
converter: MarkdownConverter | None = None,
```

Save original file to `original_storage_dir / f"{sha256}_{safe_name}"`.
Set Markdown path to `markdown_storage_dir / f"{sha256}_{Path(safe_name).stem}.md"`.

- [ ] **Step 5: Upload now converts before import**

For all allowed extensions:
- save original
- call `convert_document_to_markdown(saved_path, markdown_path, converter=converter)`
- import chunks from Markdown text
- set:

```python
document.source_path = str(saved_path)
document.markdown_path = str(markdown_path)
document.file_name = safe_name
document.file_type = file_extension(safe_name).lstrip(".")
```

If conversion fails, create a failed document record with `source_path` set, `markdown_path=None`, `parser_name="markitdown-upload"`, and the conversion error message.

- [ ] **Step 6: Update retry parser**

In `retry_document_parse(...)`, for every existing document:
- resolve `source_path`
- compute or reuse `markdown_path`
- call `convert_document_to_markdown(...)`
- read Markdown text from `markdown_path`
- chunk and embed
- replace segments transactionally
- set `document.markdown_path`
- use `parser_name="markitdown-retry"` for converted formats and `"manual-retry-text"` for text files

Keep rollback behavior for failures after segment deletion begins.

- [ ] **Step 7: Update API dependencies**

In `backend/app/api/documents.py`, pass:

```python
original_storage_dir=settings.original_storage_dir
markdown_storage_dir=settings.markdown_storage_dir
```

to upload service. For retry, pass `markdown_storage_dir=settings.markdown_storage_dir`.

- [ ] **Step 8: Update tests**

Update upload and retry tests to assert:
- original path contains `originals`
- Markdown path contains `markdown/generated`
- failed conversion creates failed document and failed ParseTask
- successful converted upload/retry records `markdown_path`

- [ ] **Step 9: Run backend tests**

Run:

```powershell
backend\.venv\Scripts\python.exe -c "import sys, pathlib, pytest; root=pathlib.Path.cwd(); sys.path[:0]=[str(root), str(root / 'backend')]; raise SystemExit(pytest.main(['backend/tests/test_document_conversion.py', 'backend/tests/test_document_uploads.py', 'backend/tests/test_document_parse_workflow.py', 'backend/tests/test_documents_api.py', 'backend/tests/test_document_detail.py', 'backend/tests/test_document_management.py', '-q']))"
```

Expected: pass.

- [ ] **Step 10: Commit**

```powershell
git add backend/app/services/document_conversion.py backend/app/services/document_uploads.py backend/app/services/document_parsing.py backend/app/api/documents.py backend/requirements.txt backend/tests/test_document_conversion.py backend/tests/test_document_uploads.py backend/tests/test_document_parse_workflow.py backend/tests/test_documents_api.py
git commit -m "feat: convert uploaded documents to markdown"
```

### Task 5: Left Panel Linkage

**Files:**
- Modify: `frontend/src/stores/documents.ts`
- Modify: `frontend/src/views/DocumentManageView.vue`
- Modify: `frontend/src/types/document.ts`
- Modify: `frontend/src/styles/main.css`

- [ ] **Step 1: Add virtual file tree model**

In `frontend/src/types/document.ts`, add:

```typescript
export type DocumentTreeNodeKind = "all" | "status" | "category" | "type";

export interface DocumentTreeNode {
  id: string;
  kind: DocumentTreeNodeKind;
  label: string;
  count: number;
  value: string;
}
```

- [ ] **Step 2: Add computed tree nodes**

In `frontend/src/stores/documents.ts`, add computed groups for:
- all
- uploaded/processing/ready/failed
- enabled/disabled
- each category
- each document type

Selecting a node should update existing filters and reset page.

- [ ] **Step 3: Close floating panel when selected document leaves filtered list**

Add a watcher in `DocumentManageView.vue`:

```typescript
watch(
  () => [documentStore.filteredDocuments, documentStore.selectedDocumentId] as const,
  ([documents, selectedId]) => {
    if (!selectedId) {
      return;
    }
    if (!documents.some((document) => document.id === selectedId)) {
      documentStore.closeDocumentDetail();
    }
  }
);
```

- [ ] **Step 4: Replace left category-only list with virtual file tree**

Render tree nodes in left panel. Keep counts. The selected node should be highlighted.

- [ ] **Step 5: Run frontend build**

Run:

```powershell
npm run build
```

Workdir:

```text
D:\桌面\文件\operation_project\frontend
```

Expected: pass.

- [ ] **Step 6: Commit**

```powershell
git add frontend/src/stores/documents.ts frontend/src/views/DocumentManageView.vue frontend/src/types/document.ts frontend/src/styles/main.css
git commit -m "feat: link document file tree filters"
```

### Task 6: Final Verification

**Files:**
- No new files unless defects are found.

- [ ] **Step 1: Install backend dependency if needed**

If `import markitdown` fails, install dependencies:

```powershell
backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
```

- [ ] **Step 2: Run backend tests**

Run:

```powershell
backend\.venv\Scripts\python.exe -c "import sys, pathlib, pytest; root=pathlib.Path.cwd(); sys.path[:0]=[str(root), str(root / 'backend')]; raise SystemExit(pytest.main(['backend/tests/test_document_conversion.py', 'backend/tests/test_document_uploads.py', 'backend/tests/test_document_parse_workflow.py', 'backend/tests/test_documents_api.py', 'backend/tests/test_document_detail.py', 'backend/tests/test_document_management.py', '-q']))"
```

Expected: pass.

- [ ] **Step 3: Run frontend build**

Run:

```powershell
npm run build
```

Workdir:

```text
D:\桌面\文件\operation_project\frontend
```

Expected: pass. Existing Vite chunk warning is acceptable.

- [ ] **Step 4: Manual smoke**

With backend/frontend running:
1. Upload `manual-test-document.md`.
2. Confirm original file appears in `data/knowledge_base/originals`.
3. Confirm Markdown output appears in `data/knowledge_base/markdown/generated`.
4. Click the document row.
5. Confirm floating detail panel opens and can close.
6. Click reparse, confirm status/task history/segment preview refresh.
7. Upload a PDF or DOCX and confirm MarkItDown success or readable failure.

- [ ] **Step 5: Final read-only review**

Run one final review over all changed backend and frontend files. Expected result: no blocking findings.

## Self-Review

- Spec coverage: Covers disk storage, MarkItDown output, database paths, detail API, floating panel, universal parse action, and left-panel linkage.
- Placeholder scan: No TBD/TODO placeholders; tasks include concrete files, code shape, commands, and expected results.
- Type consistency: Backend uses `DocumentDetailSchema`, `ParseTaskSummarySchema`, `SegmentPreviewSchema`; frontend mirrors `DocumentDetail`, `ParseTaskSummary`, `SegmentPreview`.
- Scope check: v1 intentionally avoids Markdown full preview, true disk directory browsing, background queues, and historical file migration.
