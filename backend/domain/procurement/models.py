"""Procurement domain models."""

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4


@dataclass
class Supplier:
    supplier_id: UUID = field(default_factory=uuid4)
    name: str = ""
    contact_name: str | None = None
    phone: str | None = None
    address: str | None = None
    note: str | None = None
    is_active: bool = True
    version: int = 1


@dataclass
class PurchaseOrder:
    po_id: UUID = field(default_factory=uuid4)
    supplier_id: UUID = field(default_factory=uuid4)
    status: str = "draft"  # draft/ordered/partial_received/received/cancelled
    note: str | None = None
    ordered_at: datetime | None = None


@dataclass
class PurchaseOrderLine:
    po_line_id: UUID = field(default_factory=uuid4)
    po_id: UUID = field(default_factory=uuid4)
    sku_id: UUID = field(default_factory=uuid4)
    ordered_quantity: int = 0
    received_quantity: int = 0
    unit_cost: float | None = None


@dataclass
class SupplierPriceQuote:
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
class PurchaseInquiry:
    inquiry_id: UUID = field(default_factory=uuid4)
    title: str = ""
    status: str = "draft"  # draft/quoting/decided/converted/cancelled
    note: str | None = None
    created_by: UUID | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass
class PurchaseInquiryLine:
    line_id: UUID = field(default_factory=uuid4)
    inquiry_id: UUID = field(default_factory=uuid4)
    sku_id: UUID = field(default_factory=uuid4)
    quantity: int = 0
    note: str | None = None


@dataclass
class PurchaseInquiryQuote:
    quote_id: UUID = field(default_factory=uuid4)
    inquiry_id: UUID = field(default_factory=uuid4)
    line_id: UUID = field(default_factory=uuid4)
    supplier_id: UUID = field(default_factory=uuid4)
    unit_price: float = 0
    note: str | None = None
    is_selected: bool = False
    created_at: datetime | None = None


@dataclass
class SalesQuotation:
    quotation_id: UUID = field(default_factory=uuid4)
    customer_id: UUID | None = None
    title: str = ""
    status: str = "draft"  # draft/sent/accepted/converted/cancelled
    valid_until: datetime | None = None
    note: str | None = None
    created_by: UUID | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass
class SalesQuotationLine:
    line_id: UUID = field(default_factory=uuid4)
    quotation_id: UUID = field(default_factory=uuid4)
    sku_id: UUID = field(default_factory=uuid4)
    quantity: int = 0
    unit_price: float = 0
    note: str | None = None


@dataclass
class PurchaseReceipt:
    receipt_id: UUID = field(default_factory=uuid4)
    po_id: UUID | None = None
    supplier_id: UUID = field(default_factory=uuid4)
    received_by: UUID = field(default_factory=uuid4)
    note: str | None = None


@dataclass
class PurchaseReceiptLine:
    receipt_line_id: UUID = field(default_factory=uuid4)
    receipt_id: UUID = field(default_factory=uuid4)
    sku_id: UUID = field(default_factory=uuid4)
    quantity: int = 0
    unit_cost: float | None = None
