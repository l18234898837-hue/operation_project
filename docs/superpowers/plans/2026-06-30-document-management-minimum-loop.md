# Document Management Minimum Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the document management page mock data with a usable backend-backed minimum loop: real document list, enable/disable persistence, and a retry-parse placeholder endpoint.

**Architecture:** Add a focused FastAPI document-management router over the existing `KbDocument` and `ParseTask` models, mapping backend RAG document state into the frontend `DocumentItem` contract. Keep filtering, category counts, and pagination client-side for this minimum loop, because the current page already owns that behavior. Do not implement real file upload or PDF/Word/Excel parsing in this plan; the retry endpoint only records a parse retry request and moves the document into a processing-looking state for later worker integration.

**Tech Stack:** FastAPI, Pydantic, SQLAlchemy 2.0, PostgreSQL model contracts, pytest, Vue 3, Pinia, TypeScript, Vite, Element Plus icons.

---

## File Structure

- Create `backend/app/schemas/documents.py`: Pydantic request/response contracts for document management.
- Create `backend/app/services/document_management.py`: database query, state mutation, and backend-to-frontend document mapping helpers.
- Create `backend/app/api/documents.py`: FastAPI endpoints under `/api/documents`.
- Modify `backend/app/api/router.py`: include the new documents router.
- Create `backend/tests/test_document_management.py`: unit coverage for mapping, list behavior, enable/disable updates, and retry placeholder state.
- Create `backend/tests/test_documents_api.py`: API-level contract coverage with dependency overrides.
- Modify `frontend/src/api/documents.ts`: replace mock-returning functions with real `fetch` calls.
- Modify `frontend/src/stores/documents.ts`: initialize empty, load real documents, call API mutations, keep existing local filters/pagination.
- Modify `frontend/src/views/DocumentManageView.vue`: load documents on mount, rename mock upload behavior, show loading/error states, and disable unavailable upload while real upload is out of scope.
- Modify `frontend/src/documents/documentStore.contract.ts`: update store contract names away from mock-specific APIs.
- Keep `frontend/src/mock/documents.ts`: retain category seed data for the sidebar only; stop using `mockDocuments` as live document data.

## API Contract

Backend endpoints:

- `GET /api/documents` returns `DocumentItem[]`.
- `PATCH /api/documents/{document_id}/enabled` accepts `{"enabled": true | false}` and returns the updated `DocumentItem`.
- `POST /api/documents/{document_id}/retry` records a placeholder retry request and returns the updated `DocumentItem`.

Response shape matches the existing frontend contract:

```json
{
  "id": "document-uuid",
  "name": "01_逆变器故障与维护.md",
  "type": "Markdown",
  "category": "uncategorized",
  "parseStatus": "ready",
  "enableStatus": "enabled",
  "updatedAt": "2026-06-30 09:15:33",
  "failureReason": null,
  "progress": 100
}
```

Mapping rules:

- `name`: `KbDocument.file_name`, then `document_metadata.source_file_name`, then `KbDocument.title`.
- `type`: infer from `file_type` or filename extension into `PDF | Word | Excel | Markdown | TXT`.
- `category`: `document_metadata.category` if it matches a known frontend category, otherwise `uncategorized`.
- `parseStatus`: `uploaded | processing | ready | failed`; legacy backend `disabled` maps to `ready` because enablement is represented separately.
- `enableStatus`: `enabled` when `KbDocument.enabled` is true, otherwise `disabled`.
- `progress`: `0` for uploaded, metadata progress or `15` for processing, `100` for ready, `null` for failed.

## Implementation Tasks

### Task 1: Backend Document Schemas

**Files:**
- Create: `backend/app/schemas/documents.py`
- Test: `backend/tests/test_document_management.py`

- [ ] **Step 1: Write the failing schema test**

Create `backend/tests/test_document_management.py` with this initial content:

