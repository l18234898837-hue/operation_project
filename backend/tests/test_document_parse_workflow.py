import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy.sql.dml import Delete

from app.models.rag import (
    DocumentStatus,
    KbDocument,
    KbDocumentSegment,
    ParseTask,
    ParseTaskStatus,
)
from app.services.document_parsing import retry_document_parse


class _ScalarList:
    def __init__(self, values):
        self._values = values

    def scalars(self):
        return iter(self._values)


class FakeSession:
    def __init__(
        self,
        document=None,
        retry_counts=None,
        existing_segments=None,
        segment_add_error=None,
        fail_next_commit_after_rebuild=False,
    ):
        self.document = document
        self.retry_counts = retry_counts or []
        self.existing_segments = existing_segments or []
        self._saved_segments = None
        self.segment_add_error = segment_add_error
        self.fail_next_commit_after_rebuild = fail_next_commit_after_rebuild
        self.added = []
        self.persisted = []
        self.pending = []
        self.commits = 0
        self.refreshed = []
        self.executed = []
        self.rollbacks = 0
        self.rebuild_started = False

    def get(self, model_type, document_id):
        if (
            model_type is KbDocument
            and self.document is not None
            and document_id == self.document.id
        ):
            return self.document
        return None

    def execute(self, statement):
        self.executed.append(statement)
        if isinstance(statement, Delete):
            assert statement.table.name == KbDocumentSegment.__tablename__
            assert self.document is not None
            where_clause = statement.whereclause
            assert where_clause is not None
            compiled = statement.compile()
            assert "kb_document_segment.document_id" in str(where_clause)
            assert self.document.id in compiled.params.values()
            self._saved_segments = list(self.existing_segments)
            self.rebuild_started = True
            self.existing_segments.clear()
            return _ScalarList([])
        return _ScalarList(self.retry_counts)

    def add(self, item):
        if isinstance(item, KbDocumentSegment) and self.segment_add_error is not None:
            raise self.segment_add_error
        if getattr(item, "id", None) is None:
            item.id = uuid.uuid4()
        self.added.append(item)
        self.pending.append(item)

    def commit(self):
        self.commits += 1
        if self.fail_next_commit_after_rebuild and self.rebuild_started:
            self.fail_next_commit_after_rebuild = False
            raise RuntimeError("commit unavailable")
        self.persisted.extend(self.pending)
        self.pending.clear()
        self._saved_segments = None

    def refresh(self, item):
        self.refreshed.append(item)

    def rollback(self):
        self.rollbacks += 1
        self.pending.clear()
        if self._saved_segments is not None:
            self.existing_segments = self._saved_segments
            self._saved_segments = None

    def persisted_items(self, model_type):
        return [item for item in self.persisted if isinstance(item, model_type)]


class FakeEmbeddingClient:
    def __init__(self, embeddings=None, error=None):
        self.calls = []
        self._embeddings = embeddings
        self._error = error

    async def embed(self, texts):
        self.calls.append(texts)
        if self._error is not None:
            raise self._error
        return self._embeddings or [[float(index), 0.25] for index, _ in enumerate(texts)]


class FakeConverter:
    def __init__(self, markdown="# Retry PDF\n\nConverted text"):
        self.markdown = markdown
        self.calls = []

    def convert(self, source_path):
        self.calls.append(source_path)
        return self.markdown


def _document(**overrides):
    values = {
        "id": uuid.uuid4(),
        "title": "Retry Manual",
        "source_path": None,
        "file_name": "retry.md",
        "file_type": "markdown",
        "status": DocumentStatus.failed,
        "enabled": False,
        "segment_count": 0,
        "error_message": "old failure",
        "document_metadata": {"category": "manual"},
        "updated_at": datetime(2026, 6, 30, 15, 0, 0, tzinfo=UTC),
    }
    values.update(overrides)
    return KbDocument(**values)


def _added(session, model_type):
    return [item for item in session.added if isinstance(item, model_type)]


def _persisted(session, model_type):
    return session.persisted_items(model_type)


def _markdowns(tmp_path):
    return tmp_path / "markdown" / "generated"


