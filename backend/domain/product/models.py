"""Product domain models — 純 Python，不依賴外部套件。"""

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4


@dataclass
class Category:
    category_id: UUID = field(default_factory=uuid4)
    name: str = ""
    parent_id: UUID | None = None
    sort_order: int = 0


@dataclass
class Product:
    product_id: UUID = field(default_factory=uuid4)
    name: str = ""                          # 標準化品名（規格概念，不綁品牌）
    raw_name: str | None = None             # 原始品名（凌越匯入保留底）
    series: str | None = None               # 系列（BH、MY2N、SC-N2）
    model_number: str | None = None         # 型號
    category_id: UUID | None = None
    description: str | None = None
    is_active: bool = True
    version: int = 1
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass
class SKU:
    sku_id: UUID = field(default_factory=uuid4)
    product_id: UUID = field(default_factory=uuid4)
    brand: str | None = None                # 品牌（SKU 層級：士林、東元、OMRON）
    barcode: str | None = None
    supplier_code: str | None = None        # 供應商料號
    internal_code: str | None = None        # 內部編號（凌越原始編號）
    spec: str | None = None                 # 規格（2P 20A）
    unit: str = "個"
    sell_price: float = 0
    cost_price: float | None = None
    min_stock: int | None = None
    item_type: str = "finished"  # finished/assembly/accessory/component
    is_active: bool = True
    version: int = 1


@dataclass
class ProductAlias:
    """品項別名 — 口語、客戶叫法、舊系統名稱。"""
    alias_id: UUID = field(default_factory=uuid4)
    product_id: UUID = field(default_factory=uuid4)
    alias: str = ""
    alias_type: str = "common"  # common/customer/supplier/legacy
    created_by: UUID | None = None
    created_at: datetime | None = None


@dataclass
class CustomerProductMapping:
    """客戶專屬對應 — 某客戶講X = 品項Y。"""
    mapping_id: UUID = field(default_factory=uuid4)
    customer_id: UUID = field(default_factory=uuid4)
    keyword: str = ""          # 客戶講的話
    sku_id: UUID = field(default_factory=uuid4)  # 實際對應
    note: str | None = None
    created_by: UUID | None = None
    created_at: datetime | None = None


@dataclass
class SupplierPriceQuote:
    """供應商報價紀錄 — 追蹤每次詢價/報價歷史。"""
    quote_id: UUID = field(default_factory=uuid4)
    supplier_id: UUID = field(default_factory=uuid4)
    sku_id: UUID = field(default_factory=uuid4)
    unit_price: float = 0
    unit: str | None = None
    quoted_at: datetime | None = None
    note: str | None = None
    created_by: UUID | None = None
    created_at: datetime | None = None


@dataclass
class BomChild:
    """BOM 組成件。"""
    child_sku_id: UUID = field(default_factory=uuid4)
    quantity: int = 1
    component_role: str | None = None
    sort_order: int = 0
    note: str | None = None


@dataclass
class CategoryAttributeTemplate:
    """分類屬性模板。"""
    template_id: UUID = field(default_factory=uuid4)
    category_id: UUID = field(default_factory=uuid4)
    attr_key: str = ""
    attr_unit: str | None = None
    is_required: bool = False
    sort_order: int = 0
    attr_options: str | None = None  # JSON string
    match_priority: int | None = None
    match_type: str | None = "prefer"


@dataclass
class ProductAttribute:
    """品項屬性 key-value。"""
    attr_id: UUID = field(default_factory=uuid4)
    product_id: UUID = field(default_factory=uuid4)
    attr_key: str = ""
    attr_value: str = ""
    attr_unit: str | None = None


@dataclass
class SupplierProduct:
    """供應商品項對應 — 供應商的叫法、包裝、成本。"""
    sp_id: UUID = field(default_factory=uuid4)
    supplier_id: UUID = field(default_factory=uuid4)
    sku_id: UUID = field(default_factory=uuid4)
    supplier_product_name: str | None = None
    supplier_product_code: str | None = None
    pack_unit: str | None = None      # 包裝單位
    pack_qty: int | None = None       # 包裝數量
    min_order_qty: int | None = None  # 最小訂購量
    lead_days: int | None = None      # 到貨天數
    unit_cost: float | None = None
    is_preferred: bool = False
    note: str | None = None
