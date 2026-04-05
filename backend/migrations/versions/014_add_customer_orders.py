"""014: 客訂追蹤 — 3 張新表

customer_orders        — 主表（聚合狀態）
customer_order_lines   — 明細（真實執行狀態 + 數量追蹤）
customer_order_line_po_links — 客訂明細 ↔ PO 明細 關聯
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


def upgrade():
    # 1. customer_orders 主表
    op.create_table(
        "customer_orders",
        sa.Column("order_id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("customer_id", UUID(as_uuid=True), sa.ForeignKey("customers.customer_id"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("note", sa.Text, nullable=True),
        sa.Column("expected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_notified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notify_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("pickup_deadline_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_contact_note", sa.Text, nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), nullable=True),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )
    op.create_index("ix_customer_orders_customer_id", "customer_orders", ["customer_id"])
    op.create_index("ix_customer_orders_status", "customer_orders", ["status"])
    op.create_check_constraint(
        "ck_customer_orders_status",
        "customer_orders",
        "status IN ('pending', 'sourcing', 'partial_arrived', 'arrived', 'partial_picked_up', 'completed', 'cancelled')",
    )

    # 2. customer_order_lines 明細
    op.create_table(
        "customer_order_lines",
        sa.Column("line_id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("order_id", UUID(as_uuid=True), sa.ForeignKey("customer_orders.order_id"), nullable=False),
        sa.Column("sku_id", UUID(as_uuid=True), nullable=True),
        sa.Column("product_name", sa.String(200), nullable=False),
        sa.Column("spec", sa.String(200), nullable=True),
        sa.Column("quantity", sa.Integer, nullable=False, server_default="1"),
        sa.Column("ordered_qty", sa.Integer, nullable=False, server_default="0"),
        sa.Column("arrived_qty", sa.Integer, nullable=False, server_default="0"),
        sa.Column("picked_up_qty", sa.Integer, nullable=False, server_default="0"),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("source_type", sa.String(20), nullable=False, server_default="sku"),
        sa.Column("supplier_id", UUID(as_uuid=True), nullable=True),
        sa.Column("linked_pos_sale_id", UUID(as_uuid=True), nullable=True),
        sa.Column("line_status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("sequence", sa.Integer, nullable=False, server_default="0"),
        sa.Column("note", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )
    op.create_index("ix_customer_order_lines_order_id", "customer_order_lines", ["order_id"])
    op.create_index("ix_customer_order_lines_sku_id", "customer_order_lines", ["sku_id"])
    op.create_check_constraint(
        "ck_customer_order_lines_status",
        "customer_order_lines",
        "line_status IN ('pending', 'ordered', 'partial_arrived', 'arrived', 'partial_picked_up', 'picked_up', 'cancelled')",
    )

    # 3. customer_order_line_po_links 關聯表
    op.create_table(
        "customer_order_line_po_links",
        sa.Column("link_id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("line_id", UUID(as_uuid=True), sa.ForeignKey("customer_order_lines.line_id"), nullable=False),
        sa.Column("po_id", UUID(as_uuid=True), sa.ForeignKey("purchase_orders.po_id"), nullable=False),
        sa.Column("po_line_id", UUID(as_uuid=True), nullable=True),
        sa.Column("quantity", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )
    op.create_index("ix_co_line_po_links_line_id", "customer_order_line_po_links", ["line_id"])
    op.create_index("ix_co_line_po_links_po_id", "customer_order_line_po_links", ["po_id"])


def downgrade():
    op.drop_table("customer_order_line_po_links")
    op.drop_table("customer_order_lines")
    op.drop_table("customer_orders")