```python
import uuid

from app.schemas.documents import (
    DocumentEnableRequest,
    DocumentItemSchema,
)


def test_document_item_schema_matches_frontend_contract():
    document_id = uuid.uuid4()

    item = DocumentItemSchema(
        id=document_id,
        name="01_逆变器故障与维护.md",
        type="Markdown",
        category="uncategorized",
        parseStatus="ready",
        enableStatus="enabled",
        updatedAt="2026-06-30 09:15:33",
        failureReason=None,
        progress=100,
    )

    data = item.model_dump(mode="json")

    assert data == {
        "id": str(document_id),
        "name": "01_逆变器故障与维护.md",
        "type": "Markdown",
        "category": "uncategorized",
        "parseStatus": "ready",
        "enableStatus": "enabled",
        "updatedAt": "2026-06-30 09:15:33",
        "failureReason": None,
        "progress": 100,
    }


def test_document_enable_request_accepts_boolean_enabled():
    request = DocumentEnableRequest(enabled=False)

    assert request.enabled is False
```

- [ ] **Step 2: Run the schema test to verify it fails**

Run:

```powershell
backend\.venv\Scripts\python.exe -c "import sys, pathlib, pytest; root=pathlib.Path.cwd(); sys.path[:0]=[str(root), str(root / 'backend')]; raise SystemExit(pytest.main(['backend/tests/test_document_management.py::test_document_item_schema_matches_frontend_contract', '-q']))"
```

Expected: failure with `ModuleNotFoundError: No module named 'app.schemas.documents'`.

- [ ] **Step 3: Add the document schemas**

Create `backend/app/schemas/documents.py`:

```python
from __future__ import annotations

from typing import Literal
import uuid

from pydantic import BaseModel, Field


DocumentTypeLiteral = Literal["PDF", "Word", "Excel", "Markdown", "TXT"]
DocumentCategoryLiteral = Literal[
    "inverter",
    "inspection",
    "grid-quality",
    "modules",
    "manual",
    "cases",
    "standards",
    "uncategorized",
]
DocumentParseStatusLiteral = Literal["uploaded", "processing", "ready", "failed"]
DocumentEnableStatusLiteral = Literal["enabled", "disabled"]


class DocumentItemSchema(BaseModel):
    id: uuid.UUID
    name: str
    type: DocumentTypeLiteral
    category: DocumentCategoryLiteral
    parseStatus: DocumentParseStatusLiteral
    enableStatus: DocumentEnableStatusLiteral
    updatedAt: str
    failureReason: str | None
    progress: int | None = Field(ge=0, le=100)


class DocumentEnableRequest(BaseModel):
    enabled: bool
```

- [ ] **Step 4: Run the schema tests to verify they pass**

Run:

```powershell
backend\.venv\Scripts\python.exe -c "import sys, pathlib, pytest; root=pathlib.Path.cwd(); sys.path[:0]=[str(root), str(root / 'backend')]; raise SystemExit(pytest.main(['backend/tests/test_document_management.py', '-q']))"
```

Expected: `2 passed`.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/schemas/documents.py backend/tests/test_document_management.py
git commit -m "test: add document management schemas"
```

### Task 2: Backend Document Mapping Service

**Files:**
- Create: `backend/app/services/document_management.py`
- Modify: `backend/tests/test_document_management.py`

- [ ] **Step 1: Add failing mapper tests**

Append these tests to `backend/tests/test_document_management.py`:

```python
from datetime import UTC, datetime

from app.models.rag import DocumentStatus, KbDocument
from app.services.document_management import map_document_item


def test_map_document_item_uses_file_name_and_ready_progress():
    document = KbDocument(
        id=uuid.uuid4(),
        title="逆变器故障与维护",
        file_name="01_逆变器故障与维护.md",
        file_type="markdown",
        status=DocumentStatus.ready,
        enabled=True,
        segment_count=14,
        error_message=None,
        document_metadata={"category": "inverter"},
        updated_at=datetime(2026, 6, 30, 9, 15, 33, tzinfo=UTC),
    )

    item = map_document_item(document)

    assert item.name == "01_逆变器故障与维护.md"
    assert item.type == "Markdown"
    assert item.category == "inverter"
    assert item.parseStatus == "ready"
    assert item.enableStatus == "enabled"
    assert item.updatedAt == "2026-06-30 09:15:33"
    assert item.failureReason is None
    assert item.progress == 100


