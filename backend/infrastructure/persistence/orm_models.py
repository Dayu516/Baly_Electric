"""SQLAlchemy ORM models — 所有表定義集中在此。

Phase A 建立的表：
  - users
  - products, skus, categories, product_search_docs
  - sales, sale_lines
  - stock_movements, inventory_balances
  - suppliers, purchase_orders, purchase_order_lines, purchase_receipts, purchase_receipt_lines
  - customers, accounts_receivables
  - sale_line_fulfillments, customer_pickup_notifications
  - review_tasks
  - operational_alerts
  - system_jobs
  - audit_events
  - company_info, system_parameters
"""

import uuid

from sqlalchemy import (
    Boolean,
    DateTime,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.base_model import AuditMixin, Base, TimestampMixin, VersionMixin


# ═══════════════════════════════════════════════════════════
# User
# ═══════════════════════════════════════════════════════════
class UserORM(Base, TimestampMixin):
    __tablename__ = "users"

    user_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="staff")  # owner/manager/staff
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_login_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)


# ═══════════════════════════════════════════════════════════
# Product / SKU / Category
# ═══════════════════════════════════════════════════════════
class CategoryORM(Base, TimestampMixin, VersionMixin, AuditMixin):
    __tablename__ = "categories"

    category_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class CategoryAttributeTemplateORM(Base):
    """分類屬性模板 — 定義每個分類的品項應該有哪些屬性欄位。"""
    __tablename__ = "category_attribute_templates"

    template_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    category_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    attr_key: Mapped[str] = mapped_column(String(50), nullable=False)       # 屬性名（額定電流、線徑）
    attr_unit: Mapped[str | None] = mapped_column(String(20), nullable=True)  # 單位（A、mm²、kA）
    is_required: Mapped[bool] = mapped_column(Boolean, default=False)        # 必填？
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    attr_options: Mapped[str | None] = mapped_column(Text, nullable=True)      # JSON: ["30mm","25mm"]
    match_priority: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 替代品比對權重（1=最重要）
    match_type: Mapped[str | None] = mapped_column(String(20), nullable=True)   # must / prefer / optional


class ProductAttributeORM(Base, TimestampMixin):
    """品項屬性 — key-value 儲存任意技術規格。"""
    __tablename__ = "product_attributes"

    attr_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    attr_key: Mapped[str] = mapped_column(String(50), nullable=False)       # 屬性名
    attr_value: Mapped[str] = mapped_column(String(200), nullable=False)    # 值
    attr_unit: Mapped[str | None] = mapped_column(String(20), nullable=True)  # 單位


class ProductORM(Base, TimestampMixin, VersionMixin, AuditMixin):
    __tablename__ = "products"

    product_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)  # 標準化品名
    raw_name: Mapped[str | None] = mapped_column(String(200), nullable=True)    # 原始品名（匯入保留底）
    series: Mapped[str | None] = mapped_column(String(100), nullable=True)      # 系列（BH、MY2N）
    model_number: Mapped[str] = mapped_column(String(100), nullable=True, index=True)
    category_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class SKUORM(Base, TimestampMixin, VersionMixin, AuditMixin):
    __tablename__ = "skus"

    sku_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    brand: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)  # 品牌（SKU 層級）
    barcode: Mapped[str | None] = mapped_column(String(50), nullable=True, unique=True, index=True)
    supplier_code: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)   # 供應商料號
    internal_code: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)   # 內部編號（凌越原始編號）
    spec: Mapped[str] = mapped_column(String(200), nullable=True)  # 規格（如：2P 20A）
    unit: Mapped[str] = mapped_column(String(20), nullable=False, default="個")
    sell_price: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    cost_price: Mapped[float] = mapped_column(Numeric(12, 2), nullable=True)
    min_stock: Mapped[int] = mapped_column(Integer, nullable=True)  # 安全庫存量
    item_type: Mapped[str] = mapped_column(String(20), nullable=False, default="finished")  # finished/assembly/accessory/component
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class ProductBomORM(Base):
    """BOM 組成關係 — 靜態關係表，記錄組合品由哪些件組成。"""
    __tablename__ = "product_bom"

    bom_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    parent_sku_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    child_sku_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    component_role: Mapped[str | None] = mapped_column(String(30), nullable=True)  # 主體/積熱/線圈/配件
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ProductSearchDocORM(Base, TimestampMixin):
    """品項搜尋文件。Phase A 只用 search_text，embedding 欄位 Phase B 才填。"""
    __tablename__ = "product_search_docs"

    product_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    search_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # embedding: Phase B 加入 pgvector 欄位


