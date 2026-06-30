import uuid
from datetime import UTC, datetime

from app.models.rag import DocumentStatus, KbDocument, ParseTask, ParseTaskStatus
from app.schemas.documents import (
    DocumentEnableRequest,
    DocumentItemSchema,
)
from app.services.document_management import (
    map_document_item,
    retry_document_parse,
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


class _ScalarList:
    def __init__(self, values):
        self._values = values

    def scalars(self):
        return iter(self._values)


class _RetrySession:
    def __init__(self, document=None, retry_counts=None):
        self.document = document
        self.retry_counts = retry_counts or []
        self.added = []
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

    def execute(self, statement):
        return _ScalarList(self.retry_counts)

    def add(self, item):
        self.added.append(item)

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
    session = _RetrySession(document)

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
    session = _RetrySession(document)

    item = set_document_enabled(session, document.id, True)

    assert document.enabled is True
    assert item.enableStatus == "enabled"
    assert session.commits == 1
    assert session.refreshed == [document]


def test_set_document_enabled_returns_none_for_missing_document():
    session = _RetrySession()

    item = set_document_enabled(session, uuid.uuid4(), True)

    assert item is None
    assert session.commits == 0
    assert session.refreshed == []


def test_retry_document_parse_skips_duplicate_placeholder_task():
    document = KbDocument(
        id=uuid.uuid4(),
        title="故障案例",
        file_name="故障案例.pdf",
        file_type="pdf",
        status=DocumentStatus.processing,
        enabled=False,
        segment_count=0,
        error_message=None,
        document_metadata={"category": "cases", "progress": 15, "retry_placeholder": True},
        updated_at=datetime(2026, 6, 30, 12, 30, 0, tzinfo=UTC),
    )
    session = _RetrySession(document)

    item = retry_document_parse(session, document.id)

    assert item.parseStatus == "processing"
    assert item.progress == 15
    assert session.added == []
    assert session.commits == 0
    assert session.refreshed == []


def test_retry_document_parse_adds_one_placeholder_task_on_first_retry():
    document = KbDocument(
        id=uuid.uuid4(),
        title="导入失败文档",
        file_name="故障案例.pdf",
        file_type="pdf",
        status=DocumentStatus.failed,
        enabled=True,
        segment_count=0,
        error_message="old failure",
        document_metadata={"category": "cases"},
        updated_at=datetime(2026, 6, 30, 13, 0, 0, tzinfo=UTC),
    )
    session = _RetrySession(document)

    item = retry_document_parse(session, document.id)

    assert item.parseStatus == "processing"
    assert item.enableStatus == "disabled"
    assert item.progress == 15
    assert document.error_message is None
    assert document.document_metadata["retry_placeholder"] is True
    assert len(session.added) == 1
    assert isinstance(session.added[0], ParseTask)
    assert session.added[0].status == ParseTaskStatus.pending
    assert session.added[0].parser_name == "manual-retry-placeholder"
    assert session.added[0].retry_count == 1
    assert session.added[0].task_metadata["placeholder"] is True
    assert session.commits == 1
    assert session.refreshed == [document]


def test_retry_document_parse_increments_retry_count_from_existing_tasks():
    document = KbDocument(
        id=uuid.uuid4(),
        title="瀵煎叆澶辫触鏂囨。",
        file_name="鏁呴殰妗堜緥.pdf",
        file_type="pdf",
        status=DocumentStatus.failed,
        enabled=True,
        segment_count=0,
        error_message="old failure",
        document_metadata={"category": "cases"},
        updated_at=datetime(2026, 6, 30, 13, 0, 0, tzinfo=UTC),
    )
    session = _RetrySession(document, retry_counts=[1, 4, 2])

    retry_document_parse(session, document.id)

    assert len(session.added) == 1
    assert session.added[0].retry_count == 5


def test_retry_document_parse_returns_none_for_missing_document():
    session = _RetrySession()

    item = retry_document_parse(session, uuid.uuid4())

    assert item is None
    assert session.added == []
    assert session.commits == 0
    assert session.refreshed == []
