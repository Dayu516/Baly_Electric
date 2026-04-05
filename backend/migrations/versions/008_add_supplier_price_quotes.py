"""Add supplier_price_quotes table for tracking supplier price history.

Revision ID: 008
Revises: 007
Create Date: 2026-04-03
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "supplier_price_quotes",
        sa.Column("quote_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("supplier_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("sku_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("unit", sa.String(20), nullable=True),           # M、百M、捲、個
        sa.Column("quoted_at", sa.DateTime(timezone=True), nullable=False),  # 報價日期
        sa.Column("note", sa.Text, nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # 複合索引：快速查某 SKU 的所有供應商報價
    op.create_index("ix_spq_sku_supplier", "supplier_price_quotes", ["sku_id", "supplier_id"])


def downgrade() -> None:
    op.drop_index("ix_spq_sku_supplier", table_name="supplier_price_quotes")
    op.drop_table("supplier_price_quotes")