def test_map_document_item_uses_metadata_file_name_and_failed_reason():
    document = KbDocument(
        id=uuid.uuid4(),
        title="导入失败文档",
        file_name=None,
        file_type="pdf",
        status=DocumentStatus.failed,
        enabled=False,
        segment_count=0,
        error_message="embedding unavailable",
        document_metadata={"source_file_name": "故障案例.pdf", "category": "cases"},
        updated_at=datetime(2026, 6, 30, 10, 5, 44, tzinfo=UTC),
    )

    item = map_document_item(document)

    assert item.name == "故障案例.pdf"
    assert item.type == "PDF"
    assert item.category == "cases"
    assert item.parseStatus == "failed"
    assert item.enableStatus == "disabled"
    assert item.failureReason == "embedding unavailable"
    assert item.progress is None


def test_map_document_item_falls_back_to_uncategorized_and_processing_progress():
    document = KbDocument(
        id=uuid.uuid4(),
        title="未分类文档",
        file_name="notes.txt",
        file_type=None,
        status=DocumentStatus.processing,
        enabled=False,
        segment_count=0,
        error_message=None,
        document_metadata={"category": "unknown", "progress": 60},
        updated_at=datetime(2026, 6, 30, 11, 0, 0, tzinfo=UTC),
    )

    item = map_document_item(document)

    assert item.type == "TXT"
    assert item.category == "uncategorized"
    assert item.parseStatus == "processing"
    assert item.progress == 60
```

- [ ] **Step 2: Run mapper tests to verify they fail**

Run:

```powershell
backend\.venv\Scripts\python.exe -c "import sys, pathlib, pytest; root=pathlib.Path.cwd(); sys.path[:0]=[str(root), str(root / 'backend')]; raise SystemExit(pytest.main(['backend/tests/test_document_management.py::test_map_document_item_uses_file_name_and_ready_progress', '-q']))"
```

Expected: failure with `ModuleNotFoundError: No module named 'app.services.document_management'`.

- [ ] **Step 3: Implement mapping helpers**

Create `backend/app/services/document_management.py`:

```python
from __future__ import annotations

import uuid
from pathlib import Path

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

    next_retry_count = _next_retry_count(session, document_id)
    metadata = dict(document.document_metadata or {})
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
            retry_count=next_retry_count,
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
    metadata = document.document_metadata or {}
    name = document.file_name or metadata.get("source_file_name") or document.title
    parse_status = document.status.value
    if parse_status == DocumentStatus.disabled.value:
        parse_status = DocumentStatus.ready.value

    return DocumentItemSchema(
        id=document.id,
        name=name,
        type=_document_type(document.file_type, name),
        category=_category(metadata.get("category")),
        parseStatus=parse_status,
        enableStatus="enabled" if document.enabled else "disabled",
        updatedAt=document.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
        failureReason=document.error_message,
        progress=_progress(document.status, metadata),
    )


def _document_type(file_type: str | None, name: str) -> str:
    source = (file_type or Path(name).suffix.lstrip(".")).lower()
    if source in {"pdf"}:
        return "PDF"
    if source in {"doc", "docx", "word"}:
        return "Word"
    if source in {"xls", "xlsx", "excel"}:
        return "Excel"
    if source in {"md", "markdown"}:
        return "Markdown"
    return "TXT"


def _category(value: object) -> str:
    if isinstance(value, str) and value in KNOWN_CATEGORIES:
        return value
    return "uncategorized"


def _progress(status: DocumentStatus, metadata: dict) -> int | None:
    if status == DocumentStatus.uploaded:
        return 0
    if status == DocumentStatus.processing:
        value = metadata.get("progress")
        if isinstance(value, int) and 0 <= value <= 100:
            return value
        return 15
    if status == DocumentStatus.ready:
        return 100
    return None


def _next_retry_count(session: Session, document_id: uuid.UUID) -> int:
    retry_counts = session.execute(
        select(ParseTask.retry_count).where(ParseTask.document_id == document_id)
    ).scalars()
    return max([0, *retry_counts]) + 1
