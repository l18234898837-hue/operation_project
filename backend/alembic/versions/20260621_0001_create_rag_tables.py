"""create rag tables

Revision ID: 20260621_0001
Revises:
Create Date: 2026-06-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql


revision: str = "20260621_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


document_status = postgresql.ENUM(
    "uploaded",
    "processing",
    "ready",
    "failed",
    "disabled",
    name="document_status",
    create_type=False,
)
parse_task_status = postgresql.ENUM(
    "pending",
    "running",
    "success",
    "failed",
    name="parse_task_status",
    create_type=False,
)
answer_type = postgresql.ENUM(
    "faq",
    "rag",
    "fallback",
    "none",
    name="answer_type",
    create_type=False,
)
unanswered_status = postgresql.ENUM(
    "new",
    "reviewed",
    "resolved",
    name="unanswered_status",
    create_type=False,
)


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    bind = op.get_bind()
    document_status.create(bind, checkfirst=True)
    parse_task_status.create(bind, checkfirst=True)
    answer_type.create(bind, checkfirst=True)
    unanswered_status.create(bind, checkfirst=True)

    op.create_table(
        "kb_document",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("source_path", sa.Text(), nullable=True),
        sa.Column("file_name", sa.String(length=512), nullable=True),
        sa.Column("file_type", sa.String(length=255), nullable=True),
        sa.Column("file_sha256", sa.String(length=64), nullable=True),
        sa.Column(
            "status",
            document_status,
            nullable=False,
            server_default="uploaded",
        ),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("segment_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("document_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_kb_document_enabled", "kb_document", ["enabled"])
    op.create_index("ix_kb_document_file_sha256", "kb_document", ["file_sha256"], unique=True)
    op.create_index("ix_kb_document_status", "kb_document", ["status"])

    op.create_table(
        "parse_task",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "status",
            parse_task_status,
            nullable=False,
            server_default="pending",
        ),
        sa.Column("parser_name", sa.String(length=255), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("task_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["kb_document.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_parse_task_document_id", "parse_task", ["document_id"])
    op.create_index("ix_parse_task_status", "parse_task", ["status"])

    op.create_table(
        "kb_document_segment",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("heading_path", sa.Text(), nullable=True),
        sa.Column("section_title", sa.Text(), nullable=True),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("clean_text", sa.Text(), nullable=False),
        sa.Column("indexed_text", sa.Text(), nullable=False),
        sa.Column("keyword_text", sa.Text(), nullable=True),
        sa.Column("token_count", sa.Integer(), nullable=True),
        sa.Column("char_count", sa.Integer(), nullable=False),
        sa.Column("embedding_model", sa.String(length=255), nullable=True),
        sa.Column("embedding", Vector(1024), nullable=True),
        sa.Column("segment_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["kb_document.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "document_id",
            "chunk_index",
            name="uq_kb_document_segment_document_chunk_index",
        ),
    )
    op.create_index("ix_kb_document_segment_document_id", "kb_document_segment", ["document_id"])
    op.create_index(
        "ix_kb_document_segment_embedding_model",
        "kb_document_segment",
        ["embedding_model"],
    )
    op.execute(
        "CREATE INDEX ix_kb_document_segment_embedding_hnsw "
        "ON kb_document_segment USING hnsw (embedding vector_cosine_ops)"
    )
    op.execute(
        "CREATE INDEX ix_kb_document_segment_indexed_text_trgm "
        "ON kb_document_segment USING gin (indexed_text gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX ix_kb_document_segment_keyword_text_trgm "
        "ON kb_document_segment USING gin (keyword_text gin_trgm_ops)"
    )

    op.create_table(
        "faq_item",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_document_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("normalized_question", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("keyword_text", sa.Text(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("faq_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["source_document_id"], ["kb_document.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_faq_item_source_document_id", "faq_item", ["source_document_id"])
    op.create_index("ix_faq_item_enabled", "faq_item", ["enabled"])
    op.execute(
        "CREATE INDEX ix_faq_item_keyword_text_trgm "
        "ON faq_item USING gin (keyword_text gin_trgm_ops)"
    )

    op.create_table(
        "qa_session",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.String(length=255), nullable=True),
        sa.Column("title", sa.String(length=512), nullable=True),
        sa.Column("session_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_qa_session_user_id", "qa_session", ["user_id"])

    op.create_table(
        "qa_record",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("trace_id", sa.String(length=128), nullable=True),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("normalized_question", sa.Text(), nullable=True),
        sa.Column("answer", sa.Text(), nullable=True),
        sa.Column(
            "answer_type",
            answer_type,
            nullable=False,
            server_default="none",
        ),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("model_name", sa.String(length=255), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("decision_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["qa_session.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_qa_record_answer_type", "qa_record", ["answer_type"])
    op.create_index("ix_qa_record_session_id", "qa_record", ["session_id"])
    op.create_index("ix_qa_record_trace_id", "qa_record", ["trace_id"], unique=True)

    op.create_table(
        "qa_reference",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("qa_record_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("segment_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("faq_item_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("rank", sa.Integer(), nullable=True),
        sa.Column("relevance_score", sa.Float(), nullable=True),
        sa.Column("vector_score", sa.Float(), nullable=True),
        sa.Column("keyword_score", sa.Float(), nullable=True),
        sa.Column("rrf_score", sa.Float(), nullable=True),
        sa.Column("excerpt", sa.Text(), nullable=True),
        sa.Column("ref_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["kb_document.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["faq_item_id"], ["faq_item.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["qa_record_id"], ["qa_record.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["segment_id"], ["kb_document_segment.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_qa_reference_faq_item_id", "qa_reference", ["faq_item_id"])
    op.create_index("ix_qa_reference_qa_record_id", "qa_reference", ["qa_record_id"])
    op.create_index("ix_qa_reference_segment_id", "qa_reference", ["segment_id"])

    op.create_table(
        "qa_unanswered",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("record_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("normalized_question", sa.Text(), nullable=True),
        sa.Column(
            "status",
            unanswered_status,
            nullable=False,
            server_default="new",
        ),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("resolved_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["record_id"], ["qa_record.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["session_id"], ["qa_session.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("record_id", name="uq_qa_unanswered_record_id"),
    )
    op.create_index("ix_qa_unanswered_record_id", "qa_unanswered", ["record_id"])
    op.create_index("ix_qa_unanswered_session_id", "qa_unanswered", ["session_id"])
    op.create_index("ix_qa_unanswered_status", "qa_unanswered", ["status"])


def downgrade() -> None:
    op.drop_index("ix_qa_unanswered_status", table_name="qa_unanswered")
    op.drop_index("ix_qa_unanswered_session_id", table_name="qa_unanswered")
    op.drop_index("ix_qa_unanswered_record_id", table_name="qa_unanswered")
    op.drop_table("qa_unanswered")

    op.drop_index("ix_qa_reference_segment_id", table_name="qa_reference")
    op.drop_index("ix_qa_reference_qa_record_id", table_name="qa_reference")
    op.drop_index("ix_qa_reference_faq_item_id", table_name="qa_reference")
    op.drop_table("qa_reference")

    op.drop_index("ix_qa_record_trace_id", table_name="qa_record")
    op.drop_index("ix_qa_record_session_id", table_name="qa_record")
    op.drop_index("ix_qa_record_answer_type", table_name="qa_record")
    op.drop_table("qa_record")

    op.drop_index("ix_qa_session_user_id", table_name="qa_session")
    op.drop_table("qa_session")

    op.execute("DROP INDEX IF EXISTS ix_faq_item_keyword_text_trgm")
    op.drop_index("ix_faq_item_enabled", table_name="faq_item")
    op.drop_index("ix_faq_item_source_document_id", table_name="faq_item")
    op.drop_table("faq_item")

    op.execute("DROP INDEX IF EXISTS ix_kb_document_segment_keyword_text_trgm")
    op.execute("DROP INDEX IF EXISTS ix_kb_document_segment_indexed_text_trgm")
    op.execute("DROP INDEX IF EXISTS ix_kb_document_segment_embedding_hnsw")
    op.drop_index("ix_kb_document_segment_embedding_model", table_name="kb_document_segment")
    op.drop_index("ix_kb_document_segment_document_id", table_name="kb_document_segment")
    op.drop_table("kb_document_segment")

    op.drop_index("ix_parse_task_status", table_name="parse_task")
    op.drop_index("ix_parse_task_document_id", table_name="parse_task")
    op.drop_table("parse_task")

    op.drop_index("ix_kb_document_status", table_name="kb_document")
    op.drop_index("ix_kb_document_file_sha256", table_name="kb_document")
    op.drop_index("ix_kb_document_enabled", table_name="kb_document")
    op.drop_table("kb_document")

    bind = op.get_bind()
    unanswered_status.drop(bind, checkfirst=True)
    answer_type.drop(bind, checkfirst=True)
    parse_task_status.drop(bind, checkfirst=True)
    document_status.drop(bind, checkfirst=True)
