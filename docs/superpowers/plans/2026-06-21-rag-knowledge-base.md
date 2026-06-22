# RAG Knowledge Base Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first-stage RAG knowledge base minimum loop from the existing Markdown knowledge documents: schema, ingestion, embedding, vector retrieval, keyword retrieval, RRF fusion, reranking, and Top 5 evidence output.

**Architecture:** The backend keeps PostgreSQL as the source of truth and pgvector as the dense vector store. Markdown files are parsed into heading-aware chunks, embedded with SiliconFlow `BAAI/bge-m3`, retrieved by both pgvector cosine search and PostgreSQL keyword search, fused with RRF, then refined by SiliconFlow `BAAI/bge-reranker-v2-m3`. The initial deliverable is a command-line verification path, not the full QA API or frontend.

**Tech Stack:** FastAPI, SQLAlchemy 2.0, Alembic, PostgreSQL 16, pgvector, pg_trgm, jieba, psycopg, Pydantic Settings, SiliconFlow Embeddings API, SiliconFlow Rerank API.

---

## Current Project Facts

- Project root: `D:\桌面\文件\operation_project`
- Backend package root: `backend/app`
- Existing database session: `backend/app/db/session.py`
- Existing settings: `backend/app/core/config.py`
- Existing model directory: `backend/app/models`
- Existing service directory: `backend/app/services`
- Existing knowledge source directory: `data/knowledge_base/markdown`
- PostgreSQL data directory confirmed earlier: `D:/PostgreSQL/16/data`
- PostgreSQL database: `operation_pv`
- Embedding model: `BAAI/bge-m3`
- Embedding dimension: `1024`
- Rerank model: `BAAI/bge-reranker-v2-m3`
- Chat model for later QA work: `deepseek-ai/DeepSeek-V4-Flash`

## File Structure

Create these files:

- `backend/alembic.ini`: Alembic configuration that points migrations at `backend/alembic`.
- `backend/alembic/env.py`: Alembic environment that imports SQLAlchemy metadata from app models.
- `backend/alembic/script.py.mako`: Alembic revision template.
- `backend/alembic/versions/20260621_0001_create_rag_tables.py`: Initial migration for RAG tables, extensions, and indexes.
- `backend/app/db/base.py`: Declarative SQLAlchemy base.
- `backend/app/models/rag.py`: RAG database models.
- `backend/app/services/markdown_chunker.py`: Markdown heading tree parser and chunking rules.
- `backend/app/services/siliconflow.py`: Embedding and rerank HTTP clients.
- `backend/app/services/keyword_index.py`: Keyword tokenization helper for PostgreSQL keyword search.
- `backend/app/services/ingest.py`: Markdown ingestion orchestration.
- `backend/app/services/retrieval.py`: Vector search, keyword search, RRF, rerank orchestration.
- `backend/scripts/import_knowledge_base.py`: CLI script that imports `data/knowledge_base/markdown/*.md`.
- `backend/scripts/query_knowledge_base.py`: CLI script that prints Top 5 evidence chunks for a user query.
- `backend/tests/test_markdown_chunker.py`: Chunking behavior tests.
- `backend/tests/test_rrf.py`: RRF ranking tests.
- `backend/tests/test_config.py`: Settings coverage for rerank and model configuration.
- `backend/tests/test_keyword_index.py`: Tokenization and indexed text tests.

Modify these files:

- `backend/app/core/config.py`: Add RAG, embedding, rerank, and retrieval tunables if missing.
- `backend/app/models/__init__.py`: Export RAG models so Alembic sees metadata.
- `backend/requirements.txt`: Add `python-dotenv` only if scripts need explicit `.env` loading outside Pydantic settings. Keep existing dependencies if already sufficient.
- `.env.example`: Keep model configuration examples with placeholder API keys only.

Do not modify these files during this plan:

- `.env`: Contains local secrets.
- Frontend files.
- Existing knowledge Markdown source files under `data/knowledge_base/markdown`.

---

### Task 1: Add Database Base And Alembic Skeleton

**Files:**
- Create: `backend/app/db/base.py`
- Create: `backend/alembic.ini`
- Create: `backend/alembic/env.py`
- Create: `backend/alembic/script.py.mako`
- Modify: `backend/app/models/__init__.py`

- [ ] **Step 1: Write the failing metadata import test**

Create `backend/tests/test_db_metadata.py`:

```python
from app.db.base import Base


def test_base_metadata_is_available():
    assert Base.metadata is not None
    assert Base.metadata.tables == {}
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
$env:PYTHONPATH='D:\桌面\文件\operation_project\backend'
backend\.venv\Scripts\python.exe -m pytest backend\tests\test_db_metadata.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'app.db.base'`.

- [ ] **Step 3: Create SQLAlchemy declarative base**

Create `backend/app/db/base.py`:

```python
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
```

- [ ] **Step 4: Export models package without side effects**

Update `backend/app/models/__init__.py`:

```python
from app.db.base import Base

__all__ = ["Base"]
```

- [ ] **Step 5: Create Alembic config**

Create `backend/alembic.ini`:

```ini
[alembic]
script_location = alembic
prepend_sys_path = .
timezone = UTC

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

- [ ] **Step 6: Create Alembic environment**

Create `backend/alembic/env.py`:

```python
from logging.config import fileConfig
from pathlib import Path
import sys

from alembic import context
from sqlalchemy import engine_from_config, pool

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import settings
from app.db.base import Base
import app.models.rag  # noqa: F401

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

- [ ] **Step 7: Create Alembic revision template**

Create `backend/alembic/script.py.mako`:

```python
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

revision: str = ${repr(up_revision)}
down_revision: Union[str, None] = ${repr(down_revision)}
branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)}
depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
```

- [ ] **Step 8: Run test to verify it passes**

Run:

```powershell
$env:PYTHONPATH='D:\桌面\文件\operation_project\backend'
backend\.venv\Scripts\python.exe -m pytest backend\tests\test_db_metadata.py -v
```

Expected: PASS.

---

### Task 2: Add RAG Models And Migration

**Files:**
- Create: `backend/app/models/rag.py`
- Create: `backend/alembic/versions/20260621_0001_create_rag_tables.py`
- Modify: `backend/app/models/__init__.py`
- Test: `backend/tests/test_db_metadata.py`

- [ ] **Step 1: Replace metadata test with table coverage**

Update `backend/tests/test_db_metadata.py`:

```python
from app.db.base import Base
import app.models.rag  # noqa: F401


def test_rag_tables_are_registered():
    expected = {
        "kb_document",
        "parse_task",
        "kb_document_segment",
        "faq_item",
        "qa_session",
        "qa_record",
        "qa_reference",
        "qa_unanswered",
    }

    assert expected.issubset(set(Base.metadata.tables))
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
$env:PYTHONPATH='D:\桌面\文件\operation_project\backend'
backend\.venv\Scripts\python.exe -m pytest backend\tests\test_db_metadata.py -v
```

Expected: FAIL because `app.models.rag` does not exist.

- [ ] **Step 3: Create RAG model enums and tables**

Create `backend/app/models/rag.py`:

```python
import enum
import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class DocumentStatus(str, enum.Enum):
    uploaded = "uploaded"
    processing = "processing"
    ready = "ready"
    failed = "failed"
    disabled = "disabled"


class ParseTaskStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    success = "success"
    failed = "failed"


class AnswerType(str, enum.Enum):
    faq = "faq"
    rag = "rag"
    fallback = "fallback"
    none = "none"


class UnansweredStatus(str, enum.Enum):
    new = "new"
    reviewed = "reviewed"
    resolved = "resolved"


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class KbDocument(TimestampMixin, Base):
    __tablename__ = "kb_document"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    source_path: Mapped[str] = mapped_column(Text, nullable=False)
    file_sha256: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    file_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[DocumentStatus] = mapped_column(Enum(DocumentStatus, name="document_status"), nullable=False, default=DocumentStatus.uploaded)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    error_message: Mapped[str | None] = mapped_column(Text)
    document_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    segments: Mapped[list["KbDocumentSegment"]] = relationship(back_populates="document", cascade="all, delete-orphan")
    tasks: Mapped[list["ParseTask"]] = relationship(back_populates="document", cascade="all, delete-orphan")


class ParseTask(TimestampMixin, Base):
    __tablename__ = "parse_task"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("kb_document.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[ParseTaskStatus] = mapped_column(Enum(ParseTaskStatus, name="parse_task_status"), nullable=False, default=ParseTaskStatus.pending)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[int | None] = mapped_column(Integer)

    document: Mapped[KbDocument] = relationship(back_populates="tasks")


class KbDocumentSegment(TimestampMixin, Base):
    __tablename__ = "kb_document_segment"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("kb_document.id", ondelete="CASCADE"), nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    heading_path: Mapped[str] = mapped_column(Text, nullable=False)
    section_title: Mapped[str | None] = mapped_column(Text)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    clean_text: Mapped[str] = mapped_column(Text, nullable=False)
    indexed_text: Mapped[str] = mapped_column(Text, nullable=False)
    keyword_text: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int | None] = mapped_column(Integer)
    char_count: Mapped[int] = mapped_column(Integer, nullable=False)
    embedding_model: Mapped[str] = mapped_column(String(128), nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(1024), nullable=False)
    segment_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    document: Mapped[KbDocument] = relationship(back_populates="segments")

    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index", name="uq_segment_document_chunk"),
    )


class FaqItem(TimestampMixin, Base):
    __tablename__ = "faq_item"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    source_document_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("kb_document.id", ondelete="SET NULL"))
    faq_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)


class QaSession(TimestampMixin, Base):
    __tablename__ = "qa_session"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str | None] = mapped_column(String(255))
    user_id: Mapped[str | None] = mapped_column(String(128))


class QaRecord(TimestampMixin, Base):
    __tablename__ = "qa_record"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("qa_session.id", ondelete="SET NULL"))
    trace_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str | None] = mapped_column(Text)
    answer_type: Mapped[AnswerType] = mapped_column(Enum(AnswerType, name="answer_type"), nullable=False)
    confidence: Mapped[float | None] = mapped_column(Numeric(5, 4))
    model_name: Mapped[str | None] = mapped_column(String(128))
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    decision_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)


class QaReference(TimestampMixin, Base):
    __tablename__ = "qa_reference"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    qa_record_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("qa_record.id", ondelete="CASCADE"), nullable=False)
    segment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("kb_document_segment.id", ondelete="CASCADE"), nullable=False)
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("kb_document.id", ondelete="CASCADE"), nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    relevance_score: Mapped[float | None] = mapped_column(Numeric(8, 6))
    vector_score: Mapped[float | None] = mapped_column(Numeric(8, 6))
    keyword_score: Mapped[float | None] = mapped_column(Numeric(8, 6))
    rrf_score: Mapped[float | None] = mapped_column(Numeric(8, 6))
    excerpt: Mapped[str] = mapped_column(Text, nullable=False)
    ref_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)


class QaUnanswered(TimestampMixin, Base):
    __tablename__ = "qa_unanswered"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_question: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[UnansweredStatus] = mapped_column(Enum(UnansweredStatus, name="unanswered_status"), nullable=False, default=UnansweredStatus.new)
    resolved_note: Mapped[str | None] = mapped_column(Text)


Index("ix_kb_document_status", KbDocument.status)
Index("ix_kb_document_enabled", KbDocument.enabled)
Index("ix_parse_task_document_id", ParseTask.document_id)
Index("ix_parse_task_status", ParseTask.status)
Index("ix_segment_document_id", KbDocumentSegment.document_id)
Index("ix_segment_keyword_text_trgm", KbDocumentSegment.keyword_text, postgresql_using="gin", postgresql_ops={"keyword_text": "gin_trgm_ops"})
Index("ix_segment_indexed_text_trgm", KbDocumentSegment.indexed_text, postgresql_using="gin", postgresql_ops={"indexed_text": "gin_trgm_ops"})
Index("ix_qa_record_session_id", QaRecord.session_id)
Index("ix_qa_record_trace_id", QaRecord.trace_id)
Index("ix_qa_reference_qa_record_id", QaReference.qa_record_id)
Index("ix_qa_unanswered_status", QaUnanswered.status)
```

- [ ] **Step 4: Export model classes**

Update `backend/app/models/__init__.py`:

```python
from app.db.base import Base
from app.models.rag import (
    AnswerType,
    DocumentStatus,
    FaqItem,
    KbDocument,
    KbDocumentSegment,
    ParseTask,
    ParseTaskStatus,
    QaRecord,
    QaReference,
    QaSession,
    QaUnanswered,
    UnansweredStatus,
)

__all__ = [
    "AnswerType",
    "Base",
    "DocumentStatus",
    "FaqItem",
    "KbDocument",
    "KbDocumentSegment",
    "ParseTask",
    "ParseTaskStatus",
    "QaRecord",
    "QaReference",
    "QaSession",
    "QaUnanswered",
    "UnansweredStatus",
]
```

- [ ] **Step 5: Create manual migration**

Create `backend/alembic/versions/20260621_0001_create_rag_tables.py`:

