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
        return self

    def all(self):
        return list(self._values)


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
    older_task = ParseTask(
        id=uuid.uuid4(),
        document_id=document_id,
        status=ParseTaskStatus.failed,
        parser_name="manual-retry-text",
        retry_count=0,
        duration_ms=99,
        error_message="temporary failure",
        created_at=datetime(2026, 7, 1, 9, 31, tzinfo=UTC),
        started_at=datetime(2026, 7, 1, 9, 25, tzinfo=UTC),
        finished_at=datetime(2026, 7, 1, 9, 26, tzinfo=UTC),
    )
    latest_task = ParseTask(
        id=uuid.uuid4(),
        document_id=document_id,
        status=ParseTaskStatus.success,
        parser_name="manual-retry-text",
        retry_count=1,
        duration_ms=123,
        created_at=datetime(2026, 7, 1, 9, 30, tzinfo=UTC),
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
    session = _DetailSession(
        document=document,
        tasks=[latest_task, older_task],
        segments=[segment],
    )

    detail = get_document_detail(session, document_id)

    assert detail is not None
    assert detail.item.id == document_id
    assert detail.sourcePath == "data/knowledge_base/originals/hash_manual.md"
    assert detail.markdownPath == "data/knowledge_base/markdown/generated/hash_manual.md"
    assert detail.fileSha256 == "a" * 64
    assert detail.segmentCount == 2
    assert detail.metadata == {"category": "manual", "source_file_name": "manual.md"}
    assert detail.latestTask is not None
    assert detail.latestTask.id == latest_task.id
    assert detail.latestTask.parserName == "manual-retry-text"
    assert detail.latestTask.retryCount == 1
    assert detail.latestTask.durationMs == 123
    assert detail.latestTask.startedAt == "2026-07-01 09:29:00"
    assert detail.recentTasks[1].status == "failed"
    assert detail.recentTasks[1].errorMessage == "temporary failure"
    assert detail.segmentPreview[0].headingPath == "Manual > Safety"
    assert detail.segmentPreview[0].sectionTitle == "Safety"
    assert detail.segmentPreview[0].chunkIndex == 0
    assert detail.segmentPreview[0].charCount == 12
    assert detail.segmentPreview[0].hasEmbedding is True


def test_get_document_detail_orders_recent_tasks_by_started_at_then_created_at():
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
        segment_count=0,
        document_metadata={"category": "manual", "source_file_name": "manual.md"},
        updated_at=datetime(2026, 7, 1, 9, 30, tzinfo=UTC),
    )
    created_later_started_earlier = ParseTask(
        id=uuid.uuid4(),
        document_id=document_id,
        status=ParseTaskStatus.failed,
        parser_name="manual-retry-text",
        retry_count=0,
        created_at=datetime(2026, 7, 1, 9, 35, tzinfo=UTC),
        started_at=datetime(2026, 7, 1, 9, 20, tzinfo=UTC),
    )
    started_later_created_earlier = ParseTask(
        id=uuid.uuid4(),
        document_id=document_id,
        status=ParseTaskStatus.success,
        parser_name="manual-retry-text",
        retry_count=1,
        created_at=datetime(2026, 7, 1, 9, 34, tzinfo=UTC),
        started_at=datetime(2026, 7, 1, 9, 29, tzinfo=UTC),
    )
    never_started = ParseTask(
        id=uuid.uuid4(),
        document_id=document_id,
        status=ParseTaskStatus.pending,
        parser_name="manual-retry-text",
        retry_count=2,
        created_at=datetime(2026, 7, 1, 9, 36, tzinfo=UTC),
        started_at=None,
    )
    session = _DetailSession(
        document=document,
        tasks=[
            started_later_created_earlier,
            created_later_started_earlier,
            never_started,
        ],
        segments=[],
    )

    detail = get_document_detail(session, document_id)

    assert detail is not None
    assert [task.id for task in detail.recentTasks] == [
        started_later_created_earlier.id,
        created_later_started_earlier.id,
        never_started.id,
    ]
    assert detail.latestTask is not None
    assert detail.latestTask.id == started_later_created_earlier.id


def test_get_document_detail_returns_none_for_missing_document():
    from app.services.document_management import get_document_detail

    assert get_document_detail(_DetailSession(document=None), uuid.uuid4()) is None