```

- [ ] **Step 4: Run mapper tests to verify they pass**

Run:

```powershell
backend\.venv\Scripts\python.exe -c "import sys, pathlib, pytest; root=pathlib.Path.cwd(); sys.path[:0]=[str(root), str(root / 'backend')]; raise SystemExit(pytest.main(['backend/tests/test_document_management.py', '-q']))"
```

Expected: `5 passed`.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/services/document_management.py backend/tests/test_document_management.py
git commit -m "feat: map knowledge documents for management UI"
```

### Task 3: Backend Document API Routes

**Files:**
- Create: `backend/app/api/documents.py`
- Modify: `backend/app/api/router.py`
- Create: `backend/tests/test_documents_api.py`

- [ ] **Step 1: Write failing API tests**

Create `backend/tests/test_documents_api.py`:

```python
import uuid

from fastapi.testclient import TestClient

from app.main import create_app
from app.schemas.documents import DocumentItemSchema


def _item(document_id: uuid.UUID | None = None, enabled: bool = True) -> DocumentItemSchema:
    return DocumentItemSchema(
        id=document_id or uuid.uuid4(),
        name="01_逆变器故障与维护.md",
        type="Markdown",
        category="inverter",
        parseStatus="ready",
        enableStatus="enabled" if enabled else "disabled",
        updatedAt="2026-06-30 09:15:33",
        failureReason=None,
        progress=100,
    )


def test_list_documents_endpoint_returns_document_items():
    app = create_app()
    expected = _item()

    from app.api.documents import get_document_manager

    class FakeManager:
        def list_documents(self):
            return [expected]

    app.dependency_overrides[get_document_manager] = lambda: FakeManager()
    client = TestClient(app)

    response = client.get("/api/documents")

    assert response.status_code == 200
    assert response.json()[0]["id"] == str(expected.id)
    assert response.json()[0]["name"] == "01_逆变器故障与维护.md"


def test_update_document_enabled_endpoint_returns_updated_item():
    app = create_app()
    document_id = uuid.uuid4()
    updated = _item(document_id=document_id, enabled=False)

    from app.api.documents import get_document_manager

    class FakeManager:
        def set_enabled(self, target_id, enabled):
            assert target_id == document_id
            assert enabled is False
            return updated

    app.dependency_overrides[get_document_manager] = lambda: FakeManager()
    client = TestClient(app)

    response = client.patch(
        f"/api/documents/{document_id}/enabled",
        json={"enabled": False},
    )

    assert response.status_code == 200
    assert response.json()["enableStatus"] == "disabled"


def test_update_document_enabled_endpoint_returns_404_for_missing_document():
    app = create_app()
    document_id = uuid.uuid4()

    from app.api.documents import get_document_manager

    class FakeManager:
        def set_enabled(self, target_id, enabled):
            return None

    app.dependency_overrides[get_document_manager] = lambda: FakeManager()
    client = TestClient(app)

    response = client.patch(
        f"/api/documents/{document_id}/enabled",
        json={"enabled": True},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Document not found"


def test_retry_document_endpoint_returns_processing_item():
    app = create_app()
    document_id = uuid.uuid4()
    retry_item = DocumentItemSchema(
        id=document_id,
        name="故障案例.pdf",
        type="PDF",
        category="cases",
        parseStatus="processing",
        enableStatus="disabled",
        updatedAt="2026-06-30 10:00:00",
        failureReason=None,
        progress=15,
    )

    from app.api.documents import get_document_manager

    class FakeManager:
        def retry_parse(self, target_id):
            assert target_id == document_id
            return retry_item

    app.dependency_overrides[get_document_manager] = lambda: FakeManager()
    client = TestClient(app)

    response = client.post(f"/api/documents/{document_id}/retry")

    assert response.status_code == 200
    assert response.json()["parseStatus"] == "processing"
    assert response.json()["enableStatus"] == "disabled"
```

- [ ] **Step 2: Run API tests to verify they fail**

Run:

```powershell
backend\.venv\Scripts\python.exe -c "import sys, pathlib, pytest; root=pathlib.Path.cwd(); sys.path[:0]=[str(root), str(root / 'backend')]; raise SystemExit(pytest.main(['backend/tests/test_documents_api.py', '-q']))"
```

Expected: failure with `ModuleNotFoundError: No module named 'app.api.documents'`.

