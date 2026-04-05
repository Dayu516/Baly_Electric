"""Inventory domain models."""

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4


@dataclass
class StockMovement:
    movement_id: UUID = field(default_factory=uuid4)
    sku_id: UUID = field(default_factory=uuid4)
    quantity: int = 0  # 正=入庫, 負=出庫
    movement_type: str = ""  # sale/purchase_receive/adjustment/return/initial
    reference_type: str = ""  # sale/purchase_receipt/stock_count/manual/import
    reference_id: UUID | None = None
    note: str | None = None
    created_by: UUID | None = None
    created_at: datetime | None = None


@dataclass
class InventoryBalance:
    sku_id: UUID = field(default_factory=uuid4)
    current_stock: int = 0
    last_recalc_at: datetime | None = None
