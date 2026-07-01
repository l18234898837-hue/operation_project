"""add document markdown path

Revision ID: 20260701_0004
Revises: 20260624_0003
Create Date: 2026-07-01 00:04:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260701_0004"
down_revision: str | None = "20260624_0003"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("kb_document", sa.Column("markdown_path", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("kb_document", "markdown_path")
