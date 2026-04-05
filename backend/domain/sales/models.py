"""Sales domain models — 含履約模型。"""

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4


# ── 履約狀態常數 ─────────────────────────────────────────
FULFILLMENT_STATUSES = {
    "pending",               # POS 結帳，全額待交
    "partially_delivered",   # 部分已交
    "fully_delivered",       # 全部已交（正常完成）
    "backordered",           # 全部欠貨
    "partially_backordered", # 部分交+部分欠貨
    "waiting_arrival",       # 欠貨已下 PO，等到貨
    "ready_for_pickup",      # 到貨了，等客人來拿
    "partially_picked_up",   # 部分補交
    "completed",             # 全部結案（含補交完成）
    "cancelled",             # 取消
}

BACKORDER_STATUSES = {
    "pending",           # 有欠，還沒下 PO
    "ordered",           # 已下 PO
    "partial_arrived",   # 部分到貨
    "arrived",           # 全到貨
    "partial_delivered",  # 部分補交
    "delivered",         # 全部補交完成
    "cancelled",         # 取消待補
}


@dataclass
class Sale:
    sale_id: UUID = field(default_factory=uuid4)
    customer_id: UUID | None = None
    cashier_id: UUID = field(default_factory=uuid4)
    status: str = "completed"  # completed / voided
    payment_method: str = "cash"  # cash / transfer / monthly_credit
    tax_included: bool = False    # 含稅交易
    subtotal: float = 0          # 未稅小計
    tax_amount: float = 0        # 稅額（5%）
    discount_amount: float = 0
    total: float = 0             # 最終金額
    receipt_printed: bool = False
    note: str | None = None
    client_tx_id: str | None = None
    has_backorder: bool = False   # 快取：有欠貨待補
    created_at: datetime | None = None


@dataclass
class SaleLine:
    sale_line_id: UUID = field(default_factory=uuid4)
    sale_id: UUID = field(default_factory=uuid4)
    sku_id: UUID = field(default_factory=uuid4)
    product_name: str = ""
    spec: str | None = None
    quantity: int = 0
    unit_price: float = 0
    discount_amount: float = 0
    line_total: float = 0
    # ── 履約欄位 ──────────────────────────────────────
    ordered_qty: int = 0               # 原始訂購量
    delivered_qty: int = 0             # 當下已交量
    backorder_qty: int = 0             # 欠貨量
    backorder_ordered_qty: int = 0     # 已對外採購量
    backorder_arrived_qty: int = 0     # 已到貨量
    backorder_delivered_qty: int = 0   # 已補交量
    fulfillment_status: str = "completed"
    backorder_status: str | None = None
    reserved_customer_note: str | None = None
    notified_at: datetime | None = None
    notify_count: int = 0
    last_notify_channel: str | None = None
    pickup_completed_at: datetime | None = None
    closed_at: datetime | None = None


@dataclass
class SaleLineFulfillment:
    """履約分配 — 記錄一筆需求由哪些來源補了多少。"""
    fulfillment_id: UUID = field(default_factory=uuid4)
    sale_id: UUID = field(default_factory=uuid4)
    sale_line_id: UUID = field(default_factory=uuid4)
    source_type: str = "inventory"  # inventory/purchase_order/transfer/substitute/manual_adjustment
    source_doc_id: UUID | None = None
    source_line_id: UUID | None = None
    allocated_qty: int = 0
    arrived_qty: int = 0
    delivered_qty: int = 0
    status: str = "pending"
    note: str | None = None


@dataclass
class CustomerPickupNotification:
    """客戶取貨通知紀錄。"""
    notification_id: UUID = field(default_factory=uuid4)
    customer_id: UUID = field(default_factory=uuid4)
    sale_id: UUID = field(default_factory=uuid4)
    sale_line_id: UUID | None = None
    channel: str = "manual"  # line/phone/sms/manual
    message_snapshot: str | None = None
    status: str = "sent"  # pending/sent/failed/acknowledged
    sent_by: UUID | None = None
    sent_at: datetime | None = None
    remark: str | None = None
