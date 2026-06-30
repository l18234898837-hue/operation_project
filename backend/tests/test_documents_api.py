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
