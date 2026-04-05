"""Initial schema — Phase A 所有表。

Revision ID: 001
Revises: None
Create Date: 2026-04-01
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Users ─────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("user_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("username", sa.String(50), unique=True, nullable=False, index=True),
        sa.Column("display_name", sa.String(100), nullable=False),
        sa.Column("role", sa.String(20), nullable=False, server_default="staff"),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # ── Categories ────────────────────────────────────
    op.create_table(
        "categories",
        sa.Column("category_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False, index=True),
        sa.Column("parent_id", UUID(as_uuid=True), nullable=True),
        sa.Column("sort_order", sa.Integer, server_default="0"),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("updated_by", UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # ── Products ──────────────────────────────────────
    op.create_table(
        "products",
        sa.Column("product_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False, index=True),
        sa.Column("brand", sa.String(100), nullable=True),
        sa.Column("model_number", sa.String(100), nullable=True, index=True),
        sa.Column("category_id", UUID(as_uuid=True), nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("updated_by", UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # ── SKUs ──────────────────────────────────────────
    op.create_table(
        "skus",
        sa.Column("sku_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("product_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("barcode", sa.String(50), nullable=True, unique=True, index=True),
        sa.Column("spec", sa.String(200), nullable=True),
        sa.Column("unit", sa.String(20), nullable=False, server_default="個"),
        sa.Column("sell_price", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("cost_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("min_stock", sa.Integer, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("updated_by", UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # ── Product Search Docs ───────────────────────────
    op.create_table(
        "product_search_docs",
        sa.Column("product_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("search_text", sa.Text, nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # ── Sales ─────────────────────────────────────────
    op.create_table(
        "sales",
        sa.Column("sale_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("customer_id", UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("cashier_id", UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="completed"),
        sa.Column("payment_method", sa.String(20), nullable=False, server_default="cash"),
        sa.Column("subtotal", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("discount_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("total", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("receipt_printed", sa.Boolean, server_default="false"),
        sa.Column("note", sa.Text, nullable=True),
        sa.Column("client_tx_id", sa.String(50), nullable=True, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # ── Sale Lines ────────────────────────────────────
    op.create_table(
        "sale_lines",
        sa.Column("sale_line_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("sale_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("sku_id", UUID(as_uuid=True), nullable=False),
        sa.Column("product_name", sa.String(200), nullable=False),
        sa.Column("spec", sa.String(200), nullable=True),
        sa.Column("quantity", sa.Integer, nullable=False),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("discount_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("line_total", sa.Numeric(12, 2), nullable=False),
    )

    # ── Stock Movements ───────────────────────────────
    op.create_table(
        "stock_movements",
        sa.Column("movement_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("sku_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("quantity", sa.Integer, nullable=False),
        sa.Column("movement_type", sa.String(30), nullable=False),
        sa.Column("reference_type", sa.String(30), nullable=False),
        sa.Column("reference_id", UUID(as_uuid=True), nullable=True),
        sa.Column("note", sa.Text, nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # ── Inventory Balances ────────────────────────────
    op.create_table(
        "inventory_balances",
        sa.Column("sku_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("current_stock", sa.Integer, nullable=False, server_default="0"),
        sa.Column("last_recalc_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # ── Suppliers ─────────────────────────────────────
    op.create_table(
        "suppliers",
        sa.Column("supplier_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False, index=True),
        sa.Column("contact_name", sa.String(100), nullable=True),
        sa.Column("phone", sa.String(30), nullable=True),
        sa.Column("address", sa.Text, nullable=True),
        sa.Column("note", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("updated_by", UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # ── Purchase Orders ───────────────────────────────
    op.create_table(
        "purchase_orders",
        sa.Column("po_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("supplier_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("note", sa.Text, nullable=True),
        sa.Column("ordered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_by", UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # ── Purchase Order Lines ──────────────────────────
    op.create_table(
        "purchase_order_lines",
        sa.Column("po_line_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("po_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("sku_id", UUID(as_uuid=True), nullable=False),
        sa.Column("ordered_quantity", sa.Integer, nullable=False),
        sa.Column("received_quantity", sa.Integer, nullable=False, server_default="0"),
        sa.Column("unit_cost", sa.Numeric(12, 2), nullable=True),
    )

    # ── Purchase Receipts ─────────────────────────────
    op.create_table(
        "purchase_receipts",
        sa.Column("receipt_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("po_id", UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("supplier_id", UUID(as_uuid=True), nullable=False),
        sa.Column("received_by", UUID(as_uuid=True), nullable=False),
        sa.Column("note", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # ── Purchase Receipt Lines ────────────────────────
    op.create_table(
        "purchase_receipt_lines",
        sa.Column("receipt_line_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("receipt_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("sku_id", UUID(as_uuid=True), nullable=False),
        sa.Column("quantity", sa.Integer, nullable=False),
        sa.Column("unit_cost", sa.Numeric(12, 2), nullable=True),
    )

    # ── Customers ─────────────────────────────────────
    op.create_table(
        "customers",
        sa.Column("customer_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False, index=True),
        sa.Column("phone", sa.String(30), nullable=True),
        sa.Column("address", sa.Text, nullable=True),
        sa.Column("payment_terms", sa.String(20), nullable=False, server_default="cash"),
        sa.Column("credit_limit", sa.Numeric(12, 2), nullable=True),
        sa.Column("discount_rate", sa.Numeric(5, 4), nullable=True),
        sa.Column("note", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("updated_by", UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # ── Accounts Receivables ──────────────────────────
    op.create_table(
        "accounts_receivables",
        sa.Column("ar_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("customer_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("period", sa.String(7), nullable=False),
        sa.Column("total_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("paid_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column("due_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("note", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # ── Review Tasks ──────────────────────────────────
    op.create_table(
        "review_tasks",
        sa.Column("task_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("review_type", sa.String(30), nullable=False, index=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("resolution", sa.String(20), nullable=True),
        sa.Column("reference_type", sa.String(30), nullable=True),
        sa.Column("reference_id", UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("detail", sa.Text, nullable=True),
        sa.Column("claimed_by", UUID(as_uuid=True), nullable=True),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by", UUID(as_uuid=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # ── Operational Alerts ────────────────────────────
    op.create_table(
        "operational_alerts",
        sa.Column("alert_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("alert_type", sa.String(30), nullable=False, index=True),
        sa.Column("severity", sa.String(20), nullable=False, server_default="info"),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("detail", sa.Text, nullable=True),
        sa.Column("reference_type", sa.String(30), nullable=True),
        sa.Column("reference_id", UUID(as_uuid=True), nullable=True),
        sa.Column("is_read", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # ── System Jobs ───────────────────────────────────
    op.create_table(
        "system_jobs",
        sa.Column("job_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("job_type", sa.String(30), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="running"),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("detail", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # ── Audit Events ──────────────────────────────────
    op.create_table(
        "audit_events",
        sa.Column("event_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("action", sa.String(50), nullable=False, index=True),
        sa.Column("entity_type", sa.String(30), nullable=False),
        sa.Column("entity_id", UUID(as_uuid=True), nullable=True),
        sa.Column("detail", sa.Text, nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("audit_events")
    op.drop_table("system_jobs")
    op.drop_table("operational_alerts")
    op.drop_table("review_tasks")
    op.drop_table("accounts_receivables")
    op.drop_table("customers")
    op.drop_table("purchase_receipt_lines")
    op.drop_table("purchase_receipts")
    op.drop_table("purchase_order_lines")
    op.drop_table("purchase_orders")
    op.drop_table("suppliers")
    op.drop_table("inventory_balances")
    op.drop_table("stock_movements")
    op.drop_table("sale_lines")
    op.drop_table("sales")
    op.drop_table("product_search_docs")
    op.drop_table("skus")
    op.drop_table("products")
    op.drop_table("categories")
    op.drop_table("users")
