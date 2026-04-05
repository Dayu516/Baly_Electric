"""Move brand column from products to skus.

Product = 規格概念（不綁品牌）
SKU = 品牌變體（brand=太平洋 / 華新）

Revision ID: 009
Revises: 008
Create Date: 2026-04-03
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. 加 brand 到 skus
    op.add_column("skus", sa.Column("brand", sa.String(100), nullable=True))
    op.create_index("ix_skus_brand", "skus", ["brand"])

    # 2. 把現有 products.brand 複製到對應的 skus
    op.execute("""
        UPDATE skus s
        SET brand = p.brand
        FROM products p
        WHERE s.product_id = p.product_id
          AND p.brand IS NOT NULL
    """)

    # 3. 刪除 products.brand 索引和欄位
    op.drop_index("ix_products_brand", table_name="products")
    op.drop_column("products", "brand")


def downgrade() -> None:
    # 還原：加回 products.brand
    op.add_column("products", sa.Column("brand", sa.String(100), nullable=True))
    op.create_index("ix_products_brand", "products", ["brand"])

    # 複製回去（取第一個 SKU 的 brand）
    op.execute("""
        UPDATE products p
        SET brand = (
            SELECT s.brand FROM skus s
            WHERE s.product_id = p.product_id AND s.brand IS NOT NULL
            LIMIT 1
        )
    """)

    # 刪除 skus.brand
    op.drop_index("ix_skus_brand", table_name="skus")
    op.drop_column("skus", "brand")
