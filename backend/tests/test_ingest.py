import hashlib
import uuid
from pathlib import Path

import pytest

from app.models.rag import (
    DocumentStatus,
    KbDocument,
    KbDocumentSegment,
    ParseTask,
    ParseTaskStatus,
)
from app.services.ingest import MarkdownDocument, import_markdown_document, load_markdown_documents


class _ScalarResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class FakeSession:
    def __init__(self, existing_document=None, flush_error=None, commit_error=None):
        self.existing_document = existing_document
        self.flush_error = flush_error
        self.commit_error = commit_error
        self.added = []
        self.commits = 0
        self.flushes = 0
        self.rollbacks = 0

    def execute(self, statement):
        return _ScalarResult(self.existing_document)

    def add(self, item):
        self.added.append(item)

    def flush(self):
        self.flushes += 1
        if self.flush_error is not None:
            raise self.flush_error
        for item in self.added:
            if getattr(item, "id", None) is None:
                item.id = uuid.uuid4()

    def commit(self):
        self.commits += 1
        if self.commit_error is not None:
            raise self.commit_error

    def rollback(self):
        self.rollbacks += 1


class FakeEmbeddingClient:
    def __init__(self, embeddings=None, error=None):
        self.calls = []
        self._embeddings = embeddings
        self._error = error

    async def embed(self, texts):
        self.calls.append(texts)
        if self._error is not None:
            raise self._error
        return self._embeddings or [[float(index), 0.5] for index, _ in enumerate(texts)]


def _added(session, model_type):
    return [item for item in session.added if isinstance(item, model_type)]


def test_import_script_has_sys_path_bootstrap_and_main_guard():
    script = Path("backend/scripts/import_knowledge_base.py")
    source = script.read_text(encoding="utf-8")

    assert "sys.path" in source
    assert "if __name__ == \"__main__\":" in source
    assert source.index("sys.path") < source.index("from app.")


def test_load_markdown_documents_reads_top_level_md_and_derives_title_and_hash(tmp_path):
    source = tmp_path / "data" / "knowledge_base" / "markdown"
    source.mkdir(parents=True)
    nested = source / "nested"
    nested.mkdir()

    first_bytes = "# 标题\n\n内容".encode("utf-8")
    second_bytes = "# 第二篇\n\n内容".encode("utf-8")
    (source / "01_逆变器故障与维护.md").write_bytes(first_bytes)
    (source / "02-巡检 标准.md").write_bytes(second_bytes)
    (source / "ignored.csv").write_text("name,value", encoding="utf-8")
    (nested / "03_嵌套.md").write_text("# 不读取", encoding="utf-8")

    documents = load_markdown_documents(source)

    assert [document.path.name for document in documents] == [
        "01_逆变器故障与维护.md",
        "02-巡检 标准.md",
    ]
    assert [document.title for document in documents] == ["逆变器故障与维护", "巡检 标准"]
    assert documents[0].content == "# 标题\n\n内容"
    assert documents[0].file_sha256 == hashlib.sha256(first_bytes).hexdigest()
    assert documents[1].file_sha256 == hashlib.sha256(second_bytes).hexdigest()


@pytest.mark.asyncio
async def test_import_markdown_document_creates_document_task_and_segments():
    document = MarkdownDocument(
        path=Path("01_逆变器故障与维护.md"),
        title="逆变器故障与维护",
        content="# 逆变器故障与维护\n\n## PV 过压\n\n检查组串电压。",
        file_sha256="abc123",
    )
    session = FakeSession()
    embedding_client = FakeEmbeddingClient(embeddings=[[0.1, 0.2]])

    document_id = await import_markdown_document(
        session=session,
        document=document,
        embedding_client=embedding_client,
        embedding_model="BAAI/bge-m3",
    )

    created_document = _added(session, KbDocument)[0]
    task = _added(session, ParseTask)[0]
    segments = _added(session, KbDocumentSegment)

    assert document_id == created_document.id
    assert created_document.title == "逆变器故障与维护"
    assert created_document.source_path == "01_逆变器故障与维护.md"
    assert created_document.file_name == "01_逆变器故障与维护.md"
    assert created_document.file_sha256 == "abc123"
    assert created_document.file_type == "markdown"
    assert created_document.status == DocumentStatus.ready
    assert created_document.enabled is True
    assert created_document.error_message is None
    assert created_document.document_metadata == {"source_file_name": "01_逆变器故障与维护.md"}
    assert created_document.segment_count == 1

    assert task.document_id == created_document.id
    assert task.status == ParseTaskStatus.success
    assert task.retry_count == 0
    assert task.error_message is None
    assert task.finished_at is not None
    assert task.duration_ms is not None

    assert len(segments) == 1
    segment = segments[0]
    assert segment.document_id == created_document.id
    assert segment.chunk_index == 0
    assert segment.heading_path == "逆变器故障与维护 > PV 过压"
    assert segment.section_title == "PV 过压"
    assert segment.raw_text == "检查组串电压。"
    assert segment.clean_text == "检查组串电压。"
    assert segment.indexed_text == "逆变器故障与维护 > PV 过压\n检查组串电压。"
    assert "逆变器" in segment.keyword_text
    assert segment.token_count is None
    assert segment.char_count == 6
    assert segment.embedding_model == "BAAI/bge-m3"
    assert segment.embedding == [0.1, 0.2]
    assert segment.segment_metadata["source_title"] == "逆变器故障与维护"
    assert embedding_client.calls == [["逆变器故障与维护 > PV 过压\n检查组串电压。"]]
    assert session.commits == 1