```python
"""create rag tables

Revision ID: 20260621_0001
Revises: None
Create Date: 2026-06-21 00:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "20260621_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    document_status = postgresql.ENUM("uploaded", "processing", "ready", "failed", "disabled", name="document_status")
    parse_task_status = postgresql.ENUM("pending", "running", "success", "failed", name="parse_task_status")
    answer_type = postgresql.ENUM("faq", "rag", "fallback", "none", name="answer_type")
    unanswered_status = postgresql.ENUM("new", "reviewed", "resolved", name="unanswered_status")

    document_status.create(op.get_bind(), checkfirst=True)
    parse_task_status.create(op.get_bind(), checkfirst=True)
    answer_type.create(op.get_bind(), checkfirst=True)
    unanswered_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "kb_document",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("source_path", sa.Text(), nullable=False),
        sa.Column("file_sha256", sa.String(length=64), nullable=False),
        sa.Column("file_type", sa.String(length=32), nullable=False),
        sa.Column("status", document_status, nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("document_metadata", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("file_sha256", name="uq_kb_document_file_sha256"),
    )

    op.create_table(
        "parse_task",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("kb_document.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", parse_task_status, nullable=False),
        sa.Column("retry_count", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "kb_document_segment",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("kb_document.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("heading_path", sa.Text(), nullable=False),
        sa.Column("section_title", sa.Text(), nullable=True),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("clean_text", sa.Text(), nullable=False),
        sa.Column("indexed_text", sa.Text(), nullable=False),
        sa.Column("keyword_text", sa.Text(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=True),
        sa.Column("char_count", sa.Integer(), nullable=False),
        sa.Column("embedding_model", sa.String(length=128), nullable=False),
        sa.Column("embedding", Vector(1024), nullable=False),
        sa.Column("segment_metadata", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("document_id", "chunk_index", name="uq_segment_document_chunk"),
    )

    op.create_table(
        "faq_item",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("normalized_question", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("source_document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("kb_document.id", ondelete="SET NULL"), nullable=True),
        sa.Column("faq_metadata", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "qa_session",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("user_id", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "qa_record",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("qa_session.id", ondelete="SET NULL"), nullable=True),
        sa.Column("trace_id", sa.String(length=64), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("normalized_question", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=True),
        sa.Column("answer_type", answer_type, nullable=False),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=True),
        sa.Column("model_name", sa.String(length=128), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("decision_metadata", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("trace_id", name="uq_qa_record_trace_id"),
    )

    op.create_table(
        "qa_reference",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("qa_record_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("qa_record.id", ondelete="CASCADE"), nullable=False),
        sa.Column("segment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("kb_document_segment.id", ondelete="CASCADE"), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("kb_document.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("relevance_score", sa.Numeric(8, 6), nullable=True),
        sa.Column("vector_score", sa.Numeric(8, 6), nullable=True),
        sa.Column("keyword_score", sa.Numeric(8, 6), nullable=True),
        sa.Column("rrf_score", sa.Numeric(8, 6), nullable=True),
        sa.Column("excerpt", sa.Text(), nullable=False),
        sa.Column("ref_metadata", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "qa_unanswered",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("normalized_question", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", unanswered_status, nullable=False),
        sa.Column("resolved_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_index("ix_kb_document_status", "kb_document", ["status"])
    op.create_index("ix_kb_document_enabled", "kb_document", ["enabled"])
    op.create_index("ix_parse_task_document_id", "parse_task", ["document_id"])
    op.create_index("ix_parse_task_status", "parse_task", ["status"])
    op.create_index("ix_segment_document_id", "kb_document_segment", ["document_id"])
    op.create_index("ix_segment_keyword_text_trgm", "kb_document_segment", ["keyword_text"], postgresql_using="gin", postgresql_ops={"keyword_text": "gin_trgm_ops"})
    op.create_index("ix_segment_indexed_text_trgm", "kb_document_segment", ["indexed_text"], postgresql_using="gin", postgresql_ops={"indexed_text": "gin_trgm_ops"})
    op.create_index("ix_qa_record_session_id", "qa_record", ["session_id"])
    op.create_index("ix_qa_record_trace_id", "qa_record", ["trace_id"])
    op.create_index("ix_qa_reference_qa_record_id", "qa_reference", ["qa_record_id"])
    op.create_index("ix_qa_unanswered_status", "qa_unanswered", ["status"])

    op.execute("CREATE INDEX ix_segment_embedding_hnsw ON kb_document_segment USING hnsw (embedding vector_cosine_ops)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_segment_embedding_hnsw")
    op.drop_index("ix_qa_unanswered_status", table_name="qa_unanswered")
    op.drop_index("ix_qa_reference_qa_record_id", table_name="qa_reference")
    op.drop_index("ix_qa_record_trace_id", table_name="qa_record")
    op.drop_index("ix_qa_record_session_id", table_name="qa_record")
    op.drop_index("ix_segment_indexed_text_trgm", table_name="kb_document_segment")
    op.drop_index("ix_segment_keyword_text_trgm", table_name="kb_document_segment")
    op.drop_index("ix_segment_document_id", table_name="kb_document_segment")
    op.drop_index("ix_parse_task_status", table_name="parse_task")
    op.drop_index("ix_parse_task_document_id", table_name="parse_task")
    op.drop_index("ix_kb_document_enabled", table_name="kb_document")
    op.drop_index("ix_kb_document_status", table_name="kb_document")
    op.drop_table("qa_unanswered")
    op.drop_table("qa_reference")
    op.drop_table("qa_record")
    op.drop_table("qa_session")
    op.drop_table("faq_item")
    op.drop_table("kb_document_segment")
    op.drop_table("parse_task")
    op.drop_table("kb_document")
    postgresql.ENUM(name="unanswered_status").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="answer_type").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="parse_task_status").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="document_status").drop(op.get_bind(), checkfirst=True)
```

- [ ] **Step 6: Run metadata test**

Run:

```powershell
$env:PYTHONPATH='D:\桌面\文件\operation_project\backend'
backend\.venv\Scripts\python.exe -m pytest backend\tests\test_db_metadata.py -v
```

Expected: PASS.

- [ ] **Step 7: Run migration**

Run from `backend`:

```powershell
cd D:\桌面\文件\operation_project\backend
.\.venv\Scripts\python.exe -m alembic upgrade head
```

Expected: Alembic applies revision `20260621_0001`.

- [ ] **Step 8: Verify tables in PostgreSQL**

Run:

```powershell
$env:PGPASSWORD='<local database password from .env>'
D:\PostgreSQL\16\bin\psql.exe -h 127.0.0.1 -U postgres -d operation_pv -c "\dt"
```

Expected: output includes `kb_document`, `parse_task`, `kb_document_segment`, `faq_item`, `qa_session`, `qa_record`, `qa_reference`, and `qa_unanswered`.

---

### Task 3: Add RAG Settings

**Files:**
- Modify: `backend/app/core/config.py`
- Modify: `.env.example`
- Test: `backend/tests/test_config.py`

- [ ] **Step 1: Write settings test**

Create or update `backend/tests/test_config.py`:

```python
from app.core.config import Settings


def test_settings_reads_rag_model_configuration(monkeypatch):
    monkeypatch.setenv("EMBEDDING_BASE_URL", "https://api.siliconflow.cn/v1")
    monkeypatch.setenv("EMBEDDING_API_KEY", "embedding-key")
    monkeypatch.setenv("EMBEDDING_MODEL", "BAAI/bge-m3")
    monkeypatch.setenv("EMBEDDING_DIMENSION", "1024")
    monkeypatch.setenv("RERANK_BASE_URL", "https://api.siliconflow.cn/v1")
    monkeypatch.setenv("RERANK_API_KEY", "rerank-key")
    monkeypatch.setenv("RERANK_MODEL", "BAAI/bge-reranker-v2-m3")
    monkeypatch.setenv("RERANK_ENABLED", "true")
    monkeypatch.setenv("RERANK_TOP_N", "5")
    monkeypatch.setenv("RETRIEVAL_VECTOR_TOP_K", "20")
    monkeypatch.setenv("RETRIEVAL_KEYWORD_TOP_K", "20")
    monkeypatch.setenv("RETRIEVAL_RRF_TOP_K", "20")
    monkeypatch.setenv("RETRIEVAL_FINAL_TOP_K", "5")

    settings = Settings()

    assert settings.embedding_base_url == "https://api.siliconflow.cn/v1"
    assert settings.embedding_model == "BAAI/bge-m3"
    assert settings.embedding_dimension == 1024
    assert settings.rerank_model == "BAAI/bge-reranker-v2-m3"
    assert settings.rerank_enabled is True
    assert settings.rerank_top_n == 5
    assert settings.retrieval_vector_top_k == 20
    assert settings.retrieval_keyword_top_k == 20
    assert settings.retrieval_rrf_top_k == 20
    assert settings.retrieval_final_top_k == 5
```

- [ ] **Step 2: Run test to verify it fails for missing fields**

Run:

```powershell
$env:PYTHONPATH='D:\桌面\文件\operation_project\backend'
backend\.venv\Scripts\python.exe -m pytest backend\tests\test_config.py -v
```

Expected: FAIL if `embedding_dimension` or retrieval settings are missing.

- [ ] **Step 3: Add settings fields**

