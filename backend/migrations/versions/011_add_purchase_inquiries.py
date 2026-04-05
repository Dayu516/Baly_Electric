"""Add purchase inquiry tables for quotation workflow.

Flow: 建立詢價單 → 記錄各供應商報價 → 比價 → 轉採購單

Revision ID: 011
Revises: 010
Create Date: 2026-04-03
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision: str = "011"
down_revision: Union[str, None] = "010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 詢價單
    op.create_table(
        "purchase_inquiries",
        sa.Column("inquiry_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
            # draft / quoting / decided / converted / cancelled
        sa.Column("note", sa.Text, nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # 詢價明細行（要詢的品項 + 數量）
    op.create_table(
        "purchase_inquiry_lines",
        sa.Column("line_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("inquiry_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("sku_id", UUID(as_uuid=True), nullable=False),
        sa.Column("quantity", sa.Integer, nullable=False),
        sa.Column("note", sa.Text, nullable=True),
    )

    # 各供應商對每行的報價
    op.create_table(
        "purchase_inquiry_quotes",
        sa.Column("quote_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("inquiry_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("line_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("supplier_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("note", sa.Text, nullable=True),
        sa.Column("is_selected", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("purchase_inquiry_quotes")
    op.drop_table("purchase_inquiry_lines")
    op.drop_table("purchase_inquiries")