- [ ] **Step 3: Implement the documents API router**

Create `backend/app/api/documents.py`:

```python
from __future__ import annotations

import uuid
from collections.abc import Iterator

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
```

- [ ] **Step 4: Include the router**

Modify `backend/app/api/router.py` to:

```python
from fastapi import APIRouter

from app.api.documents import router as documents_router
from app.api.qa import router as qa_router

router = APIRouter()


@router.get("/health", tags=["health"])
async def api_health() -> dict[str, str]:
    return {"status": "ok"}


router.include_router(documents_router)
router.include_router(qa_router)
api_router = router
```

- [ ] **Step 5: Run API tests to verify they pass**

Run:

```powershell
backend\.venv\Scripts\python.exe -c "import sys, pathlib, pytest; root=pathlib.Path.cwd(); sys.path[:0]=[str(root), str(root / 'backend')]; raise SystemExit(pytest.main(['backend/tests/test_documents_api.py', '-q']))"
```

Expected: `4 passed`.

- [ ] **Step 6: Commit**

```powershell
git add backend/app/api/documents.py backend/app/api/router.py backend/tests/test_documents_api.py
git commit -m "feat: add document management API"
```

### Task 4: Backend Service Mutation Tests

**Files:**
- Modify: `backend/tests/test_document_management.py`
- Modify: `backend/app/services/document_management.py` if tests reveal gaps

- [ ] **Step 1: Add service-level mutation tests**

Append these tests to `backend/tests/test_document_management.py`:

```python
from app.models.rag import ParseTask, ParseTaskStatus
from app.services.document_management import retry_document_parse, set_document_enabled


class _ScalarList:
    def __init__(self, values):
        self._values = values

    def scalars(self):
        return iter(self._values)


class _MutationSession:
    def __init__(self, document):
        self.document = document
        self.added = []
        self.commits = 0
        self.refreshed = []

    def get(self, model_type, document_id):
        if model_type is KbDocument and document_id == self.document.id:
            return self.document
        return None

    def execute(self, statement):
        return _ScalarList([2])

    def add(self, item):
        self.added.append(item)

    def commit(self):
        self.commits += 1

    def refresh(self, item):
        self.refreshed.append(item)


def test_set_document_enabled_persists_boolean_and_returns_item():
    document = KbDocument(
        id=uuid.uuid4(),
        title="逆变器故障与维护",
        file_name="01_逆变器故障与维护.md",
        file_type="markdown",
        status=DocumentStatus.ready,
        enabled=True,
        segment_count=14,
        updated_at=datetime(2026, 6, 30, 9, 15, 33, tzinfo=UTC),
    )
    session = _MutationSession(document)

    item = set_document_enabled(session, document.id, False)

    assert document.enabled is False
    assert item.enableStatus == "disabled"
    assert session.commits == 1
    assert session.refreshed == [document]


def test_retry_document_parse_records_placeholder_task_and_processing_state():
    document = KbDocument(
        id=uuid.uuid4(),
        title="故障案例",
        file_name="故障案例.pdf",
        file_type="pdf",
        status=DocumentStatus.failed,
        enabled=True,
        segment_count=0,
        error_message="old failure",
        document_metadata={"category": "cases"},
        updated_at=datetime(2026, 6, 30, 10, 0, 0, tzinfo=UTC),
    )
    session = _MutationSession(document)

    item = retry_document_parse(session, document.id)

    assert document.status == DocumentStatus.processing
    assert document.enabled is False
    assert document.error_message is None
    assert document.document_metadata["progress"] == 15
    assert document.document_metadata["retry_placeholder"] is True
    assert item.parseStatus == "processing"
    assert item.enableStatus == "disabled"
    assert item.progress == 15
    assert session.commits == 1

    task = session.added[0]
    assert isinstance(task, ParseTask)
    assert task.document_id == document.id
    assert task.status == ParseTaskStatus.pending
    assert task.parser_name == "manual-retry-placeholder"
    assert task.retry_count == 3
    assert task.task_metadata["placeholder"] is True
```

- [ ] **Step 2: Run mutation tests**

Run:

```powershell
backend\.venv\Scripts\python.exe -c "import sys, pathlib, pytest; root=pathlib.Path.cwd(); sys.path[:0]=[str(root), str(root / 'backend')]; raise SystemExit(pytest.main(['backend/tests/test_document_management.py', '-q']))"
```

Expected: all document management tests pass. If `_next_retry_count` fails because fake scalar behavior differs from SQLAlchemy expectations, adjust the helper to convert `session.execute(...).scalars()` to `list(...)` exactly as shown in Task 2.

- [ ] **Step 3: Commit**

```powershell
git add backend/app/services/document_management.py backend/tests/test_document_management.py
git commit -m "test: cover document management mutations"
```

### Task 5: Frontend API Client Uses Real Endpoints

**Files:**
- Modify: `frontend/src/api/documents.ts`

- [ ] **Step 1: Replace mock API functions**

Change `frontend/src/api/documents.ts` to:

```typescript
import type { DocumentItem } from "../types/document";

async function parseDocumentResponse(response: Response): Promise<DocumentItem> {
  if (!response.ok) {
    throw new Error(`Document request failed: ${response.status}`);
  }

  return (await response.json()) as DocumentItem;
}

export async function listDocuments(): Promise<DocumentItem[]> {
  const response = await fetch("/api/documents");

  if (!response.ok) {
    throw new Error(`Document list request failed: ${response.status}`);
  }

  return (await response.json()) as DocumentItem[];
}

export async function setDocumentEnabled(id: string, enabled: boolean): Promise<DocumentItem> {
  const response = await fetch(`/api/documents/${id}/enabled`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ enabled })
  });

  return parseDocumentResponse(response);
}

export async function retryDocumentParse(id: string): Promise<DocumentItem> {
  const response = await fetch(`/api/documents/${id}/retry`, {
    method: "POST"
  });

  return parseDocumentResponse(response);
}
```

- [ ] **Step 2: Run frontend typecheck to expose store callsite failures**

Run:

```powershell
cd frontend
npm run build
```

Expected: TypeScript fails because `stores/documents.ts` still imports `uploadDocument` and uses mock-specific store methods.

- [ ] **Step 3: Commit after frontend store task, not now**

Do not commit this file alone because the project is intentionally broken until Task 6 updates the store.

### Task 6: Frontend Store Loads and Mutates Real Documents

**Files:**
- Modify: `frontend/src/stores/documents.ts`
- Modify: `frontend/src/documents/documentStore.contract.ts`

- [ ] **Step 1: Update the document store API usage**

In `frontend/src/stores/documents.ts`, replace imports at the top with:

```typescript
import { computed, ref } from "vue";
import { defineStore } from "pinia";

import { listDocuments, retryDocumentParse, setDocumentEnabled } from "../api/documents";
import { baseDocumentCategories } from "../mock/documents";
import type {
  DocumentCategory,
  DocumentCategoryKey,
  DocumentEnableStatus,
  DocumentFilters,
  DocumentItem,
  DocumentParseStatus,
  DocumentSummary,
  DocumentType
} from "../types/document";
```

Replace the initial document and notice refs with:

```typescript
  const documents = ref<DocumentItem[]>([]);
  const isLoading = ref(false);
  const errorMessage = ref("");
  const lastNotice = ref("");
```

Add these actions before `resetPage()`:

```typescript
  async function loadDocuments() {
    isLoading.value = true;
    errorMessage.value = "";

    try {
      documents.value = await listDocuments();
      resetPage();
    } catch (error) {
      errorMessage.value = error instanceof Error ? error.message : "文档列表加载失败";
    } finally {
      isLoading.value = false;
    }
  }

  function replaceDocument(nextDocument: DocumentItem) {
    documents.value = documents.value.map((document) =>
      document.id === nextDocument.id ? nextDocument : document
    );
  }
```

Replace `uploadMockDocument`, `toggleDocumentEnabled`, and `retryParse` with:

```typescript
  async function toggleDocumentEnabled(id: string) {
    const document = documents.value.find((item) => item.id === id);
    if (!document) {
      return;
    }

    errorMessage.value = "";
    const nextEnabled = document.enableStatus !== "enabled";

    try {
      const updated = await setDocumentEnabled(id, nextEnabled);
      replaceDocument(updated);
      lastNotice.value = nextEnabled ? "文档已启用，将参与 RAG 检索。" : "文档已禁用，暂不参与 RAG 检索。";
    } catch (error) {
      errorMessage.value = error instanceof Error ? error.message : "文档启用状态更新失败";
    }
  }

  async function retryParse(id: string) {
    errorMessage.value = "";

    try {
      const updated = await retryDocumentParse(id);
      replaceDocument(updated);
      lastNotice.value = "已提交重新解析请求，真实解析任务将在后续接入。";
    } catch (error) {
      errorMessage.value = error instanceof Error ? error.message : "重新解析请求提交失败";
    }
  }
```

Ensure the returned object includes `isLoading`, `errorMessage`, and `loadDocuments`, and removes `uploadMockDocument`:

```typescript
  return {
    documents,
    filters,
    isLoading,
    errorMessage,
    lastNotice,
    categories,
    currentCategoryLabel,
    summary,
    filteredDocuments,
    paginatedDocuments,
    totalPages,
    documentTypeOptions,
    parseStatusOptions,
    enableStatusOptions,
    loadDocuments,
    setCategory,
    setSearchKeyword,
    setTypeFilter,
    setParseStatusFilter,
    setEnableStatusFilter,
    setPage,
    resetFilters,
    toggleDocumentEnabled,
    retryParse,
    getFailureReason
  };
```

- [ ] **Step 2: Update the store contract**

In `frontend/src/documents/documentStore.contract.ts`, replace:

```typescript
void store.uploadMockDocument("新增运维规程.pdf", "PDF");
```

with:

```typescript
void store.loadDocuments();
void store.isLoading;
void store.errorMessage;
```

Keep these calls:

```typescript
void store.toggleDocumentEnabled("doc-inverter-manual");
void store.retryParse("doc-grid-failure");
```

- [ ] **Step 3: Run frontend build to expose view callsite failures**

Run:

```powershell
cd frontend
npm run build
```

Expected: TypeScript fails because `DocumentManageView.vue` still calls `uploadMockDocument`.

- [ ] **Step 4: Commit after Task 7, not now**

Do not commit yet because the frontend is intentionally broken until the view is updated.

### Task 7: Frontend View Loads Real Data and Disables Upload Placeholder

**Files:**
- Modify: `frontend/src/views/DocumentManageView.vue`

- [ ] **Step 1: Update imports and mount loading**

Change the script import from:

```typescript
import { computed, ref } from "vue";
```

to:

```typescript
import { computed, onMounted, ref } from "vue";
```

Remove:

```typescript
const uploadName = ref("新上传运维资料.pdf");
const uploadType = ref<DocumentType>("PDF");

const uploadTypeOptions: DocumentType[] = ["PDF", "Word", "Excel", "Markdown", "TXT"];
```

Add after `const selectedFailure = ref<DocumentItem | null>(null);`:

```typescript
onMounted(() => {
  void documentStore.loadDocuments();
});
```

Remove the `uploadMock()` function entirely.

- [ ] **Step 2: Update the primary upload button**

Replace the primary upload button with a disabled placeholder:

```vue
        <button class="document-upload-primary" type="button" disabled title="真实上传将在下一阶段接入">
          <Upload aria-hidden="true" />
          上传文档
        </button>
```

- [ ] **Step 3: Replace the simulated upload strip**

Replace the whole `<section class="document-upload-strip">...</section>` block with:

```vue
      <section class="document-upload-strip">
        <div>
          <strong>真实文档列表已接入</strong>
          <span>当前页面读取后端知识库文档；文件上传和真实重新解析工作流将在下一阶段接入。</span>
        </div>
        <button class="document-reset" type="button" @click="documentStore.loadDocuments">
          <Refresh aria-hidden="true" />
          刷新列表
        </button>
      </section>
```

- [ ] **Step 4: Add loading and error display**

Add this block after the upload strip:

```vue
      <p v-if="documentStore.errorMessage" class="document-notice error">
        {{ documentStore.errorMessage }}
      </p>

      <div v-if="documentStore.isLoading" class="document-empty">
        正在加载文档列表...
      </div>
```