Modify `backend/app/core/config.py` inside `Settings`:

```python
    embedding_base_url: str = ""
    embedding_api_key: str = ""
    embedding_model: str = "BAAI/bge-m3"
    embedding_dimension: int = 1024

    rerank_base_url: str = ""
    rerank_api_key: str = ""
    rerank_model: str = "BAAI/bge-reranker-v2-m3"
    rerank_enabled: bool = True
    rerank_top_n: int = 5

    retrieval_vector_top_k: int = 20
    retrieval_keyword_top_k: int = 20
    retrieval_rrf_top_k: int = 20
    retrieval_final_top_k: int = 5
    retrieval_rrf_k: int = 60
```

- [ ] **Step 4: Update `.env.example` with placeholders**

Ensure `.env.example` contains:

```env
EMBEDDING_BASE_URL=https://api.siliconflow.cn/v1
EMBEDDING_API_KEY=your_api_key
EMBEDDING_MODEL=BAAI/bge-m3
EMBEDDING_DIMENSION=1024

RERANK_BASE_URL=https://api.siliconflow.cn/v1
RERANK_API_KEY=your_api_key
RERANK_MODEL=BAAI/bge-reranker-v2-m3
RERANK_ENABLED=true
RERANK_TOP_N=5

RETRIEVAL_VECTOR_TOP_K=20
RETRIEVAL_KEYWORD_TOP_K=20
RETRIEVAL_RRF_TOP_K=20
RETRIEVAL_FINAL_TOP_K=5
RETRIEVAL_RRF_K=60
```

- [ ] **Step 5: Run settings test**

Run:

```powershell
$env:PYTHONPATH='D:\桌面\文件\operation_project\backend'
backend\.venv\Scripts\python.exe -m pytest backend\tests\test_config.py -v
```

Expected: PASS.

---

### Task 4: Implement Markdown Heading Parser And Chunker

**Files:**
- Create: `backend/app/services/markdown_chunker.py`
- Test: `backend/tests/test_markdown_chunker.py`

- [ ] **Step 1: Write chunker tests**

Create `backend/tests/test_markdown_chunker.py`:

```python
from app.services.markdown_chunker import chunk_markdown


def test_chunker_adds_heading_path_to_indexed_text():
    markdown = """# 逆变器故障与维护

## 常见故障与处理

### PV 过压

原因：组串电压超过逆变器允许范围。

处理：检查组串配置、环境温度和逆变器直流输入参数。
"""

    chunks = chunk_markdown(markdown, source_title="逆变器故障与维护")

    assert len(chunks) == 1
    assert chunks[0].heading_path == "逆变器故障与维护 > 常见故障与处理 > PV 过压"
    assert chunks[0].indexed_text.startswith("逆变器故障与维护 > 常见故障与处理 > PV 过压\n")
    assert "组串电压" in chunks[0].indexed_text


def test_chunker_splits_long_section_without_crossing_heading_topic():
    paragraph = "检查逆变器直流侧、电缆接头、组件绝缘和接地情况。" * 70
    markdown = f"""# 逆变器故障与维护

## 常见故障与处理

### 绝缘阻抗低

{paragraph}

### PV 过压

短内容应留在自己的故障主题内。
"""

    chunks = chunk_markdown(markdown, source_title="逆变器故障与维护")

    insulation_chunks = [chunk for chunk in chunks if "绝缘阻抗低" in chunk.heading_path]
    overvoltage_chunks = [chunk for chunk in chunks if "PV 过压" in chunk.heading_path]
    assert len(insulation_chunks) >= 2
    assert len(overvoltage_chunks) == 1
    assert all("PV 过压" not in chunk.raw_text for chunk in insulation_chunks)


def test_chunker_merges_short_same_topic_sections():
    markdown = """# SVG与无功设备故障

## SVG 故障

### 控制器通讯异常

现象：后台无法读取 SVG 状态。

### 控制器通讯异常处理

处理：检查通讯线缆、地址配置和控制器供电。

### 功率模块故障

现象：模块告警，设备退出运行。
"""

    chunks = chunk_markdown(markdown, source_title="SVG与无功设备故障")

    merged = [chunk for chunk in chunks if "控制器通讯异常" in chunk.heading_path]
    power = [chunk for chunk in chunks if "功率模块故障" in chunk.heading_path]
    assert len(merged) == 1
    assert "通讯线缆" in merged[0].raw_text
    assert len(power) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
$env:PYTHONPATH='D:\桌面\文件\operation_project\backend'
backend\.venv\Scripts\python.exe -m pytest backend\tests\test_markdown_chunker.py -v
```

Expected: FAIL because `app.services.markdown_chunker` does not exist.

- [ ] **Step 3: Implement chunker**

Create `backend/app/services/markdown_chunker.py`:

```python
from dataclasses import dataclass
import re


MIN_DIRECT_CHARS = 250
MAX_DIRECT_CHARS = 1000
TARGET_SPLIT_MIN = 500
TARGET_SPLIT_MAX = 800
LONG_SPLIT_OVERLAP = 120


@dataclass(frozen=True)
class MarkdownChunk:
    heading_path: str
    section_title: str | None
    raw_text: str
    clean_text: str
    indexed_text: str
    char_count: int
    metadata: dict


@dataclass
class Section:
    level: int
    title: str
    heading_path: list[str]
    content: list[str]


HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")


def clean_text(text: str) -> str:
    lines = [line.rstrip() for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    compact = "\n".join(lines)
    compact = re.sub(r"\n{3,}", "\n\n", compact)
    return compact.strip()


def _parse_sections(markdown: str, source_title: str) -> list[Section]:
    stack: list[tuple[int, str]] = []
    sections: list[Section] = []
    current: Section | None = None

    for line in markdown.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        match = HEADING_RE.match(line)
        if match:
            level = len(match.group(1))
            title = match.group(2).strip()
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, title))
            path = [item[1] for item in stack]
            if path[0] != source_title:
                path = [source_title] + path
            current = Section(level=level, title=title, heading_path=path, content=[])
            sections.append(current)
            continue
        if current is None:
            current = Section(level=1, title=source_title, heading_path=[source_title], content=[])
            sections.append(current)
        current.content.append(line)

    return [section for section in sections if clean_text("\n".join(section.content))]


def _same_topic(left: Section, right: Section) -> bool:
    if left.level != right.level:
        return False
    if left.heading_path[:-1] != right.heading_path[:-1]:
        return False
    left_key = re.sub(r"(处理|原因|现象|说明)$", "", left.title)
    right_key = re.sub(r"(处理|原因|现象|说明)$", "", right.title)
    return left_key and right_key and (left_key in right_key or right_key in left_key)


def _build_chunk(section: Section, text: str, split_index: int | None = None) -> MarkdownChunk:
    cleaned = clean_text(text)
    heading_path = " > ".join(section.heading_path)
    indexed = f"{heading_path}\n{cleaned}"
    metadata = {"heading_level": section.level}
    if split_index is not None:
        metadata["split_index"] = split_index
    return MarkdownChunk(
        heading_path=heading_path,
        section_title=section.title,
        raw_text=text.strip(),
        clean_text=cleaned,
        indexed_text=indexed,
        char_count=len(cleaned),
        metadata=metadata,
    )


def _split_long_section(section: Section, text: str) -> list[MarkdownChunk]:
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        candidate = f"{current}\n\n{paragraph}".strip() if current else paragraph
        if len(candidate) <= TARGET_SPLIT_MAX:
            current = candidate
            continue
        if current:
            chunks.append(current)
        current = paragraph
    if current:
        chunks.append(current)

    balanced: list[str] = []
    for item in chunks:
        if len(item) <= MAX_DIRECT_CHARS:
            balanced.append(item)
            continue
        start = 0
        while start < len(item):
            end = min(start + TARGET_SPLIT_MAX, len(item))
            balanced.append(item[start:end])
            if end == len(item):
                break
            start = max(end - LONG_SPLIT_OVERLAP, start + 1)

    return [_build_chunk(section, item, index) for index, item in enumerate(balanced)]


def chunk_markdown(markdown: str, source_title: str) -> list[MarkdownChunk]:
    sections = _parse_sections(markdown, source_title)
    chunks: list[MarkdownChunk] = []
    index = 0

    while index < len(sections):
        section = sections[index]
        text = clean_text("\n".join(section.content))

        if len(text) > MAX_DIRECT_CHARS:
            chunks.extend(_split_long_section(section, text))
            index += 1
            continue

        if len(text) < MIN_DIRECT_CHARS and index + 1 < len(sections) and _same_topic(section, sections[index + 1]):
            next_section = sections[index + 1]
            next_text = clean_text("\n".join(next_section.content))
            merged_text = f"{section.title}\n{text}\n\n{next_section.title}\n{next_text}"
            chunks.append(_build_chunk(section, merged_text))
            index += 2
            continue

        chunks.append(_build_chunk(section, text))
        index += 1

    return chunks
```

