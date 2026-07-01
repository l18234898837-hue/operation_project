import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.schemas.documents import DocumentDetailSchema, DocumentItemSchema


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


def _detail(document_id: uuid.UUID | None = None) -> DocumentDetailSchema:
    item = _item(document_id=document_id)
    return DocumentDetailSchema(
        item=item,
        sourcePath="data/knowledge_base/originals/upload.md",
        markdownPath="data/knowledge_base/markdown/generated/upload.md",
        fileSha256="a" * 64,
        segmentCount=3,
        metadata={"category": "inverter"},
        latestTask={
            "id": str(uuid.uuid4()),
            "status": "success",
            "parserName": "manual-retry-text",
            "retryCount": 1,
            "durationMs": 123,
            "errorMessage": None,
            "startedAt": "2026-07-01 09:29:00",
            "finishedAt": "2026-07-01 09:30:00",
        },
        recentTasks=[],
        segmentPreview=[],
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


def test_get_document_detail_endpoint_returns_detail_payload():
    app = create_app()
    document_id = uuid.uuid4()
    detail = _detail(document_id=document_id)

    from app.api.documents import get_document_manager

    class FakeManager:
        def get_detail(self, target_id):
            assert target_id == document_id
            return detail

    app.dependency_overrides[get_document_manager] = lambda: FakeManager()
    client = TestClient(app)

    response = client.get(f"/api/documents/{document_id}")

    assert response.status_code == 200
    assert response.json()["item"]["id"] == str(document_id)
    assert response.json()["markdownPath"] == "data/knowledge_base/markdown/generated/upload.md"


def test_get_document_detail_endpoint_returns_404_for_missing_document():
    app = create_app()
    document_id = uuid.uuid4()

    from app.api.documents import get_document_manager

    class FakeManager:
        def get_detail(self, target_id):
            assert target_id == document_id
            return None

    app.dependency_overrides[get_document_manager] = lambda: FakeManager()
    client = TestClient(app)

    response = client.get(f"/api/documents/{document_id}")

    assert response.status_code == 404
    assert response.json()["detail"] == "Document not found"


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


def test_retry_document_endpoint_returns_ready_item_from_parser():
    app = create_app()
    document_id = uuid.uuid4()
    retry_item = _item(document_id=document_id)

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
    assert response.json()["enableStatus"] == "enabled"


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
    assert response.json()["detail"] == "Document not found"


def test_upload_document_endpoint_returns_uploaded_item():
    app = create_app()
    expected = _item()

    from app.api.documents import get_document_uploader

    class FakeUploader:
        async def upload(self, file):
            assert file.filename == "upload.md"
            return expected

    app.dependency_overrides[get_document_uploader] = lambda: FakeUploader()
    client = TestClient(app)

    response = client.post(
        "/api/documents/upload",
        files={"file": ("upload.md", b"# Title\n\nbody", "text/markdown")},
    )

    assert response.status_code == 200
    assert response.json()["id"] == str(expected.id)


def test_upload_document_endpoint_returns_400_for_bad_upload():
    app = create_app()

    from app.api.documents import get_document_uploader

    class FakeUploader:
        async def upload(self, file):
            raise ValueError("bad upload")

    app.dependency_overrides[get_document_uploader] = lambda: FakeUploader()
    client = TestClient(app)

    response = client.post(
        "/api/documents/upload",
        files={"file": ("upload.md", b"# Title\n\nbody", "text/markdown")},
    )

    assert response.status_code == 400
    assert response.json()["message"] == "bad upload"


@pytest.mark.asyncio
async def test_document_uploader_rejects_oversized_file_before_upload_service(monkeypatch):
    from app.api import documents

    class FakeUploadFile:
        filename = "upload.md"

        def __init__(self):
            self._chunks = [b"1234", b"56"]

        async def read(self, size=-1):
            if not self._chunks:
                return b""
            return self._chunks.pop(0)

    async def fail_upload_document_file(**kwargs):
        raise AssertionError("upload service should not receive oversized content")

    monkeypatch.setattr(documents.settings, "upload_max_bytes", 5)
    monkeypatch.setattr(documents, "upload_document_file", fail_upload_document_file)

    uploader = documents.DocumentUploader(session=object())

    with pytest.raises(ValueError, match="文件超过大小限制"):
        await uploader.upload(FakeUploadFile())


@pytest.mark.asyncio
async def test_document_uploader_passes_original_and_markdown_storage_dirs(monkeypatch):
    from app.api import documents

    expected = _item()
    captured = {}

    class FakeUploadFile:
        filename = "upload.md"

        def __init__(self):
            self._chunks = [b"# Title\n\nbody"]

        async def read(self, size=-1):
            if not self._chunks:
                return b""
            return self._chunks.pop(0)

    async def fake_upload_document_file(**kwargs):
        captured.update(kwargs)
        return expected

    monkeypatch.setattr(documents.settings, "upload_max_bytes", 1000)
    monkeypatch.setattr(documents.settings, "original_storage_dir", Path("originals"))
    monkeypatch.setattr(documents.settings, "markdown_storage_dir", Path("markdown/generated"))
    monkeypatch.setattr(documents.settings, "embedding_base_url", "http://embedding.test")
    monkeypatch.setattr(documents, "upload_document_file", fake_upload_document_file)

    uploader = documents.DocumentUploader(session="session")

    item = await uploader.upload(FakeUploadFile())

    assert item == expected
    assert captured["session"] == "session"
    assert captured["original_storage_dir"] == Path("originals")
    assert captured["markdown_storage_dir"] == Path("markdown/generated")
    assert captured["file_data"].filename == "upload.md"
    assert captured["file_data"].content == b"# Title\n\nbody"


@pytest.mark.asyncio
async def test_document_parser_passes_markdown_storage_dir(monkeypatch):
    from app.api import documents

    expected = _item()
    document_id = uuid.uuid4()
    captured = {}

    async def fake_retry_document_parse(**kwargs):
        captured.update(kwargs)
        return expected

    monkeypatch.setattr(documents.settings, "markdown_storage_dir", Path("markdown/generated"))
    monkeypatch.setattr(documents.settings, "embedding_base_url", "http://embedding.test")
    monkeypatch.setattr(documents, "retry_document_parse", fake_retry_document_parse)

    parser = documents.DocumentParser(session="session")

    item = await parser.retry_parse(document_id)

    assert item == expected
    assert captured["session"] == "session"
    assert captured["document_id"] == document_id
    assert captured["markdown_storage_dir"] == Path("markdown/generated")
