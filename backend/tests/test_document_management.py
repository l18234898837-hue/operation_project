import uuid
from datetime import UTC, datetime

from app.models.rag import DocumentStatus, KbDocument
from app.schemas.documents import (
    DocumentEnableRequest,
    DocumentItemSchema,
)
from app.services.document_management import (
    map_document_item,
    set_document_enabled,
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


def test_map_document_item_handles_non_dict_metadata_with_title_fallback():
    document = KbDocument(
        id=uuid.uuid4(),
        title="未分类文档",
        file_name=None,
        file_type="markdown",
        status=DocumentStatus.ready,
        enabled=True,
        segment_count=0,
        error_message=None,
        document_metadata=["not", "a", "dict"],
        updated_at=datetime(2026, 6, 30, 12, 0, 0, tzinfo=UTC),
    )

    item = map_document_item(document)

    assert item.name == "未分类文档"
    assert item.category == "uncategorized"
    assert item.progress == 100


class _DocumentSession:
    def __init__(self, document=None):
        self.document = document
        self.commits = 0
        self.refreshed = []

    def get(self, model_type, document_id):
        if (
            model_type is KbDocument
            and self.document is not None
            and document_id == self.document.id
        ):
            return self.document
        return None

    def commit(self):
        self.commits += 1

    def refresh(self, item):
        self.refreshed.append(item)


def test_set_document_enabled_persists_boolean_and_returns_disabled_item():
    document = KbDocument(
        id=uuid.uuid4(),
        title="閫嗗彉鍣ㄦ晠闅滀笌缁存姢",
        file_name="01_閫嗗彉鍣ㄦ晠闅滀笌缁存姢.md",
        file_type="markdown",
        status=DocumentStatus.ready,
        enabled=True,
        segment_count=14,
        error_message=None,
        document_metadata={"category": "inverter"},
        updated_at=datetime(2026, 6, 30, 9, 15, 33, tzinfo=UTC),
    )
    session = _DocumentSession(document)

    item = set_document_enabled(session, document.id, False)

    assert document.enabled is False
    assert item.enableStatus == "disabled"
    assert session.commits == 1
    assert session.refreshed == [document]


def test_set_document_enabled_persists_boolean_and_returns_enabled_item():
    document = KbDocument(
        id=uuid.uuid4(),
        title="閫嗗彉鍣ㄦ晠闅滀笌缁存姢",
        file_name="01_閫嗗彉鍣ㄦ晠闅滀笌缁存姢.md",
        file_type="markdown",
        status=DocumentStatus.ready,
        enabled=False,
        segment_count=14,
        error_message=None,
        document_metadata={"category": "inverter"},
        updated_at=datetime(2026, 6, 30, 9, 15, 33, tzinfo=UTC),
    )
    session = _DocumentSession(document)

    item = set_document_enabled(session, document.id, True)

    assert document.enabled is True
    assert item.enableStatus == "enabled"
    assert session.commits == 1
    assert session.refreshed == [document]


def test_set_document_enabled_returns_none_for_missing_document():
    session = _DocumentSession()

    item = set_document_enabled(session, uuid.uuid4(), True)

    assert item is None
    assert session.commits == 0
    assert session.refreshed == []