- [ ] **Step 4: Run chunker tests**

Run:

```powershell
$env:PYTHONPATH='D:\桌面\文件\operation_project\backend'
backend\.venv\Scripts\python.exe -m pytest backend\tests\test_markdown_chunker.py -v
```

Expected: PASS.

---

### Task 5: Implement Keyword Index Helper

**Files:**
- Create: `backend/app/services/keyword_index.py`
- Test: `backend/tests/test_keyword_index.py`

- [ ] **Step 1: Write tests**

Create `backend/tests/test_keyword_index.py`:

```python
from app.services.keyword_index import build_keyword_text, normalize_query


def test_build_keyword_text_keeps_heading_and_technical_terms():
    indexed_text = "逆变器故障与维护 > 常见故障与处理 > PV 过压\n检查 PV1 电压、直流侧接线和故障码 E001。"

    keyword_text = build_keyword_text(indexed_text)

    assert "逆变器" in keyword_text
    assert "PV1" in keyword_text
    assert "E001" in keyword_text


def test_normalize_query_trims_and_compacts_whitespace():
    assert normalize_query("  逆变器   绝缘阻抗低 怎么处理  ") == "逆变器 绝缘阻抗低 怎么处理"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
$env:PYTHONPATH='D:\桌面\文件\operation_project\backend'
backend\.venv\Scripts\python.exe -m pytest backend\tests\test_keyword_index.py -v
```

Expected: FAIL because `app.services.keyword_index` does not exist.

- [ ] **Step 3: Implement helper**

Create `backend/app/services/keyword_index.py`:

```python
import re

import jieba


TECH_TOKEN_RE = re.compile(r"[A-Za-z]+[A-Za-z0-9_-]*\d*|\d+(?:\.\d+)?")


def normalize_query(query: str) -> str:
    return re.sub(r"\s+", " ", query.strip())


def build_keyword_text(indexed_text: str) -> str:
    normalized = normalize_query(indexed_text)
    jieba_tokens = [token.strip() for token in jieba.cut(normalized) if token.strip()]
    tech_tokens = TECH_TOKEN_RE.findall(normalized)
    return " ".join(dict.fromkeys([*jieba_tokens, *tech_tokens]))
```

- [ ] **Step 4: Run tests**

Run:

```powershell
$env:PYTHONPATH='D:\桌面\文件\operation_project\backend'
backend\.venv\Scripts\python.exe -m pytest backend\tests\test_keyword_index.py -v
```

Expected: PASS.

---

### Task 6: Implement SiliconFlow Embedding And Rerank Client

**Files:**
- Create: `backend/app/services/siliconflow.py`
- Test: `backend/tests/test_siliconflow_client.py`

- [ ] **Step 1: Write tests with local fake transport**

Create `backend/tests/test_siliconflow_client.py`:

```python
import httpx
import pytest

from app.services.siliconflow import SiliconFlowEmbeddingClient, SiliconFlowRerankClient


@pytest.mark.asyncio
async def test_embedding_client_validates_dimension():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "model": "BAAI/bge-m3",
                "data": [{"embedding": [0.1] * 1024, "index": 0}],
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://api.siliconflow.cn/v1")
    embedding_client = SiliconFlowEmbeddingClient(client=client, api_key="test", model="BAAI/bge-m3", dimension=1024)

    vectors = await embedding_client.embed(["逆变器故障"])

    assert len(vectors) == 1
    assert len(vectors[0]) == 1024
    await client.aclose()


@pytest.mark.asyncio
async def test_rerank_client_returns_scores():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "results": [
                    {"index": 1, "relevance_score": 0.9, "document": {"text": "B"}},
                    {"index": 0, "relevance_score": 0.5, "document": {"text": "A"}},
                ]
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://api.siliconflow.cn/v1")
    rerank_client = SiliconFlowRerankClient(client=client, api_key="test", model="BAAI/bge-reranker-v2-m3")

    results = await rerank_client.rerank("query", ["A", "B"], top_n=2)

    assert results[0].index == 1
    assert results[0].score == 0.9
    await client.aclose()
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
$env:PYTHONPATH='D:\桌面\文件\operation_project\backend'
backend\.venv\Scripts\python.exe -m pytest backend\tests\test_siliconflow_client.py -v
```

Expected: FAIL because `app.services.siliconflow` does not exist.

- [ ] **Step 3: Implement clients**

Create `backend/app/services/siliconflow.py`:

```python
from dataclasses import dataclass

import httpx


@dataclass(frozen=True)
class RerankResult:
    index: int
    score: float
    text: str | None


class SiliconFlowEmbeddingClient:
    def __init__(self, client: httpx.AsyncClient, api_key: str, model: str, dimension: int) -> None:
        self.client = client
        self.api_key = api_key
        self.model = model
        self.dimension = dimension

    async def embed(self, texts: list[str]) -> list[list[float]]:
        response = await self.client.post(
            "/embeddings",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={"model": self.model, "input": texts, "encoding_format": "float"},
        )
        response.raise_for_status()
        payload = response.json()
        vectors = [item["embedding"] for item in sorted(payload["data"], key=lambda item: item["index"])]
        for vector in vectors:
            if len(vector) != self.dimension:
                raise ValueError(f"Embedding dimension mismatch: expected {self.dimension}, got {len(vector)}")
        return vectors


class SiliconFlowRerankClient:
    def __init__(self, client: httpx.AsyncClient, api_key: str, model: str) -> None:
        self.client = client
        self.api_key = api_key
        self.model = model

    async def rerank(self, query: str, documents: list[str], top_n: int) -> list[RerankResult]:
        response = await self.client.post(
            "/rerank",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "model": self.model,
                "query": query,
                "documents": documents,
                "top_n": top_n,
                "return_documents": True,
            },
        )
        response.raise_for_status()
        payload = response.json()
        return [
            RerankResult(
                index=item["index"],
                score=float(item["relevance_score"]),
                text=item.get("document", {}).get("text"),
            )
            for item in payload.get("results", [])
        ]
```

- [ ] **Step 4: Run tests**