class ProductAliasORM(Base, TimestampMixin):
    """品項別名 — 口語、客戶叫法、舊系統名稱。搜尋時一起查。"""
    __tablename__ = "product_aliases"

    alias_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    alias: Mapped[str] = mapped_column(String(200), nullable=False, index=True)  # 別名文字
    alias_type: Mapped[str] = mapped_column(String(30), nullable=False, default="common")
    # common=通用口語, customer=客戶叫法, supplier=供應商叫法, legacy=舊系統名稱
    created_by: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)


class CustomerProductMappingORM(Base, TimestampMixin):
    """客戶專屬對應 — 某客戶講X，實際是品項Y。"""
    __tablename__ = "customer_product_mappings"

    mapping_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    keyword: Mapped[str] = mapped_column(String(200), nullable=False)  # 客戶講的話
    sku_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)  # 實際對應的 SKU
    note: Mapped[str | None] = mapped_column(Text, nullable=True)  # 備註（如「張師傅慣用」）
    created_by: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)


class SupplierProductORM(Base, TimestampMixin, AuditMixin):
    """供應商品項對應 — 供應商對此品項的叫法、包裝、成本。"""
    __tablename__ = "supplier_products"

    sp_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    supplier_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    sku_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    supplier_product_name: Mapped[str | None] = mapped_column(String(200), nullable=True)  # 供應商叫這個品名
    supplier_product_code: Mapped[str | None] = mapped_column(String(50), nullable=True)   # 供應商料號
    pack_unit: Mapped[str | None] = mapped_column(String(50), nullable=True)    # 包裝單位（如「1包=25kg」）
    pack_qty: Mapped[int | None] = mapped_column(Integer, nullable=True)         # 包裝數量
    min_order_qty: Mapped[int | None] = mapped_column(Integer, nullable=True)    # 最小訂購量
    lead_days: Mapped[int | None] = mapped_column(Integer, nullable=True)        # 到貨天數
    unit_cost: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)  # 進貨成本
    is_preferred: Mapped[bool] = mapped_column(Boolean, default=False)           # 優先供應商
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class SupplierPriceQuoteORM(Base):
    """供應商報價紀錄 — append-only，追蹤每次詢價/報價。"""
    __tablename__ = "supplier_price_quotes"

    quote_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    supplier_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    sku_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    unit_price: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    unit: Mapped[str | None] = mapped_column(String(20), nullable=True)
    quoted_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    created_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)


# ═══════════════════════════════════════════════════════════
# Purchase Inquiry
# ═══════════════════════════════════════════════════════════
class PurchaseInquiryORM(Base):
    """詢價單。"""
    __tablename__ = "purchase_inquiries"

    inquiry_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    created_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PurchaseInquiryLineORM(Base):
    """詢價明細行。"""
    __tablename__ = "purchase_inquiry_lines"

    line_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    inquiry_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    sku_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class PurchaseInquiryQuoteORM(Base):
    """各供應商對每行的報價。"""
    __tablename__ = "purchase_inquiry_quotes"

    quote_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    inquiry_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    line_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    supplier_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    unit_price: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_selected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)


# ═══════════════════════════════════════════════════════════
# Sales Quotation
# ═══════════════════════════════════════════════════════════
class SalesQuotationORM(Base):
    """報價單（給客戶）。"""
    __tablename__ = "sales_quotations"

    quotation_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    quotation_number: Mapped[str | None] = mapped_column(String(30), nullable=True)
    customer_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    quotation_date: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    valid_until: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    contact_person: Mapped[str | None] = mapped_column(String(100), nullable=True)
    quotation_type: Mapped[str] = mapped_column(String(30), nullable=False, default="general")
    project_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # 商業條件
    tax_mode: Mapped[str] = mapped_column(String(20), nullable=False, default="excluded")
    payment_terms_text: Mapped[str | None] = mapped_column(String(200), nullable=True)
    delivery_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    delivery_terms: Mapped[str | None] = mapped_column(String(200), nullable=True)
    shipping_terms: Mapped[str | None] = mapped_column(String(200), nullable=True)
    warranty_terms: Mapped[str | None] = mapped_column(String(200), nullable=True)
    special_terms: Mapped[str | None] = mapped_column(Text, nullable=True)
    valid_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="TWD")
    includes_installation: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # 轉單
    expected_close_date: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    win_probability: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_inquiry_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    converted_sale_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    internal_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    created_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SalesQuotationLineORM(Base):
    """報價單明細行。"""
    __tablename__ = "sales_quotation_lines"

    line_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    quotation_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    sku_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class CustomerPriceHistoryORM(Base, TimestampMixin):
    """客戶歷史售價 — 記住上次賣這個客人這個品項多少錢。"""
    __tablename__ = "customer_price_history"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    sku_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    last_price: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)     # 上次賣多少
    last_cost: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)  # 當時成本
    last_sold_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False)  # 上次什麼時候賣
    sale_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)  # 對應哪筆交易


