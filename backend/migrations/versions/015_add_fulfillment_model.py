"""015: 履約模型 — 銷貨欠貨 + PO 來源追蹤 + 履約分配表 + 通知紀錄表

sale_lines: 欠貨 qty 欄位 + 履約狀態 + 通知欄位
sales: has_backorder 快取
purchase_order_lines: source 來源追蹤
sale_line_fulfillments: 履約分配表（多對多）
customer_pickup_notifications: 通知紀錄表
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


def upgrade():
    # ── 1. sale_lines 加履約欄位 ─────────────────────────
    for col_name, col_type, default in [
        ("ordered_qty", sa.Integer, None),          # 原始訂購量（= quantity）
        ("delivered_qty", sa.Integer, "0"),          # 當下已交量
        ("backorder_qty", sa.Integer, "0"),          # 欠貨量
        ("backorder_ordered_qty", sa.Integer, "0"),  # 已對外採購量
        ("backorder_arrived_qty", sa.Integer, "0"),  # 已到貨量
        ("backorder_delivered_qty", sa.Integer, "0"),# 已補交量
    ]:
        if default is not None:
            op.add_column("sale_lines", sa.Column(col_name, col_type, nullable=False, server_default=default))
        else:
            # ordered_qty 先加 nullable，再回填，再改 NOT NULL
            op.add_column("sale_lines", sa.Column(col_name, col_type, nullable=True))

    # ordered_qty 回填 = quantity
    op.execute("UPDATE sale_lines SET ordered_qty = quantity WHERE ordered_qty IS NULL")
    op.alter_column("sale_lines", "ordered_qty", nullable=False)

    # delivered_qty 回填 = quantity（既有銷貨都已交付）
    op.execute("UPDATE sale_lines SET delivered_qty = quantity WHERE delivered_qty = 0")

    op.add_column("sale_lines", sa.Column("fulfillment_status", sa.String(30), nullable=False, server_default="completed"))
    op.add_column("sale_lines", sa.Column("backorder_status", sa.String(30), nullable=True))
    op.add_column("sale_lines", sa.Column("reserved_customer_note", sa.Text, nullable=True))
    op.add_column("sale_lines", sa.Column("notified_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("sale_lines", sa.Column("notify_count", sa.Integer, nullable=False, server_default="0"))
    op.add_column("sale_lines", sa.Column("last_notify_channel", sa.String(20), nullable=True))
    op.add_column("sale_lines", sa.Column("pickup_completed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("sale_lines", sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True))

    op.create_index("ix_sale_lines_fulfillment_status", "sale_lines", ["fulfillment_status"])
    op.create_index("ix_sale_lines_backorder_status", "sale_lines", ["backorder_status"])

    # ── 2. sales 加 has_backorder ────────────────────────
    op.add_column("sales", sa.Column("has_backorder", sa.Boolean, nullable=False, server_default="false"))

    # ── 3. purchase_order_lines 加來源追蹤 ───────────────
    op.add_column("purchase_order_lines", sa.Column("source_type", sa.String(30), nullable=False, server_default="restock"))
    op.add_column("purchase_order_lines", sa.Column("source_customer_id", UUID(as_uuid=True), nullable=True))
    op.add_column("purchase_order_lines", sa.Column("source_sale_id", UUID(as_uuid=True), nullable=True))
    op.add_column("purchase_order_lines", sa.Column("source_sale_line_id", UUID(as_uuid=True), nullable=True))
    op.add_column("purchase_order_lines", sa.Column("reserved_qty", sa.Integer, nullable=False, server_default="0"))
    op.add_column("purchase_order_lines", sa.Column("allocated_qty", sa.Integer, nullable=False, server_default="0"))

    op.create_index("ix_po_lines_source_type", "purchase_order_lines", ["source_type"])
    op.create_index("ix_po_lines_source_customer", "purchase_order_lines", ["source_customer_id"])
    op.create_index("ix_po_lines_source_sale_line", "purchase_order_lines", ["source_sale_line_id"])

    # ── 4. sale_line_fulfillments 履約分配表 ─────────────
    op.create_table(
        "sale_line_fulfillments",
        sa.Column("fulfillment_id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("sale_id", UUID(as_uuid=True), sa.ForeignKey("sales.sale_id"), nullable=False),
        sa.Column("sale_line_id", UUID(as_uuid=True), sa.ForeignKey("sale_lines.sale_line_id"), nullable=False),
        sa.Column("source_type", sa.String(30), nullable=False),  # inventory / purchase_order / transfer / substitute / manual_adjustment
        sa.Column("source_doc_id", UUID(as_uuid=True), nullable=True),   # po_id / transfer_id / ...
        sa.Column("source_line_id", UUID(as_uuid=True), nullable=True),  # po_line_id / ...
        sa.Column("allocated_qty", sa.Integer, nullable=False),
        sa.Column("arrived_qty", sa.Integer, nullable=False, server_default="0"),
        sa.Column("delivered_qty", sa.Integer, nullable=False, server_default="0"),
        sa.Column("status", sa.String(30), nullable=False, server_default="pending"),
        sa.Column("note", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )
    op.create_index("ix_slf_sale_line", "sale_line_fulfillments", ["sale_line_id"])
    op.create_index("ix_slf_source_doc", "sale_line_fulfillments", ["source_doc_id"])
    op.create_index("ix_slf_status", "sale_line_fulfillments", ["status"])

    # ── 5. customer_pickup_notifications 通知紀錄表 ──────
    op.create_table(
        "customer_pickup_notifications",
        sa.Column("notification_id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("customer_id", UUID(as_uuid=True), sa.ForeignKey("customers.customer_id"), nullable=False),
        sa.Column("sale_id", UUID(as_uuid=True), sa.ForeignKey("sales.sale_id"), nullable=False),
        sa.Column("sale_line_id", UUID(as_uuid=True), nullable=True),
        sa.Column("channel", sa.String(20), nullable=False, server_default="manual"),  # line / phone / sms / manual
        sa.Column("message_snapshot", sa.Text, nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="sent"),  # pending / sent / failed / acknowledged
        sa.Column("sent_by", UUID(as_uuid=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("remark", sa.Text, nullable=True),
    )
    op.create_index("ix_cpn_customer", "customer_pickup_notifications", ["customer_id"])
    op.create_index("ix_cpn_sale", "customer_pickup_notifications", ["sale_id"])


def downgrade():
    op.drop_table("customer_pickup_notifications")
    op.drop_table("sale_line_fulfillments")

    for col in ["source_type", "source_customer_id", "source_sale_id",
                 "source_sale_line_id", "reserved_qty", "allocated_qty"]:
        op.drop_column("purchase_order_lines", col)

    op.drop_column("sales", "has_backorder")

    for col in ["ordered_qty", "delivered_qty", "backorder_qty",
                 "backorder_ordered_qty", "backorder_arrived_qty", "backorder_delivered_qty",
                 "fulfillment_status", "backorder_status", "reserved_customer_note",
                 "notified_at", "notify_count", "last_notify_channel",
                 "pickup_completed_at", "closed_at"]:
        op.drop_column("sale_lines", col)