Run:

```powershell
$env:PYTHONPATH='D:\桌面\文件\operation_project\backend'
backend\.venv\Scripts\python.exe -m pytest backend\tests\test_siliconflow_client.py -v
```

Expected: PASS.

---

### Task 7: Implement Markdown Ingestion Service And Import Script

**Files:**
- Create: `backend/app/services/ingest.py`
- Create: `backend/scripts/import_knowledge_base.py`
- Test: `backend/tests/test_ingest.py`

- [ ] **Step 1: Write ingestion unit test with fake embedding client**

Create `backend/tests/test_ingest.py`:

```python
from pathlib import Path

from app.services.ingest import load_markdown_documents


def test_load_markdown_documents_reads_only_top_level_markdown(tmp_path: Path):
    (tmp_path / "01_逆变器故障与维护.md").write_text("# 逆变器故障与维护\n\n### PV 过压\n\n处理内容", encoding="utf-8")
    (tmp_path / "图片素材表.csv").write_text("name,path", encoding="utf-8")
    (tmp_path / "_中间文档").mkdir()
    (tmp_path / "_中间文档" / "10_培训.md").write_text("# 临时", encoding="utf-8")

    docs = load_markdown_documents(tmp_path)

    assert len(docs) == 1
    assert docs[0].title == "逆变器故障与维护"
    assert docs[0].path.name == "01_逆变器故障与维护.md"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
$env:PYTHONPATH='D:\桌面\文件\operation_project\backend'
backend\.venv\Scripts\python.exe -m pytest backend\tests\test_ingest.py -v
```

Expected: FAIL because `app.services.ingest` does not exist.

- [ ] **Step 3: Implement document loading and ingestion orchestration**

Create `backend/app/services/ingest.py`:

```python
from dataclasses import dataclass
from pathlib import Path
import hashlib
import uuid

from sqlalchemy.orm import Session

from app.models.rag import DocumentStatus, KbDocument, KbDocumentSegment, ParseTask, ParseTaskStatus
from app.services.keyword_index import build_keyword_text
from app.services.markdown_chunker import chunk_markdown
from app.services.siliconflow import SiliconFlowEmbeddingClient


@dataclass(frozen=True)
class MarkdownDocument:
    path: Path
    title: str
    content: str
    file_sha256: str


def _title_from_path(path: Path) -> str:
    stem = path.stem
    return stem.split("_", 1)[1] if "_" in stem else stem


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_markdown_documents(directory: Path) -> list[MarkdownDocument]:
    documents: list[MarkdownDocument] = []
    for path in sorted(directory.glob("*.md")):
        data = path.read_bytes()
        documents.append(
            MarkdownDocument(
                path=path,
                title=_title_from_path(path),
                content=data.decode("utf-8"),
                file_sha256=_sha256_bytes(data),
            )
        )
    return documents


async def import_markdown_document(
    session: Session,
    document: MarkdownDocument,
    embedding_client: SiliconFlowEmbeddingClient,
    embedding_model: str,
) -> uuid.UUID:
    existing = session.query(KbDocument).filter(KbDocument.file_sha256 == document.file_sha256).one_or_none()
    if existing is not None:
        return existing.id

    db_document = KbDocument(
        title=document.title,
        source_path=str(document.path),
        file_sha256=document.file_sha256,
        file_type="markdown",
        status=DocumentStatus.processing,
        enabled=True,
        document_metadata={},
    )
    session.add(db_document)
    session.flush()

    task = ParseTask(document_id=db_document.id, status=ParseTaskStatus.running, retry_count=0)
    session.add(task)
    session.flush()

    chunks = chunk_markdown(document.content, source_title=document.title)
    vectors = await embedding_client.embed([chunk.indexed_text for chunk in chunks])

    for index, (chunk, vector) in enumerate(zip(chunks, vectors, strict=True)):
        session.add(
            KbDocumentSegment(
                document_id=db_document.id,
                chunk_index=index,
                heading_path=chunk.heading_path,
                section_title=chunk.section_title,
                raw_text=chunk.raw_text,
                clean_text=chunk.clean_text,
                indexed_text=chunk.indexed_text,
                keyword_text=build_keyword_text(chunk.indexed_text),
                token_count=None,
                char_count=chunk.char_count,
                embedding_model=embedding_model,
                embedding=vector,
                segment_metadata=chunk.metadata,
            )
        )

    db_document.status = DocumentStatus.ready
    task.status = ParseTaskStatus.success
    session.commit()
    return db_document.id
```

- [ ] **Step 4: Create import CLI**

Create `backend/scripts/import_knowledge_base.py`:

```python
import asyncio
from pathlib import Path
import sys

import httpx

ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = ROOT.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import settings
from app.db.session import SessionLocal
from app.services.ingest import import_markdown_document, load_markdown_documents
from app.services.siliconflow import SiliconFlowEmbeddingClient


async def main() -> None:
    source_dir = PROJECT_ROOT / "data/knowledge_base/markdown"
    documents = load_markdown_documents(source_dir)
    async with httpx.AsyncClient(base_url=settings.embedding_base_url, timeout=60) as http_client:
        embedding_client = SiliconFlowEmbeddingClient(
            client=http_client,
            api_key=settings.embedding_api_key,
            model=settings.embedding_model,
            dimension=settings.embedding_dimension,
        )
        with SessionLocal() as session:
            for document in documents:
                document_id = await import_markdown_document(
                    session=session,
                    document=document,
                    embedding_client=embedding_client,
                    embedding_model=settings.embedding_model,
                )
                print(f"imported {document.path.name} -> {document_id}")


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 5: Run ingestion tests**

Run:

```powershell
$env:PYTHONPATH='D:\桌面\文件\operation_project\backend'
backend\.venv\Scripts\python.exe -m pytest backend\tests\test_ingest.py -v
```

Expected: PASS.

- [ ] **Step 6: Run import script**

Run:

```powershell
cd D:\桌面\文件\operation_project
backend\.venv\Scripts\python.exe backend\scripts\import_knowledge_base.py
```

Expected: prints one `imported ... -> <uuid>` line for each top-level Markdown document in `data/knowledge_base/markdown`.

---

### Task 8: Implement RRF Fusion

**Files:**
- Create or modify: `backend/app/services/retrieval.py`
- Test: `backend/tests/test_rrf.py`

- [ ] **Step 1: Write RRF tests**

Create `backend/tests/test_rrf.py`:

```python
from app.services.retrieval import RankedCandidate, reciprocal_rank_fusion