# ═══════════════════════════════════════════════════════════
# Sales
# ═══════════════════════════════════════════════════════════
class SaleORM(Base, TimestampMixin):
    __tablename__ = "sales"

    sale_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True, index=True)
    cashier_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="completed")  # completed / voided
    payment_method: Mapped[str] = mapped_column(String(20), nullable=False, default="cash")
    tax_included: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)  # 含稅交易
    subtotal: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)  # 未稅小計
    tax_amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)  # 稅額
    discount_amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    total: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)  # 含稅總額（或未稅總額）
    receipt_printed: Mapped[bool] = mapped_column(Boolean, default=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    client_tx_id: Mapped[str | None] = mapped_column(String(50), nullable=True, unique=True)  # 離線冪等
    has_backorder: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)  # 快取：有欠貨待補


class SaleLineORM(Base):
    __tablename__ = "sale_lines"

    sale_line_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sale_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    sku_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    product_name: Mapped[str] = mapped_column(String(200), nullable=False)  # 快照
    spec: Mapped[str] = mapped_column(String(200), nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    discount_amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    line_total: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    # ── 履約欄位 ──────────────────────────────────────
    ordered_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0)          # 原始訂購量
    delivered_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0)        # 當下已交量
    backorder_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0)        # 欠貨量
    backorder_ordered_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # 已對外採購量
    backorder_arrived_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # 已到貨量
    backorder_delivered_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0) # 已補交量
    fulfillment_status: Mapped[str] = mapped_column(String(30), nullable=False, default="completed")
    backorder_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    reserved_customer_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    notified_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notify_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_notify_channel: Mapped[str | None] = mapped_column(String(20), nullable=True)
    pickup_completed_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)


# ═══════════════════════════════════════════════════════════
# Inventory
# ═══════════════════════════════════════════════════════════
class StockMovementORM(Base, TimestampMixin):
    __tablename__ = "stock_movements"

    movement_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sku_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)  # 正=入庫, 負=出庫
    movement_type: Mapped[str] = mapped_column(String(30), nullable=False)  # sale/purchase_receive/adjustment/return/initial
    reference_type: Mapped[str] = mapped_column(String(30), nullable=False)  # sale/purchase_receipt/stock_count/manual/import
    reference_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)


class InventoryBalanceORM(Base, TimestampMixin):
    __tablename__ = "inventory_balances"

    sku_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    current_stock: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_recalc_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)


# ═══════════════════════════════════════════════════════════
# Procurement
# ═══════════════════════════════════════════════════════════
class SupplierORM(Base, TimestampMixin, VersionMixin, AuditMixin):
    __tablename__ = "suppliers"

    supplier_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    contact_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class PurchaseOrderORM(Base, TimestampMixin, AuditMixin):
    __tablename__ = "purchase_orders"

    po_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    supplier_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    ordered_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PurchaseOrderLineORM(Base):
    __tablename__ = "purchase_order_lines"

    po_line_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    po_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    sku_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    ordered_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    received_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unit_cost: Mapped[float] = mapped_column(Numeric(12, 2), nullable=True)
    # ── 來源追蹤 ──────────────────────────────────────
    source_type: Mapped[str] = mapped_column(String(30), nullable=False, default="restock")  # restock/customer_backorder/quote_confirmed/manual_special_order
    source_customer_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    source_sale_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    source_sale_line_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    reserved_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    allocated_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class PurchaseReceiptORM(Base, TimestampMixin):
    __tablename__ = "purchase_receipts"

    receipt_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    po_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True, index=True)
    supplier_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    received_by: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class PurchaseReceiptLineORM(Base):
    __tablename__ = "purchase_receipt_lines"

    receipt_line_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    receipt_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    sku_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_cost: Mapped[float] = mapped_column(Numeric(12, 2), nullable=True)


