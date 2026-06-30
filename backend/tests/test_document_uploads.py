import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy.exc import IntegrityError

from app.core.config import PROJECT_ROOT, Settings
from app.models.rag import (
    DocumentStatus,
    KbDocument,
    KbDocumentSegment,
    ParseTask,
    ParseTaskStatus,
)
from app.schemas.documents import DocumentUploadErrorSchema
from app.services import document_uploads as document_uploads_service
from app.services.document_uploads import (
    UploadedFileData,
    document_type_from_filename,
    file_sha256,
    safe_upload_filename,
    upload_document_file,
    validate_upload_file,
)


def test_default_upload_settings_point_to_ignored_backend_uploads(monkeypatch):
    monkeypatch.delenv("UPLOAD_STORAGE_DIR", raising=False)
    monkeypatch.delenv("UPLOAD_MAX_BYTES", raising=False)
    settings = Settings(_env_file=None)

    assert settings.upload_storage_dir == PROJECT_ROOT / "backend" / "uploads" / "documents"
    assert settings.upload_max_bytes == 20 * 1024 * 1024


def test_relative_upload_storage_dir_resolves_against_project_root():
    settings = Settings(
        upload_storage_dir=Path("backend/uploads/documents"),
        _env_file=None,
    )

    assert settings.upload_storage_dir == PROJECT_ROOT / "backend" / "uploads" / "documents"


def test_document_upload_error_schema_contains_message():
    error = DocumentUploadErrorSchema(message="文件过大")

    assert error.message == "文件过大"


def test_safe_upload_filename_removes_path_and_unsafe_characters():
    assert safe_upload_filename("..\\\u9006\u53d8\u5668?\u8fd0\u7ef4\u624b\u518c.md") == "\u9006\u53d8\u5668_\u8fd0\u7ef4\u624b\u518c.md"
    assert safe_upload_filename("../../bad name?.txt") == "bad_name_.txt"


def test_safe_upload_filename_handles_windows_drive_and_unc_paths():
    assert safe_upload_filename("C:\\dir\\file.md") == "file.md"
    assert safe_upload_filename("\\\\server\\share\\a.txt") == "a.txt"


def test_document_type_from_filename_maps_supported_extensions():
    assert document_type_from_filename("a.pdf") == "PDF"
    assert document_type_from_filename("a.docx") == "Word"
    assert document_type_from_filename("a.xlsx") == "Excel"
    assert document_type_from_filename("a.markdown") == "Markdown"
    assert document_type_from_filename("a.txt") == "TXT"


def test_document_type_from_filename_rejects_unknown_extension():
    with pytest.raises(ValueError, match="不支持的文件类型"):
        document_type_from_filename("a.exe")


def test_validate_upload_file_rejects_empty_and_oversized_files():
    with pytest.raises(ValueError, match="\u6587\u4ef6\u5185\u5bb9\u4e3a\u7a7a"):
        validate_upload_file(UploadedFileData(filename="a.md", content=b""), max_bytes=10)

    with pytest.raises(ValueError, match="\u6587\u4ef6\u8d85\u8fc7\u5927\u5c0f\u9650\u5236"):
        validate_upload_file(UploadedFileData(filename="a.md", content=b"123456"), max_bytes=5)


def test_validate_upload_file_rejects_unknown_extension():
    with pytest.raises(ValueError, match="\u4e0d\u652f\u6301\u7684\u6587\u4ef6\u7c7b\u578b"):
        validate_upload_file(UploadedFileData(filename="a.exe", content=b"hello"), max_bytes=100)


@pytest.mark.parametrize("filename", ["CON.md", "NUL.txt", "COM1.docx"])
def test_validate_upload_file_rejects_windows_reserved_device_names(filename):
    with pytest.raises(ValueError, match="文件名不能使用 Windows 保留名称"):
        validate_upload_file(UploadedFileData(filename=filename, content=b"hello"), max_bytes=100)


def test_validate_upload_file_rejects_reserved_name_before_sanitizing():
    with pytest.raises(ValueError, match="文件名不能使用 Windows 保留名称"):
        validate_upload_file(UploadedFileData(filename="CON?.md", content=b"hello"), max_bytes=100)