def test_rrf_combines_vector_and_keyword_rankings():
    vector = [
        RankedCandidate(segment_id="A", rank=1, score=0.9, source="vector"),
        RankedCandidate(segment_id="B", rank=2, score=0.8, source="vector"),
    ]
    keyword = [
        RankedCandidate(segment_id="B", rank=1, score=12.0, source="keyword"),
        RankedCandidate(segment_id="C", rank=2, score=6.0, source="keyword"),
    ]

    fused = reciprocal_rank_fusion(vector, keyword, k=60, limit=3)

    assert [item.segment_id for item in fused] == ["B", "A", "C"]
    assert fused[0].rrf_score > fused[1].rrf_score
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
$env:PYTHONPATH='D:\桌面\文件\operation_project\backend'
backend\.venv\Scripts\python.exe -m pytest backend\tests\test_rrf.py -v
```

Expected: FAIL because `app.services.retrieval` does not exist or RRF functions are missing.

- [ ] **Step 3: Implement RRF data structures and function**

Create or update `backend/app/services/retrieval.py`:

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class RankedCandidate:
    segment_id: str
    rank: int
    score: float
    source: str


@dataclass(frozen=True)
class FusedCandidate:
    segment_id: str
    rrf_score: float
    vector_score: float | None
    keyword_score: float | None


def reciprocal_rank_fusion(
    vector_results: list[RankedCandidate],
    keyword_results: list[RankedCandidate],
    k: int,
    limit: int,
) -> list[FusedCandidate]:
    scores: dict[str, float] = {}
    vector_scores: dict[str, float] = {}
    keyword_scores: dict[str, float] = {}

    for result in vector_results:
        scores[result.segment_id] = scores.get(result.segment_id, 0.0) + 1.0 / (k + result.rank)
        vector_scores[result.segment_id] = result.score

    for result in keyword_results:
        scores[result.segment_id] = scores.get(result.segment_id, 0.0) + 1.0 / (k + result.rank)
        keyword_scores[result.segment_id] = result.score

    fused = [
        FusedCandidate(
            segment_id=segment_id,
            rrf_score=score,
            vector_score=vector_scores.get(segment_id),
            keyword_score=keyword_scores.get(segment_id),
        )
        for segment_id, score in scores.items()
    ]
    return sorted(fused, key=lambda item: item.rrf_score, reverse=True)[:limit]
```

- [ ] **Step 4: Run RRF tests**

Run:

```powershell
$env:PYTHONPATH='D:\桌面\文件\operation_project\backend'
backend\.venv\Scripts\python.exe -m pytest backend\tests\test_rrf.py -v
```

Expected: PASS.

---

### Task 9: Implement Vector Search, Keyword Search, And Rerank Orchestration

**Files:**
- Modify: `backend/app/services/retrieval.py`
- Create: `backend/scripts/query_knowledge_base.py`
- Test: `backend/tests/test_retrieval_sql.py`

- [ ] **Step 1: Write retrieval SQL shape test**

Create `backend/tests/test_retrieval_sql.py`:

```python
from app.services.retrieval import build_keyword_search_sql, build_vector_search_sql


def test_vector_search_sql_uses_cosine_distance():
    sql = build_vector_search_sql(limit=20)

    assert "embedding <=> :query_embedding" in sql
    assert "LIMIT :limit" in sql


def test_keyword_search_sql_uses_keyword_text():
    sql = build_keyword_search_sql(limit=20)

    assert "keyword_text" in sql
    assert "websearch_to_tsquery" in sql
    assert "LIMIT :limit" in sql
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
$env:PYTHONPATH='D:\桌面\文件\operation_project\backend'
backend\.venv\Scripts\python.exe -m pytest backend\tests\test_retrieval_sql.py -v
```

Expected: FAIL because SQL builder functions are missing.

- [ ] **Step 3: Add SQL builders and evidence result structure**

Append to `backend/app/services/retrieval.py`:

```python
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.rag import KbDocumentSegment
from app.services.keyword_index import normalize_query
from app.services.siliconflow import SiliconFlowEmbeddingClient, SiliconFlowRerankClient


@dataclass(frozen=True)
class EvidenceChunk:
    segment_id: str
    document_id: str
    heading_path: str
    indexed_text: str
    clean_text: str
    vector_score: float | None
    keyword_score: float | None
    rrf_score: float
    rerank_score: float | None


def build_vector_search_sql(limit: int) -> str:
    return """
    SELECT id::text AS segment_id,
           (1 - (embedding <=> :query_embedding)) AS score,
           row_number() OVER (ORDER BY embedding <=> :query_embedding) AS rank
    FROM kb_document_segment
    ORDER BY embedding <=> :query_embedding
    LIMIT :limit
    """


def build_keyword_search_sql(limit: int) -> str:
    return """
    SELECT id::text AS segment_id,
           ts_rank_cd(to_tsvector('simple', keyword_text), websearch_to_tsquery('simple', :query_text)) AS score,
           row_number() OVER (
               ORDER BY ts_rank_cd(to_tsvector('simple', keyword_text), websearch_to_tsquery('simple', :query_text)) DESC
           ) AS rank
    FROM kb_document_segment
    WHERE to_tsvector('simple', keyword_text) @@ websearch_to_tsquery('simple', :query_text)
       OR keyword_text ILIKE :like_query
    ORDER BY score DESC
    LIMIT :limit
    """


def _rows_to_ranked(rows, source: str) -> list[RankedCandidate]:
    return [
        RankedCandidate(
            segment_id=row.segment_id,
            rank=int(row.rank),
            score=float(row.score or 0.0),
            source=source,
        )
        for row in rows
    ]


async def retrieve_evidence(
    session: Session,
    query: str,
    embedding_client: SiliconFlowEmbeddingClient,
    rerank_client: SiliconFlowRerankClient | None,
    vector_top_k: int,
    keyword_top_k: int,
    rrf_top_k: int,
    final_top_k: int,
    rrf_k: int,
) -> list[EvidenceChunk]:
    normalized_query = normalize_query(query)
    query_embedding = (await embedding_client.embed([normalized_query]))[0]

    vector_rows = session.execute(
        text(build_vector_search_sql(vector_top_k)),
        {"query_embedding": query_embedding, "limit": vector_top_k},
    ).all()
    keyword_rows = session.execute(
        text(build_keyword_search_sql(keyword_top_k)),
        {"query_text": normalized_query, "like_query": f"%{normalized_query}%", "limit": keyword_top_k},
    ).all()

    fused = reciprocal_rank_fusion(
        _rows_to_ranked(vector_rows, "vector"),
        _rows_to_ranked(keyword_rows, "keyword"),
        k=rrf_k,
        limit=rrf_top_k,
    )
    if not fused:
        return []

    segment_ids = [item.segment_id for item in fused]
    segments = session.query(KbDocumentSegment).filter(KbDocumentSegment.id.in_(segment_ids)).all()
    segment_by_id = {str(segment.id): segment for segment in segments}
    fused_by_id = {item.segment_id: item for item in fused}
    ordered_segments = [segment_by_id[segment_id] for segment_id in segment_ids if segment_id in segment_by_id]

    rerank_scores: dict[str, float] = {}
    final_segment_ids = segment_ids[:final_top_k]
    if rerank_client is not None:
        rerank_results = await rerank_client.rerank(
            normalized_query,
            [segment.indexed_text for segment in ordered_segments],
            top_n=final_top_k,
        )
        final_segment_ids = []
        for result in rerank_results:
            segment = ordered_segments[result.index]
            segment_id = str(segment.id)
            rerank_scores[segment_id] = result.score
            final_segment_ids.append(segment_id)

    evidence: list[EvidenceChunk] = []
    for segment_id in final_segment_ids[:final_top_k]:
        segment = segment_by_id[segment_id]
        fused_item = fused_by_id[segment_id]
        evidence.append(
            EvidenceChunk(
                segment_id=segment_id,
                document_id=str(segment.document_id),
                heading_path=segment.heading_path,
                indexed_text=segment.indexed_text,
                clean_text=segment.clean_text,
                vector_score=fused_item.vector_score,
                keyword_score=fused_item.keyword_score,
                rrf_score=fused_item.rrf_score,
                rerank_score=rerank_scores.get(segment_id),
            )
        )
    return evidence
```

- [ ] **Step 4: Create query CLI**

Create `backend/scripts/query_knowledge_base.py`:

```python
import asyncio
from pathlib import Path
import sys

import httpx

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import settings
from app.db.session import SessionLocal
from app.services.retrieval import retrieve_evidence
from app.services.siliconflow import SiliconFlowEmbeddingClient, SiliconFlowRerankClient


async def main() -> None:
    query = " ".join(sys.argv[1:]).strip()
    if not query:
        raise SystemExit("Usage: python backend/scripts/query_knowledge_base.py <question>")

    async with httpx.AsyncClient(base_url=settings.embedding_base_url, timeout=60) as embedding_http, httpx.AsyncClient(base_url=settings.rerank_base_url, timeout=60) as rerank_http:
        embedding_client = SiliconFlowEmbeddingClient(
            client=embedding_http,
            api_key=settings.embedding_api_key,
            model=settings.embedding_model,
            dimension=settings.embedding_dimension,
        )
        rerank_client = SiliconFlowRerankClient(
            client=rerank_http,
            api_key=settings.rerank_api_key,
            model=settings.rerank_model,
        ) if settings.rerank_enabled else None

        with SessionLocal() as session:
            evidence = await retrieve_evidence(
                session=session,
                query=query,
                embedding_client=embedding_client,
                rerank_client=rerank_client,
                vector_top_k=settings.retrieval_vector_top_k,
                keyword_top_k=settings.retrieval_keyword_top_k,
                rrf_top_k=settings.retrieval_rrf_top_k,
                final_top_k=settings.retrieval_final_top_k,
                rrf_k=settings.retrieval_rrf_k,
            )

    for index, item in enumerate(evidence, start=1):
        print(f"[{index}] {item.heading_path}")
        print(f"segment_id={item.segment_id}")
        print(f"vector_score={item.vector_score} keyword_score={item.keyword_score} rrf_score={item.rrf_score} rerank_score={item.rerank_score}")
        print(item.clean_text[:300].replace('\\n', ' '))
        print()


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 5: Run retrieval tests**

Run:

```powershell
$env:PYTHONPATH='D:\桌面\文件\operation_project\backend'
backend\.venv\Scripts\python.exe -m pytest backend\tests\test_retrieval_sql.py backend\tests\test_rrf.py -v
```

Expected: PASS.

---

### Task 10: Run End-To-End Minimum Verification

**Files:**
- No new files.
- Uses existing scripts from Tasks 7 and 9.

- [ ] **Step 1: Install development dependencies if pytest is missing**

Run:

```powershell
backend\.venv\Scripts\python.exe -m pip install -r backend\requirements-dev.txt
```

Expected: `pytest` is installed in `backend\.venv`.

- [ ] **Step 2: Run all backend unit tests**

Run:

```powershell
$env:PYTHONPATH='D:\桌面\文件\operation_project\backend'
backend\.venv\Scripts\python.exe -m pytest backend\tests -v
```

Expected: all tests PASS.

- [ ] **Step 3: Apply database migration**

Run:

```powershell
cd D:\桌面\文件\operation_project\backend
.\.venv\Scripts\python.exe -m alembic upgrade head
```

Expected: migration finishes without error.

- [ ] **Step 4: Import knowledge base**

Run:

```powershell
cd D:\桌面\文件\operation_project
backend\.venv\Scripts\python.exe backend\scripts\import_knowledge_base.py
```

Expected: the script prints imported document IDs for the 9 Markdown documents.

- [ ] **Step 5: Verify segment count**

Run:

```powershell
$env:PGPASSWORD='<local database password from .env>'
D:\PostgreSQL\16\bin\psql.exe -h 127.0.0.1 -U postgres -d operation_pv -c "SELECT COUNT(*) AS documents FROM kb_document; SELECT COUNT(*) AS segments FROM kb_document_segment;"
```

Expected: `documents` is 9 and `segments` is greater than 9.

- [ ] **Step 6: Query evidence for inverter fault**

Run:

```powershell
cd D:\桌面\文件\operation_project
backend\.venv\Scripts\python.exe backend\scripts\query_knowledge_base.py "逆变器绝缘阻抗低怎么排查？"
```

Expected: prints up to 5 evidence chunks. At least one heading path should relate to inverter faults, insulation, DC cable, grounding, or component-side inspection.

- [ ] **Step 7: Query evidence for SVG fault**

Run:

```powershell
cd D:\桌面\文件\operation_project
backend\.venv\Scripts\python.exe backend\scripts\query_knowledge_base.py "SVG 无功补偿异常怎么处理？"
```

Expected: prints up to 5 evidence chunks. At least one heading path should relate to SVG or reactive power equipment.

- [ ] **Step 8: Query evidence for out-of-domain question**

Run:

```powershell
cd D:\桌面\文件\operation_project
backend\.venv\Scripts\python.exe backend\scripts\query_knowledge_base.py "今天上海天气怎么样？"
```

Expected: evidence is empty or weak. Record this as input for later refusal-threshold work; do not implement refusal logic in this plan.

---

### Task 11: Record Verification Notes

**Files:**
- Create: `docs/rag-minimum-loop-verification.md`

- [ ] **Step 1: Create verification note**

Create `docs/rag-minimum-loop-verification.md`:

```markdown
# RAG Minimum Loop Verification

## Environment

- Database: local Windows PostgreSQL 16
- Vector extension: pgvector
- Embedding model: BAAI/bge-m3
- Embedding dimension: 1024
- Rerank model: BAAI/bge-reranker-v2-m3

## Commands Run

```powershell
backend\.venv\Scripts\python.exe -m pytest backend\tests -v
cd backend
.\.venv\Scripts\python.exe -m alembic upgrade head
cd ..
backend\.venv\Scripts\python.exe backend\scripts\import_knowledge_base.py
backend\.venv\Scripts\python.exe backend\scripts\query_knowledge_base.py "逆变器绝缘阻抗低怎么排查？"
backend\.venv\Scripts\python.exe backend\scripts\query_knowledge_base.py "SVG 无功补偿异常怎么处理？"
```

## Results

- Documents imported:
- Segments created:
- Inverter query Top 5:
- SVG query Top 5:
- Out-of-domain query behavior:

## Follow-Up Work

- Add QA answer generation endpoint.
- Add citation persistence into `qa_reference`.
- Add refusal threshold and unanswered question recording.
- Build golden QA evaluation set.
```

- [ ] **Step 2: Fill in measured results**

Replace the empty bullets with the actual counts and evidence headings from Task 10.

- [ ] **Step 3: Confirm the plan scope is complete**

Check that the minimum loop covers:

- Database tables.
- Markdown heading-aware chunking.
- Embedding into pgvector.
- PostgreSQL keyword retrieval.
- RRF fusion.
- Reranker refinement.
- Top 5 evidence output.
- Tests and verification commands.

Expected: every item is covered by a completed task.

---

## Self-Review

**Spec coverage:** The plan covers all requested items: RAG core database tables, SQLAlchemy models, Alembic migration, Markdown heading-tree chunking, import script, embedding provider, vector retrieval, keyword retrieval, RRF, reranker, Top 5 evidence output, and minimum tests.

**Scope exclusions honored:** The plan does not implement frontend pages, full QA API, multi-turn sessions, permission system, complex OCR, or Docker deployment.

**Type consistency:** The plan uses `KbDocument`, `ParseTask`, `KbDocumentSegment`, `SiliconFlowEmbeddingClient`, `SiliconFlowRerankClient`, `MarkdownChunk`, `RankedCandidate`, `FusedCandidate`, and `EvidenceChunk` consistently across tasks.

**Security note:** `.env` must remain local. `.env.example` must contain placeholder API keys only.