# ═══════════════════════════════════════════════════════════
# Customer / Accounts Receivable
# ═══════════════════════════════════════════════════════════
class CustomerORM(Base, TimestampMixin, VersionMixin, AuditMixin):
    __tablename__ = "customers"

    customer_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    short_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    tax_id: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    customer_type: Mapped[str] = mapped_column(String(30), nullable=False, default="general")
    customer_code: Mapped[str | None] = mapped_column(String(30), nullable=True)
    # 聯絡
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    contact_person: Mapped[str | None] = mapped_column(String(100), nullable=True)
    mobile: Mapped[str | None] = mapped_column(String(30), nullable=True)
    email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    line_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    shipping_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 交易條件
    payment_terms: Mapped[str] = mapped_column(String(20), nullable=False, default="cash")
    payment_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    price_level: Mapped[str] = mapped_column(String(30), nullable=False, default="retail")
    credit_limit: Mapped[float] = mapped_column(Numeric(12, 2), nullable=True)
    discount_rate: Mapped[float] = mapped_column(Numeric(5, 4), nullable=True)
    allow_debt: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    invoice_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    invoice_title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    invoice_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    invoice_delivery: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # 業務管理
    sales_rep: Mapped[str | None] = mapped_column(String(100), nullable=True)
    source: Mapped[str | None] = mapped_column(String(50), nullable=True)
    customer_level: Mapped[str | None] = mapped_column(String(10), nullable=True)
    cooperation_status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    tags: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON array
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class AccountsReceivableORM(Base, TimestampMixin):
    __tablename__ = "accounts_receivables"

    ar_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    period: Mapped[str] = mapped_column(String(7), nullable=False)  # YYYY-MM
    total_amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    paid_amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")  # open/partial_paid/paid/overdue
    due_date: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    paid_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


# ═══════════════════════════════════════════════════════════
# Review / Alert / SystemJob / Audit
# ═══════════════════════════════════════════════════════════
class ReviewTaskORM(Base, TimestampMixin):
    __tablename__ = "review_tasks"

    task_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    review_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    # product_confirm / stock_discrepancy / monthly_reconcile
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    # pending / claimed / completed / rejected
    resolution: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # approved / modified / rejected
    reference_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    reference_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    claimed_by: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    claimed_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    resolved_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class OperationalAlertORM(Base, TimestampMixin):
    __tablename__ = "operational_alerts"

    alert_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    alert_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    # low_stock / overdue / backup_failed / sync_failed / stock_inconsistency
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="info")  # info/warning/critical
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    reference_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    reference_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    expires_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SystemJobORM(Base, TimestampMixin):
    __tablename__ = "system_jobs"

    job_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_type: Mapped[str] = mapped_column(String(30), nullable=False)  # backup / recalc
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="running")  # running/completed/failed
    started_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)


class AuditEventORM(Base, TimestampMixin):
    __tablename__ = "audit_events"

    event_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    # create_product / update_price / void_sale / adjust_stock / login / ...
    entity_type: Mapped[str] = mapped_column(String(30), nullable=False)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON snapshot
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)


# ═══════════════════════════════════════════════════════════
# System Settings
# ═══════════════════════════════════════════════════════════
class CompanyInfoORM(Base):
    """公司資料 — 單列表，只有一筆 (id=1)。"""
    __tablename__ = "company_info"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    short_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    tax_id: Mapped[str | None] = mapped_column(String(20), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    fax: Mapped[str | None] = mapped_column(String(30), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    owner_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SystemParameterORM(Base):
    """系統參數 — key-value 表。"""
    __tablename__ = "system_parameters"

    key: Mapped[str] = mapped_column(String(50), primary_key=True)
    value: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    description: Mapped[str | None] = mapped_column(String(200), nullable=True)
    updated_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)


# ═══════════════════════════════════════════════════════════
# Fulfillment（履約分配 + 取貨通知）
# ═══════════════════════════════════════════════════════════
class SaleLineFulfillmentORM(Base, TimestampMixin):
    """履約分配 — 記錄一筆銷貨需求由哪些來源補了多少。"""
    __tablename__ = "sale_line_fulfillments"

    fulfillment_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sale_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    sale_line_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(30), nullable=False)  # inventory/purchase_order/transfer/substitute/manual_adjustment
    source_doc_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    source_line_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    allocated_qty: Mapped[int] = mapped_column(Integer, nullable=False)
    arrived_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    delivered_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class CustomerPickupNotificationORM(Base):
    """客戶取貨通知紀錄。"""
    __tablename__ = "customer_pickup_notifications"

    notification_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    sale_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    sale_line_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    channel: Mapped[str] = mapped_column(String(20), nullable=False, default="manual")
    message_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="sent")
    sent_by: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    sent_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)



# NOTE: customer_orders / customer_order_lines / customer_order_line_po_links
# DB 表仍存在（migration 014），但 ORM class 已移除。
# 新流程使用 sale_lines 履約欄位 + sale_line_fulfillments + customer_pickup_notifications。