class _ScalarResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class _UploadSession:
    def __init__(self, existing_document=None):
        self.existing_document = existing_document
        self.added = []
        self.commits = 0
        self.flushes = 0
        self.refreshed = []
        self.documents_by_id = {}

    def execute(self, statement):
        return _ScalarResult(self.existing_document)

    def add(self, item):
        self.added.append(item)
        if isinstance(item, KbDocument) and getattr(item, "id", None) is not None:
            self.documents_by_id[item.id] = item

    def flush(self):
        self.flushes += 1
        now = datetime(2026, 6, 30, 15, 0, 0, tzinfo=UTC)
        for item in self.added:
            if getattr(item, "id", None) is None:
                item.id = uuid.uuid4()
            if getattr(item, "created_at", None) is None:
                item.created_at = now
            if getattr(item, "updated_at", None) is None:
                item.updated_at = now
            if isinstance(item, KbDocument):
                self.documents_by_id[item.id] = item

    def commit(self):
        self.commits += 1
        self.flush()

    def refresh(self, item):
        self.refreshed.append(item)

    def get(self, model, item_id):
        if model is KbDocument:
            return self.documents_by_id.get(item_id)
        return None


class _IntegrityRaceSession(_UploadSession):
    def __init__(self, existing_after_rollback):
        super().__init__()
        self.existing_after_rollback = existing_after_rollback
        self.execute_calls = 0
        self.rollbacks = 0

    def execute(self, statement):
        self.execute_calls += 1
        if self.execute_calls == 1:
            return _ScalarResult(None)
        return _ScalarResult(self.existing_after_rollback)

    def flush(self):
        if any(isinstance(item, KbDocument) for item in self.added):
            raise IntegrityError("insert kb_document", {}, Exception("duplicate sha"))
        super().flush()

    def rollback(self):
        self.rollbacks += 1


class _SupportedIntegrityRaceSession(_UploadSession):
    def __init__(self, existing_after_rollback):
        super().__init__()
        self.existing_after_rollback = existing_after_rollback
        self.execute_calls = 0
        self.rollbacks = 0

    def execute(self, statement):
        self.execute_calls += 1
        if self.execute_calls <= 2:
            return _ScalarResult(None)
        return _ScalarResult(self.existing_after_rollback)

    def flush(self):
        if any(isinstance(item, KbDocument) for item in self.added):
            raise IntegrityError("insert kb_document", {}, Exception("duplicate sha"))
        super().flush()

    def rollback(self):
        self.rollbacks += 1


class _FakeEmbeddingClient:
    async def embed(self, texts):
        return [[0.1, 0.2] for _ in texts]


@pytest.mark.asyncio
async def test_upload_document_file_returns_existing_duplicate_document(tmp_path):
    content = b"# Existing\n\ncontent"
    existing = KbDocument(
        id=uuid.uuid4(),
        title="已有文档",
        file_name="existing.md",
        file_type="markdown",
        file_sha256=file_sha256(content),
        status=DocumentStatus.ready,
        enabled=True,
        segment_count=1,
        document_metadata={"source_file_name": "existing.md", "category": "manual"},
        updated_at=datetime(2026, 6, 30, 15, 0, 0, tzinfo=UTC),
    )
    session = _UploadSession(existing_document=existing)

    item = await upload_document_file(
        session=session,
        file_data=UploadedFileData(filename="existing.md", content=content),
        upload_dir=tmp_path,
        max_bytes=1000,
        embedding_client=_FakeEmbeddingClient(),
        embedding_model="test-embedding",
    )

    assert item.id == existing.id
    assert item.name == "existing.md"
    assert item.parseStatus == "ready"
    assert session.added == []
    assert list(tmp_path.iterdir()) == []


