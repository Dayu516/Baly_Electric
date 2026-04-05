"""Add customer_price_history table.

Revision ID: 004
Revises: 003
Create Date: 2026-04-02
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "customer_price_history",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("customer_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("sku_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("last_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("last_cost", sa.Numeric(12, 2), nullable=True),
        sa.Column("last_sold_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sale_id", UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    # 複合索引：快速查詢某客戶某品項的歷史價
    op.create_index("ix_cph_customer_sku", "customer_price_history", ["customer_id", "sku_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_cph_customer_sku", "customer_price_history")
    op.drop_table("customer_price_history")