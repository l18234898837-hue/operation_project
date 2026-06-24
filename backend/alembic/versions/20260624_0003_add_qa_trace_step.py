"""add qa trace step

Revision ID: 20260624_0003
Revises: 20260622_0002
Create Date: 2026-06-24 00:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260624_0003"
down_revision: Union[str, None] = "20260622_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "qa_trace_step",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "qa_record_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("qa_record.id", ondelete="CASCADE"),
        ),
        sa.Column("trace_id", sa.String(length=128), nullable=False),
        sa.Column("step_name", sa.String(length=128), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=64),
            nullable=False,
            server_default="success",
        ),
        sa.Column("model_name", sa.String(length=255)),
        sa.Column("input_tokens", sa.Integer()),
        sa.Column("output_tokens", sa.Integer()),
        sa.Column("error_message", sa.Text()),
        sa.Column("metadata", postgresql.JSONB()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_qa_trace_step_qa_record_id", "qa_trace_step", ["qa_record_id"])
    op.create_index("ix_qa_trace_step_trace_id", "qa_trace_step", ["trace_id"])
    op.create_index("ix_qa_trace_step_step_name", "qa_trace_step", ["step_name"])
    op.create_index("ix_qa_trace_step_status", "qa_trace_step", ["status"])


def downgrade() -> None:
    op.drop_index("ix_qa_trace_step_status", table_name="qa_trace_step")
    op.drop_index("ix_qa_trace_step_step_name", table_name="qa_trace_step")
    op.drop_index("ix_qa_trace_step_trace_id", table_name="qa_trace_step")
    op.drop_index("ix_qa_trace_step_qa_record_id", table_name="qa_trace_step")
    op.drop_table("qa_trace_step")
