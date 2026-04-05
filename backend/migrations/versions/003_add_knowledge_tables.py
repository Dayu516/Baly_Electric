"""Add product knowledge tables: aliases, customer mappings, supplier products.

Revision ID: 003
Revises: 002
Create Date: 2026-04-02
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 品項別名 ─────────────────────────────────────
    op.create_table(
        "product_aliases",
        sa.Column("alias_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("product_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("alias", sa.String(200), nullable=False, index=True),
        sa.Column("alias_type", sa.String(30), nullable=False, server_default="common"),
        sa.Column("created_by", UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # ── 客戶專屬對應 ─────────────────────────────────
    op.create_table(
        "customer_product_mappings",
        sa.Column("mapping_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("customer_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("keyword", sa.String(200), nullable=False),
        sa.Column("sku_id", UUID(as_uuid=True), nullable=False),
        sa.Column("note", sa.Text, nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # ── 供應商品項對應 ───────────────────────────────
    op.create_table(
        "supplier_products",
        sa.Column("sp_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("supplier_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("sku_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("supplier_product_name", sa.String(200), nullable=True),
        sa.Column("supplier_product_code", sa.String(50), nullable=True),
        sa.Column("pack_unit", sa.String(50), nullable=True),
        sa.Column("pack_qty", sa.Integer, nullable=True),
        sa.Column("min_order_qty", sa.Integer, nullable=True),
        sa.Column("lead_days", sa.Integer, nullable=True),
        sa.Column("unit_cost", sa.Numeric(12, 2), nullable=True),
        sa.Column("is_preferred", sa.Boolean, server_default="false"),
        sa.Column("note", sa.Text, nullable=True),
        sa.Column("updated_by", UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("supplier_products")
    op.drop_table("customer_product_mappings")
    op.drop_table("product_aliases")