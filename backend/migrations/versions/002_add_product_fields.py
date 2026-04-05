"""Add raw_name, series to products; supplier_code, internal_code to skus.

Revision ID: 002
Revises: 001
Create Date: 2026-04-02
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Products: 加 raw_name, series, category_id index, brand index
    op.add_column("products", sa.Column("raw_name", sa.String(200), nullable=True))
    op.add_column("products", sa.Column("series", sa.String(100), nullable=True))
    op.create_index("ix_products_category_id", "products", ["category_id"])
    op.create_index("ix_products_brand", "products", ["brand"])

    # SKUs: 加 supplier_code, internal_code
    op.add_column("skus", sa.Column("supplier_code", sa.String(50), nullable=True))
    op.add_column("skus", sa.Column("internal_code", sa.String(50), nullable=True))
    op.create_index("ix_skus_supplier_code", "skus", ["supplier_code"])
    op.create_index("ix_skus_internal_code", "skus", ["internal_code"])


def downgrade() -> None:
    op.drop_index("ix_skus_internal_code", "skus")
    op.drop_index("ix_skus_supplier_code", "skus")
    op.drop_column("skus", "internal_code")
    op.drop_column("skus", "supplier_code")

    op.drop_index("ix_products_brand", "products")
    op.drop_index("ix_products_category_id", "products")
    op.drop_column("products", "series")
    op.drop_column("products", "raw_name")