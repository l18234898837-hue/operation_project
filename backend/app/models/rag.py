from __future__ import annotations

import enum
import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    true,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def _enum_values(enum_class: type[enum.Enum]) -> list[str]:
    return [item.value for item in enum_class]


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


document_status_enum = Enum(
    DocumentStatus,
    name="document_status",
    values_callable=_enum_values,
)
parse_task_status_enum = Enum(
    ParseTaskStatus,
    name="parse_task_status",
    values_callable=_enum_values,
)
answer_type_enum = Enum(
    AnswerType,
    name="answer_type",
    values_callable=_enum_values,
)
unanswered_status_enum = Enum(
    UnansweredStatus,
    name="unanswered_status",
    values_callable=_enum_values,
)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class KbDocument(TimestampMixin, Base):
    __tablename__ = "kb_document"
    __table_args__ = (
        Index("ix_kb_document_status", "status"),
        Index("ix_kb_document_file_sha256", "file_sha256", unique=True),
        Index("ix_kb_document_enabled", "enabled"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    source_path: Mapped[str | None] = mapped_column(Text)
    file_name: Mapped[str | None] = mapped_column(String(512))
    file_type: Mapped[str | None] = mapped_column(String(255))
    file_sha256: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[DocumentStatus] = mapped_column(
        document_status_enum,
        nullable=False,
        default=DocumentStatus.uploaded,
        server_default=DocumentStatus.uploaded.value,
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=true(),
    )
    segment_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    error_message: Mapped[str | None] = mapped_column(Text)
    document_metadata: Mapped[dict | None] = mapped_column(JSONB)

    parse_tasks: Mapped[list[ParseTask]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
    )
    segments: Mapped[list[KbDocumentSegment]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
    )


class ParseTask(TimestampMixin, Base):
    __tablename__ = "parse_task"
    __table_args__ = (
        Index("ix_parse_task_document_id", "document_id"),
        Index("ix_parse_task_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("kb_document.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[ParseTaskStatus] = mapped_column(
        parse_task_status_enum,
        nullable=False,
        default=ParseTaskStatus.pending,
        server_default=ParseTaskStatus.pending.value,
    )
    parser_name: Mapped[str | None] = mapped_column(String(255))
    retry_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    task_metadata: Mapped[dict | None] = mapped_column(JSONB)

    document: Mapped[KbDocument] = relationship(back_populates="parse_tasks")


class KbDocumentSegment(TimestampMixin, Base):
    __tablename__ = "kb_document_segment"
    __table_args__ = (
        UniqueConstraint(
            "document_id",
            "chunk_index",
            name="uq_kb_document_segment_document_chunk_index",
        ),
        Index("ix_kb_document_segment_document_id", "document_id"),
        Index("ix_kb_document_segment_embedding_model", "embedding_model"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("kb_document.id", ondelete="CASCADE"),
        nullable=False,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    heading_path: Mapped[str | None] = mapped_column(Text)
    section_title: Mapped[str | None] = mapped_column(Text)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    clean_text: Mapped[str] = mapped_column(Text, nullable=False)
    indexed_text: Mapped[str] = mapped_column(Text, nullable=False)
    keyword_text: Mapped[str | None] = mapped_column(Text)
    token_count: Mapped[int | None] = mapped_column(Integer)
    char_count: Mapped[int] = mapped_column(Integer, nullable=False)
    embedding_model: Mapped[str | None] = mapped_column(String(255))
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1024))
    segment_metadata: Mapped[dict | None] = mapped_column(JSONB)

    document: Mapped[KbDocument] = relationship(back_populates="segments")
    references: Mapped[list[QaReference]] = relationship(back_populates="segment")


class FaqItem(TimestampMixin, Base):
    __tablename__ = "faq_item"
    __table_args__ = (
        Index("ix_faq_item_enabled", "enabled"),
        Index("ix_faq_item_source_document_id", "source_document_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    source_document_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("kb_document.id", ondelete="SET NULL"),
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    keyword_text: Mapped[str | None] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=true(),
    )
    faq_metadata: Mapped[dict | None] = mapped_column(JSONB)

    document: Mapped[KbDocument | None] = relationship()
    references: Mapped[list[QaReference]] = relationship(back_populates="faq_item")


class QaSession(TimestampMixin, Base):
    __tablename__ = "qa_session"
    __table_args__ = (Index("ix_qa_session_user_id", "user_id"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[str | None] = mapped_column(String(255))
    title: Mapped[str | None] = mapped_column(String(512))
    session_metadata: Mapped[dict | None] = mapped_column(JSONB)

    records: Mapped[list[QaRecord]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
    )
    unanswered_items: Mapped[list[QaUnanswered]] = relationship(
        back_populates="session",
    )


class QaRecord(TimestampMixin, Base):
    __tablename__ = "qa_record"
    __table_args__ = (
        Index("ix_qa_record_session_id", "session_id"),
        Index("ix_qa_record_answer_type", "answer_type"),
        Index("ix_qa_record_trace_id", "trace_id", unique=True),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("qa_session.id", ondelete="CASCADE"),
        nullable=False,
    )
    trace_id: Mapped[str | None] = mapped_column(String(128))
    question: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_question: Mapped[str | None] = mapped_column(Text)
    answer: Mapped[str | None] = mapped_column(Text)
    answer_type: Mapped[AnswerType] = mapped_column(
        answer_type_enum,
        nullable=False,
        default=AnswerType.none,
        server_default=AnswerType.none.value,
    )
    confidence: Mapped[float | None] = mapped_column(Float)
    model_name: Mapped[str | None] = mapped_column(String(255))
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    decision_metadata: Mapped[dict | None] = mapped_column(JSONB)

    session: Mapped[QaSession] = relationship(back_populates="records")
    references: Mapped[list[QaReference]] = relationship(
        back_populates="record",
        cascade="all, delete-orphan",
    )
    unanswered_item: Mapped[QaUnanswered | None] = relationship(
        back_populates="record",
    )


class QaReference(TimestampMixin, Base):
    __tablename__ = "qa_reference"
    __table_args__ = (
        Index("ix_qa_reference_qa_record_id", "qa_record_id"),
        Index("ix_qa_reference_segment_id", "segment_id"),
        Index("ix_qa_reference_faq_item_id", "faq_item_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    qa_record_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("qa_record.id", ondelete="CASCADE"),
        nullable=False,
    )
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("kb_document.id", ondelete="SET NULL"),
    )
    segment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("kb_document_segment.id", ondelete="SET NULL"),
    )
    faq_item_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("faq_item.id", ondelete="SET NULL"),
    )
    rank: Mapped[int | None] = mapped_column(Integer)
    relevance_score: Mapped[float | None] = mapped_column(Float)
    vector_score: Mapped[float | None] = mapped_column(Float)
    keyword_score: Mapped[float | None] = mapped_column(Float)
    rrf_score: Mapped[float | None] = mapped_column(Float)
    excerpt: Mapped[str | None] = mapped_column(Text)
    ref_metadata: Mapped[dict | None] = mapped_column(JSONB)

    record: Mapped[QaRecord] = relationship(back_populates="references")
    document: Mapped[KbDocument | None] = relationship()
    segment: Mapped[KbDocumentSegment | None] = relationship(back_populates="references")
    faq_item: Mapped[FaqItem | None] = relationship(back_populates="references")


class QaUnanswered(TimestampMixin, Base):
    __tablename__ = "qa_unanswered"
    __table_args__ = (
        Index("ix_qa_unanswered_status", "status"),
        Index("ix_qa_unanswered_session_id", "session_id"),
        Index("ix_qa_unanswered_record_id", "record_id"),
        UniqueConstraint("record_id", name="uq_qa_unanswered_record_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("qa_session.id", ondelete="SET NULL"),
    )
    record_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("qa_record.id", ondelete="SET NULL"),
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_question: Mapped[str | None] = mapped_column(Text)
    status: Mapped[UnansweredStatus] = mapped_column(
        unanswered_status_enum,
        nullable=False,
        default=UnansweredStatus.new,
        server_default=UnansweredStatus.new.value,
    )
    reason: Mapped[str | None] = mapped_column(Text)
    resolved_note: Mapped[str | None] = mapped_column(Text)

    session: Mapped[QaSession | None] = relationship(back_populates="unanswered_items")
    record: Mapped[QaRecord | None] = relationship(back_populates="unanswered_item")