@pytest.mark.asyncio
async def test_supported_markdown_retry_rebuilds_segments_and_returns_ready_item(tmp_path):
    source = tmp_path / "retry.md"
    source.write_text("# Retry Manual\n\n## Reset\n\nCheck DC input.", encoding="utf-8")
    document = _document(
        source_path=str(source),
        file_sha256="b" * 64,
        segment_count=2,
    )
    session = FakeSession(
        document=document,
        retry_counts=[0, 2],
        existing_segments=[KbDocumentSegment(document_id=document.id, chunk_index=0)],
    )
    embedding_client = FakeEmbeddingClient(embeddings=[[0.1, 0.2]])

    item = await retry_document_parse(
        session=session,
        document_id=document.id,
        embedding_client=embedding_client,
        embedding_model="BAAI/bge-m3",
        markdown_storage_dir=_markdowns(tmp_path),
    )

    task = _persisted(session, ParseTask)[0]
    segments = _added(session, KbDocumentSegment)
    expected_markdown = _markdowns(tmp_path) / f"{document.file_sha256}_retry.md"

    assert document.status == DocumentStatus.ready
    assert document.enabled is True
    assert document.error_message is None
    assert document.markdown_path == str(expected_markdown)
    assert expected_markdown.read_text(encoding="utf-8") == "# Retry Manual\n\n## Reset\n\nCheck DC input."
    assert document.segment_count == 1
    assert task.status == ParseTaskStatus.success
    assert task.parser_name == "manual-retry-text"
    assert task.retry_count == 3
    assert task.error_message is None
    assert task.started_at is not None
    assert task.finished_at is not None
    assert len(segments) == 1
    assert segments[0].document_id == document.id
    assert segments[0].chunk_index == 0
    assert segments[0].heading_path == "Retry Manual > Reset"
    assert segments[0].indexed_text == "Retry Manual > Reset\nCheck DC input."
    assert segments[0].keyword_text
    assert segments[0].embedding_model == "BAAI/bge-m3"
    assert segments[0].embedding == [0.1, 0.2]
    assert session.existing_segments == []
    assert embedding_client.calls == [["Retry Manual > Reset\nCheck DC input."]]
    assert item.parseStatus == "ready"
    assert item.enableStatus == "enabled"
    assert item.failureReason is None
    assert item.progress == 100
    assert session.commits == 1
    assert session.refreshed == [document]


@pytest.mark.asyncio
async def test_pdf_retry_converts_markdown_and_rebuilds_segments(tmp_path):
    source = tmp_path / "manual.pdf"
    source.write_bytes(b"%PDF fake")
    document = _document(
        source_path=str(source),
        file_name="manual.pdf",
        file_type="pdf",
        document_metadata={"category": "cases"},
    )
    session = FakeSession(document=document)
    embedding_client = FakeEmbeddingClient(embeddings=[[0.4, 0.5]])
    converter = FakeConverter("# Retry PDF\n\n## Converted\n\nConverted text")

    item = await retry_document_parse(
        session=session,
        document_id=document.id,
        embedding_client=embedding_client,
        embedding_model="BAAI/bge-m3",
        markdown_storage_dir=_markdowns(tmp_path),
        converter=converter,
    )

    task = _persisted(session, ParseTask)[0]
    segments = _added(session, KbDocumentSegment)
    expected_markdown = _markdowns(tmp_path) / f"{document.id}_{source.stem}.md"

    assert document.status == DocumentStatus.ready
    assert document.enabled is True
    assert document.error_message is None
    assert document.markdown_path == str(expected_markdown)
    assert expected_markdown.read_text(encoding="utf-8") == "# Retry PDF\n\n## Converted\n\nConverted text"
    assert converter.calls == [source]
    assert task.status == ParseTaskStatus.success
    assert task.parser_name == "markitdown-retry"
    assert len(segments) == 1
    assert segments[0].heading_path == "Retry PDF > Converted"
    assert segments[0].embedding == [0.4, 0.5]
    assert embedding_client.calls == [["Retry PDF > Converted\nConverted text"]]
    assert item.parseStatus == "ready"
    assert item.enableStatus == "enabled"
    assert session.commits == 1
    assert session.refreshed == [document]


