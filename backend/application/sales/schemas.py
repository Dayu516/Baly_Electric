"""POS 結帳 schemas。"""

from uuid import UUID

from pydantic import BaseModel, Field


class CartItem(BaseModel):
    sku_id: UUID
    quantity: int = Field(..., gt=0)
    unit_price: float = Field(..., ge=0)
    discount_amount: float = Field(0, ge=0)
    product_name: str
    spec: str | None = None


class CheckoutRequest(BaseModel):
    customer_id: UUID | None = None
    payment_method: str = "cash"  # cash / transfer / monthly_credit
    tax_mode: str = "none"          # none / included / extra
    items: list[CartItem] = Field(..., min_length=1)
    discount_amount: float = Field(0, ge=0)  # 整單折扣
    note: str | None = None
    client_tx_id: str | None = None  # 離線冪等 ID


class CheckoutResponse(BaseModel):
    sale_id: UUID
    total: float
    status: str
    item_count: int


class VoidSaleRequest(BaseModel):
    reason: str | None = None