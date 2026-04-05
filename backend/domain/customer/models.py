"""Customer domain models."""

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4


@dataclass
class Customer:
    customer_id: UUID = field(default_factory=uuid4)
    name: str = ""
    short_name: str | None = None
    tax_id: str | None = None
    customer_type: str = "general"  # general/company/dealer/vip/project
    customer_code: str | None = None
    # 聯絡
    phone: str | None = None
    contact_person: str | None = None
    mobile: str | None = None
    email: str | None = None
    line_id: str | None = None
    address: str | None = None
    shipping_address: str | None = None
    # 交易
    payment_terms: str = "cash"  # cash/monthly_credit/transfer/check
    payment_days: int | None = None
    price_level: str = "retail"  # retail/wholesale/dealer/project/vip
    credit_limit: float | None = None
    discount_rate: float | None = None
    allow_debt: bool = True
    invoice_type: str | None = None  # 二聯/三聯/免開
    invoice_title: str | None = None
    invoice_address: str | None = None
    invoice_delivery: str | None = None
    # 業務
    sales_rep: str | None = None
    source: str | None = None
    customer_level: str | None = None  # A/B/C
    cooperation_status: str = "active"  # potential/active/suspended
    tags: str | None = None  # JSON array
    note: str | None = None
    is_active: bool = True
    version: int = 1


@dataclass
class AccountsReceivable:
    ar_id: UUID = field(default_factory=uuid4)
    customer_id: UUID = field(default_factory=uuid4)
    period: str = ""  # YYYY-MM
    total_amount: float = 0
    paid_amount: float = 0
    status: str = "open"  # open/partial_paid/paid/overdue
    due_date: datetime | None = None
    paid_at: datetime | None = None
    note: str | None = None