@pytest.mark.asyncio
async def test_upload_document_file_creates_failed_record_for_unsupported_pdf(tmp_path):
    session = _UploadSession()

    item = await upload_document_file(
        session=session,
        file_data=UploadedFileData(filename="设备资料.pdf", content=b"%PDF test"),
        upload_dir=tmp_path,
        max_bytes=1000,
        embedding_client=_FakeEmbeddingClient(),
        embedding_model="test-embedding",
    )

    document = next(item for item in session.added if isinstance(item, KbDocument))
    task = next(item for item in session.added if isinstance(item, ParseTask))

    assert document.file_name == "设备资料.pdf"
    assert document.file_type == "pdf"
    assert document.status == DocumentStatus.failed
    assert document.enabled is False
    assert document.document_metadata["source_file_name"] == "设备资料.pdf"
    assert document.document_metadata["category"] == "uncategorized"
    assert "暂不支持解析 PDF" in document.error_message
    assert task.status == ParseTaskStatus.failed
    assert task.parser_name == "unsupported-upload-placeholder"
    assert task.error_message == document.error_message
    assert item.parseStatus == "failed"
    assert item.enableStatus == "disabled"
    assert item.failureReason == document.error_message
    assert (tmp_path / f"{document.file_sha256}_设备资料.pdf").exists()


@pytest.mark.asyncio
async def test_upload_document_file_imports_markdown_text(tmp_path):
    session = _UploadSession()

    item = await upload_document_file(
        session=session,
        file_data=UploadedFileData(
            filename="新上传运维资料.md",
            content="# 新上传运维资料\n\n## 检查步骤\n\n检查逆变器运行状态。".encode("utf-8"),
        ),
        upload_dir=tmp_path,
        max_bytes=2000,
        embedding_client=_FakeEmbeddingClient(),
        embedding_model="test-embedding",
    )

    document = next(item for item in session.added if isinstance(item, KbDocument))
    segments = [item for item in session.added if isinstance(item, KbDocumentSegment)]

    assert document.file_name == "新上传运维资料.md"
    assert document.file_type == "markdown"
    assert document.source_path == str(tmp_path / f"{document.file_sha256}_新上传运维资料.md")
    assert document.status == DocumentStatus.ready
    assert document.enabled is True
    assert document.document_metadata["source_file_name"] == "新上传运维资料.md"
    assert document.document_metadata["category"] == "uncategorized"
    assert segments
    assert item.parseStatus == "ready"
    assert item.enableStatus == "enabled"
    assert item.category == "uncategorized"


@pytest.mark.asyncio
async def test_upload_document_file_rejects_non_utf8_text(tmp_path):
    session = _UploadSession()

    with pytest.raises(ValueError, match="文本文件必须使用 UTF-8 编码"):
        await upload_document_file(
            session=session,
            file_data=UploadedFileData(filename="bad.txt", content=b"\xff\xfe\x00"),
            upload_dir=tmp_path,
            max_bytes=1000,
            embedding_client=_FakeEmbeddingClient(),
            embedding_model="test-embedding",
        )

    assert list(tmp_path.iterdir()) == []


@pytest.mark.asyncio
async def test_upload_document_file_does_not_mutate_duplicate_returned_by_ingest(
    monkeypatch,
    tmp_path,
):
    content = "# Duplicate\n\nbody".encode("utf-8")
    existing = KbDocument(
        id=uuid.uuid4(),
        title="Original",
        file_name="original.md",
        file_type="markdown",
        file_sha256=file_sha256(content),
        status=DocumentStatus.ready,
        enabled=True,
        segment_count=1,
        document_metadata={"source_file_name": "original.md", "category": "manual"},
        source_path="seed/original.md",
        updated_at=datetime(2026, 6, 30, 15, 0, 0, tzinfo=UTC),
    )
    session = _UploadSession()
    session.documents_by_id[existing.id] = existing

    async def fake_import_markdown_document_with_result(**kwargs):
        return existing.id, False

    monkeypatch.setattr(
        document_uploads_service,
        "import_markdown_document_with_result",
        fake_import_markdown_document_with_result,
        raising=False,
    )

    item = await upload_document_file(
        session=session,
        file_data=UploadedFileData(filename="new-name.md", content=content),
        upload_dir=tmp_path,
        max_bytes=1000,
        embedding_client=_FakeEmbeddingClient(),
        embedding_model="test-embedding",
    )

    assert item.id == existing.id
    assert item.name == "original.md"
    assert existing.file_name == "original.md"
    assert existing.source_path == "seed/original.md"
    assert existing.document_metadata == {"source_file_name": "original.md", "category": "manual"}
    assert session.commits == 0


