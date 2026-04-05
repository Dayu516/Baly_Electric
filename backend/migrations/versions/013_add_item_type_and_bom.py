"""013: SKU 加 item_type + product_bom 表

品項結構化：
- skus.item_type: finished/assembly/accessory/component (CHECK constraint)
- product_bom: 組成關係表 (FK + UNIQUE constraint)
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


def upgrade():
    # 1. skus 加 item_type
    op.add_column("skus", sa.Column("item_type", sa.String(20), nullable=False, server_default="finished"))
    op.create_index("ix_skus_item_type", "skus", ["item_type"])
    op.create_check_constraint(
        "ck_skus_item_type",
        "skus",
        "item_type IN ('finished', 'assembly', 'accessory', 'component')",
    )

    # 2. product_bom 表
    op.create_table(
        "product_bom",
        sa.Column("bom_id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("parent_sku_id", UUID(as_uuid=True), sa.ForeignKey("skus.sku_id"), nullable=False),
        sa.Column("child_sku_id", UUID(as_uuid=True), sa.ForeignKey("skus.sku_id"), nullable=False),
        sa.Column("quantity", sa.Integer, nullable=False, server_default="1"),
        sa.Column("component_role", sa.String(30), nullable=True),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("note", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )
    op.create_index("ix_bom_parent", "product_bom", ["parent_sku_id"])
    op.create_index("ix_bom_child", "product_bom", ["child_sku_id"])
    op.create_unique_constraint("uq_bom_parent_child_role", "product_bom", ["parent_sku_id", "child_sku_id", "component_role"])


def downgrade():
    op.drop_table("product_bom")
    op.drop_constraint("ck_skus_item_type", "skus", type_="check")
    op.drop_index("ix_skus_item_type", "skus")
    op.drop_column("skus", "item_type")
