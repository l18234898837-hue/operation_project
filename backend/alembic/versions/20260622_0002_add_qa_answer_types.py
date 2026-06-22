"""add qa answer types

Revision ID: 20260622_0002
Revises: 20260621_0001
Create Date: 2026-06-22 00:00:00
"""

from typing import Sequence, Union

from alembic import op

revision: str = "20260622_0002"
down_revision: Union[str, None] = "20260621_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE answer_type ADD VALUE IF NOT EXISTS 'general_llm'")
    op.execute("ALTER TYPE answer_type ADD VALUE IF NOT EXISTS 'refused'")


def downgrade() -> None:
    # PostgreSQL cannot safely drop enum values without recreating the type.
    # Keep downgrade as a no-op to avoid destructive data rewrites.
    pass