@pytest.mark.asyncio
async def test_upload_document_file_keeps_same_path_duplicate_source_file(
    monkeypatch,
    tmp_path,
):
    content = "# Same\n\nbody".encode("utf-8")
    sha256 = file_sha256(content)
    source_path = tmp_path / f"{sha256}_same-name.md"
    source_path.write_bytes(content)
    existing = KbDocument(
        id=uuid.uuid4(),
        title="Same",
        file_name="same-name.md",
        file_type="markdown",
        file_sha256=sha256,
        status=DocumentStatus.ready,
        enabled=True,
        segment_count=1,
        document_metadata={"source_file_name": "same-name.md", "category": "manual"},
        source_path=str(source_path),
        updated_at=datetime(2026, 6, 30, 15, 0, 0, tzinfo=UTC),
    )
    session = _UploadSession()
    session.documents_by_id[existing.id] = existing

    async def fake_import_markdown_document_with_result(**kwargs):
        return existing.id, False

    monkeypatch.setattr(
        document_uploads_service,
        "import_markdown_document_with_result",
        fake_import_markdown_document_with_result,
        raising=False,
    )

    item = await upload_document_file(
        session=session,
        file_data=UploadedFileData(filename="same-name.md", content=content),
        upload_dir=tmp_path,
        max_bytes=1000,
        embedding_client=_FakeEmbeddingClient(),
        embedding_model="test-embedding",
    )

    assert item.id == existing.id
    assert item.name == "same-name.md"
    assert source_path.exists()
    assert source_path.read_bytes() == content


@pytest.mark.asyncio
async def test_upload_document_file_recovers_unsupported_unique_race(tmp_path):
    content = b"%PDF race"
    existing = KbDocument(
        id=uuid.uuid4(),
        title="Existing PDF",
        file_name="existing.pdf",
        file_type="pdf",
        file_sha256=file_sha256(content),
        status=DocumentStatus.failed,
        enabled=False,
        segment_count=0,
        error_message="already recorded",
        document_metadata={"source_file_name": "existing.pdf", "category": "uncategorized"},
        updated_at=datetime(2026, 6, 30, 15, 0, 0, tzinfo=UTC),
    )
    session = _IntegrityRaceSession(existing_after_rollback=existing)

    item = await upload_document_file(
        session=session,
        file_data=UploadedFileData(filename="race.pdf", content=content),
        upload_dir=tmp_path,
        max_bytes=1000,
        embedding_client=_FakeEmbeddingClient(),
        embedding_model="test-embedding",
    )

    assert item.id == existing.id
    assert item.name == "existing.pdf"
    assert session.rollbacks == 1
    assert session.execute_calls == 2
    assert list(tmp_path.iterdir()) == []


@pytest.mark.asyncio
async def test_upload_document_file_recovers_supported_text_unique_race(tmp_path):
    content = "# Race\n\nbody".encode("utf-8")
    existing = KbDocument(
        id=uuid.uuid4(),
        title="Existing Markdown",
        file_name="existing.md",
        file_type="markdown",
        file_sha256=file_sha256(content),
        status=DocumentStatus.ready,
        enabled=True,
        segment_count=1,
        document_metadata={"source_file_name": "existing.md", "category": "manual"},
        updated_at=datetime(2026, 6, 30, 15, 0, 0, tzinfo=UTC),
    )
    session = _SupportedIntegrityRaceSession(existing_after_rollback=existing)

    item = await upload_document_file(
        session=session,
        file_data=UploadedFileData(filename="race.md", content=content),
        upload_dir=tmp_path,
        max_bytes=1000,
        embedding_client=_FakeEmbeddingClient(),
        embedding_model="test-embedding",
    )

    assert item.id == existing.id
    assert item.name == "existing.md"
    assert session.rollbacks >= 1
    assert session.execute_calls == 3
    assert list(tmp_path.iterdir()) == []
