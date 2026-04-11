"""add user auto settings jsonb column

Revision ID: 003_add_user_auto_settings
Revises: 002_add_claude_memory_regime
Create Date: 2026-04-02

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "003_add_user_auto_settings"
down_revision: Union[str, None] = "002_add_claude_memory_regime"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("auto_settings", postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "auto_settings")