@pytest.mark.asyncio
async def test_import_markdown_document_returns_existing_id_for_duplicate_sha_without_embedding():
    existing_id = uuid.uuid4()
    existing_document = KbDocument(
        id=existing_id,
        title="已有文档",
        file_sha256="duplicate",
        status=DocumentStatus.ready,
        enabled=True,
    )
    session = FakeSession(existing_document=existing_document)
    embedding_client = FakeEmbeddingClient()

    document_id = await import_markdown_document(
        session=session,
        document=MarkdownDocument(
            path=Path("01_重复.md"),
            title="重复",
            content="# 重复\n\n内容",
            file_sha256="duplicate",
        ),
        embedding_client=embedding_client,
        embedding_model="BAAI/bge-m3",
    )

    assert document_id == existing_id
    assert embedding_client.calls == []
    assert _added(session, KbDocumentSegment) == []
    assert session.commits == 0


@pytest.mark.asyncio
async def test_import_markdown_document_marks_document_and_task_failed_when_embedding_raises():
    session = FakeSession()
    embedding_client = FakeEmbeddingClient(error=RuntimeError("embedding unavailable"))

    with pytest.raises(RuntimeError, match="embedding unavailable"):
        await import_markdown_document(
            session=session,
            document=MarkdownDocument(
                path=Path("01_失败.md"),
                title="失败",
                content="# 失败\n\n## 告警\n\n检查设备。",
                file_sha256="failed-sha",
            ),
            embedding_client=embedding_client,
            embedding_model="BAAI/bge-m3",
        )

    created_document = _added(session, KbDocument)[0]
    task = _added(session, ParseTask)[0]
    assert created_document.status == DocumentStatus.failed
    assert created_document.error_message == "embedding unavailable"
    assert task.status == ParseTaskStatus.failed
    assert task.error_message == "embedding unavailable"
    assert task.finished_at is not None
    assert task.duration_ms is not None
    assert session.commits == 1


@pytest.mark.asyncio
async def test_import_markdown_document_marks_failed_when_no_chunks_are_produced():
    session = FakeSession()
    embedding_client = FakeEmbeddingClient()

    with pytest.raises(ValueError, match="No chunks produced for 01_empty.md"):
        await import_markdown_document(
            session=session,
            document=MarkdownDocument(
                path=Path("01_empty.md"),
                title="empty",
                content="# Empty only",
                file_sha256="empty-sha",
            ),
            embedding_client=embedding_client,
            embedding_model="BAAI/bge-m3",
        )

    created_document = _added(session, KbDocument)[0]
    task = _added(session, ParseTask)[0]
    assert created_document.status == DocumentStatus.failed
    assert created_document.error_message == "No chunks produced for 01_empty.md"
    assert task.status == ParseTaskStatus.failed
    assert task.error_message == "No chunks produced for 01_empty.md"
    assert embedding_client.calls == []
    assert session.commits == 1


@pytest.mark.asyncio
async def test_import_markdown_document_rolls_back_and_does_not_commit_after_flush_failure():
    session = FakeSession(flush_error=RuntimeError("flush failed"))
    embedding_client = FakeEmbeddingClient()

    with pytest.raises(RuntimeError, match="flush failed"):
        await import_markdown_document(
            session=session,
            document=MarkdownDocument(
                path=Path("01_flush.md"),
                title="flush",
                content="# Flush\n\nbody",
                file_sha256="flush-sha",
            ),
            embedding_client=embedding_client,
            embedding_model="BAAI/bge-m3",
        )

    assert embedding_client.calls == []
    assert session.rollbacks == 1
    assert session.commits == 0


@pytest.mark.asyncio
async def test_import_markdown_document_rolls_back_and_preserves_original_error_when_failure_commit_fails():
    session = FakeSession(commit_error=RuntimeError("commit failed"))
    embedding_client = FakeEmbeddingClient(error=RuntimeError("embedding unavailable"))

    with pytest.raises(RuntimeError, match="embedding unavailable"):
        await import_markdown_document(
            session=session,
            document=MarkdownDocument(
                path=Path("01_commit.md"),
                title="commit",
                content="# Commit\n\n## Alarm\n\nbody",
                file_sha256="commit-sha",
            ),
            embedding_client=embedding_client,
            embedding_model="BAAI/bge-m3",
        )

    created_document = _added(session, KbDocument)[0]
    task = _added(session, ParseTask)[0]
    assert created_document.status == DocumentStatus.failed
    assert created_document.error_message == "embedding unavailable"
    assert task.status == ParseTaskStatus.failed
    assert task.error_message == "embedding unavailable"
    assert session.commits == 1
    assert session.rollbacks == 1
