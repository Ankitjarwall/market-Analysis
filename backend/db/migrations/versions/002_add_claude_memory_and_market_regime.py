"""add claude_memory and market_regime tables

Revision ID: 002_add_claude_memory_regime
Revises: 001
Create Date: 2026-03-31

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "002_add_claude_memory_regime"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "claude_memory",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=False),
        sa.Column("key", sa.String(length=255), nullable=False),
        sa.Column("value", postgresql.JSONB(), nullable=False),
        sa.Column("source", sa.String(length=100), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("validation_count", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("category", "key", name="uq_claude_memory_category_key"),
    )
    op.create_index("ix_claude_memory_category", "claude_memory", ["category"])

    op.create_table(
        "market_regime",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("regime", sa.String(length=50), nullable=False),
        sa.Column("vix_avg_5d", sa.Float(), nullable=True),
        sa.Column("nifty_trend_5d", sa.Float(), nullable=True),
        sa.Column("fii_net_5d", sa.Float(), nullable=True),
        sa.Column("put_call_ratio_avg", sa.Float(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("date", name="uq_market_regime_date"),
    )


def downgrade() -> None:
    op.drop_table("market_regime")
    op.drop_index("ix_claude_memory_category", table_name="claude_memory")
    op.drop_table("claude_memory")