@pytest.mark.asyncio
async def test_embedding_failure_marks_document_and_task_failed_and_returns_failed_item(tmp_path):
    source = tmp_path / "retry.md"
    source.write_text("# Retry Manual\n\n## Reset\n\nCheck DC input.", encoding="utf-8")
    document = _document(source_path=str(source))
    old_segment = KbDocumentSegment(document_id=document.id, chunk_index=0)
    session = FakeSession(document=document, existing_segments=[old_segment])
    embedding_client = FakeEmbeddingClient(error=RuntimeError("embedding unavailable"))

    item = await retry_document_parse(
        session=session,
        document_id=document.id,
        embedding_client=embedding_client,
        embedding_model="BAAI/bge-m3",
        markdown_storage_dir=_markdowns(tmp_path),
    )

    task = _persisted(session, ParseTask)[0]
    assert document.status == DocumentStatus.failed
    assert document.enabled is False
    assert document.error_message == "embedding unavailable"
    assert task.status == ParseTaskStatus.failed
    assert task.parser_name == "manual-retry-text"
    assert task.error_message == "embedding unavailable"
    assert _added(session, KbDocumentSegment) == []
    assert session.existing_segments == [old_segment]
    assert item.parseStatus == "failed"
    assert item.enableStatus == "disabled"
    assert item.failureReason == "embedding unavailable"
    assert session.commits == 1
    assert session.refreshed == [document]


@pytest.mark.asyncio
async def test_segment_insert_failure_rolls_back_delete_and_persists_failed_task_separately(
    tmp_path,
):
    source = tmp_path / "retry.md"
    source.write_text("# Retry Manual\n\n## Reset\n\nCheck DC input.", encoding="utf-8")
    document = _document(source_path=str(source), segment_count=1)
    old_segment = KbDocumentSegment(document_id=document.id, chunk_index=0)
    session = FakeSession(
        document=document,
        existing_segments=[old_segment],
        segment_add_error=RuntimeError("segment insert unavailable"),
    )
    embedding_client = FakeEmbeddingClient(embeddings=[[0.1, 0.2]])

    item = await retry_document_parse(
        session=session,
        document_id=document.id,
        embedding_client=embedding_client,
        embedding_model="BAAI/bge-m3",
        markdown_storage_dir=_markdowns(tmp_path),
    )

    task = _persisted(session, ParseTask)[0]
    assert session.rollbacks == 1
    assert session.existing_segments == [old_segment]
    assert document.status == DocumentStatus.failed
    assert document.enabled is False
    assert document.error_message == "segment insert unavailable"
    assert task.status == ParseTaskStatus.failed
    assert task.error_message == "segment insert unavailable"
    assert item.parseStatus == "failed"
    assert item.enableStatus == "disabled"
    assert item.failureReason == "segment insert unavailable"
    assert session.commits == 1
    assert session.refreshed == [document]


@pytest.mark.asyncio
async def test_rebuild_commit_failure_rolls_back_and_persists_fresh_failed_task(
    tmp_path,
):
    source = tmp_path / "retry.md"
    source.write_text("# Retry Manual\n\n## Reset\n\nCheck DC input.", encoding="utf-8")
    document = _document(source_path=str(source), segment_count=1)
    old_segment = KbDocumentSegment(document_id=document.id, chunk_index=0)
    session = FakeSession(
        document=document,
        existing_segments=[old_segment],
        fail_next_commit_after_rebuild=True,
    )
    embedding_client = FakeEmbeddingClient(embeddings=[[0.1, 0.2]])

    item = await retry_document_parse(
        session=session,
        document_id=document.id,
        embedding_client=embedding_client,
        embedding_model="BAAI/bge-m3",
        markdown_storage_dir=_markdowns(tmp_path),
    )

    persisted_tasks = _persisted(session, ParseTask)
    assert session.rollbacks == 1
    assert session.commits == 2
    assert session.existing_segments == [old_segment]
    assert len(persisted_tasks) == 1
    assert persisted_tasks[0].status == ParseTaskStatus.failed
    assert persisted_tasks[0].parser_name == "manual-retry-text"
    assert persisted_tasks[0].error_message == "commit unavailable"
    assert document.status == DocumentStatus.failed
    assert document.enabled is False
    assert document.error_message == "commit unavailable"
    assert item.parseStatus == "failed"
    assert item.enableStatus == "disabled"
    assert item.failureReason == "commit unavailable"
    assert session.refreshed == [document]