Change the empty table message condition from:

```vue
        <div v-if="documentStore.paginatedDocuments.length === 0" class="document-empty">
```

to:

```vue
        <div v-if="!documentStore.isLoading && documentStore.paginatedDocuments.length === 0" class="document-empty">
```

- [ ] **Step 5: Ensure the disabled upload button has usable styles**

If `.document-upload-primary:disabled` is not already styled in `frontend/src/styles/main.css`, add:

```css
.document-upload-primary:disabled {
  cursor: not-allowed;
  opacity: 0.58;
}

.document-notice.error {
  border-color: rgba(248, 113, 113, 0.35);
  background: rgba(254, 226, 226, 0.72);
  color: #991b1b;
}
```

- [ ] **Step 6: Run frontend build**

Run:

```powershell
cd frontend
npm run build
```

Expected: build succeeds.

- [ ] **Step 7: Commit frontend real API wiring**

```powershell
git add frontend/src/api/documents.ts frontend/src/stores/documents.ts frontend/src/documents/documentStore.contract.ts frontend/src/views/DocumentManageView.vue frontend/src/styles/main.css
git commit -m "feat: wire document management page to backend"
```

### Task 8: Full Verification

**Files:**
- No new files unless verification exposes defects.

- [ ] **Step 1: Run backend document tests**

Run:

```powershell
backend\.venv\Scripts\python.exe -c "import sys, pathlib, pytest; root=pathlib.Path.cwd(); sys.path[:0]=[str(root), str(root / 'backend')]; raise SystemExit(pytest.main(['backend/tests/test_document_management.py', 'backend/tests/test_documents_api.py', '-q']))"
```

Expected: all document tests pass.

- [ ] **Step 2: Run existing QA API smoke tests**

Run:

```powershell
backend\.venv\Scripts\python.exe -c "import sys, pathlib, pytest; root=pathlib.Path.cwd(); sys.path[:0]=[str(root), str(root / 'backend')]; raise SystemExit(pytest.main(['backend/tests/test_qa_api.py', '-q']))"
```

Expected: existing QA API tests pass, proving the new router include did not break `/api/qa/*`.

- [ ] **Step 3: Run frontend production build**

Run:

```powershell
cd frontend
npm run build
```

Expected: `vue-tsc --noEmit && vite build` succeeds.

- [ ] **Step 4: Manual API smoke with backend running**

Start backend:

```powershell
cd backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

In another PowerShell window from repo root, run:

```powershell
$response = Invoke-RestMethod -Method Get -Uri http://127.0.0.1:8000/api/documents
$response | Select-Object -First 1
```

Expected: returns a document object with `id`, `name`, `type`, `parseStatus`, and `enableStatus`.

- [ ] **Step 5: Manual frontend smoke**

Start frontend:

```powershell
cd frontend
npm run dev
```

Open:

```text
http://127.0.0.1:5173/admin/documents
```

Expected:

- The table is populated from `/api/documents`.
- The summary cards match the returned rows.
- Clicking `禁用` or `启用` persists after pressing `刷新列表`.
- Clicking `重新解析` on a failed row changes it to `解析中 (15%)` and disables it.
- Upload is visibly disabled with title text saying real upload is next phase.

- [ ] **Step 6: Final commit for verification-only adjustments**

If verification required small fixes, commit them:

```powershell
git add backend frontend
git commit -m "fix: stabilize document management minimum loop"
```

If no fixes were needed, skip this commit.

## Self-Review

- Spec coverage: The plan covers real document listing, enable/disable persistence, retry placeholder endpoint, and frontend mock removal. Real upload and actual parse workers are intentionally excluded and represented as disabled/placeholder UI.
- Placeholder scan: The only placeholder behavior is the explicitly requested retry-parse placeholder endpoint; all code paths and messages are specified.
- Type consistency: Backend `DocumentItemSchema` fields match frontend `DocumentItem`; frontend API names are `listDocuments`, `setDocumentEnabled`, and `retryDocumentParse`; store methods exposed to the view are `loadDocuments`, `toggleDocumentEnabled`, and `retryParse`.
