"""品項模組的 Pydantic schemas — API 層用。"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


# ── Category ─────────────────────────────────────────
class CategoryCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    parent_id: UUID | None = None
    sort_order: int = 0


class CategoryUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    parent_id: UUID | None = None
    sort_order: int | None = None


class CategoryResponse(BaseModel):
    category_id: UUID
    name: str
    parent_id: UUID | None
    sort_order: int

    model_config = {"from_attributes": True}


# ── Product ──────────────────────────────────────────
class ProductCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    raw_name: str | None = Field(None, max_length=200)
    series: str | None = Field(None, max_length=100)
    model_number: str | None = Field(None, max_length=100)
    category_id: UUID | None = None
    description: str | None = None


class ProductUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    series: str | None = Field(None, max_length=100)
    model_number: str | None = Field(None, max_length=100)
    category_id: UUID | None = None
    description: str | None = None
    version: int  # optimistic lock


class ProductResponse(BaseModel):
    product_id: UUID
    name: str
    raw_name: str | None
    series: str | None
    model_number: str | None
    category_id: UUID | None
    description: str | None
    is_active: bool
    version: int
    created_at: datetime | None
    updated_at: datetime | None

    model_config = {"from_attributes": True}


# ── SKU ──────────────────────────────────────────────
VALID_ITEM_TYPES = {"finished", "assembly", "accessory", "component"}


class SKUCreate(BaseModel):
    product_id: UUID
    brand: str | None = Field(None, max_length=100)
    barcode: str | None = Field(None, max_length=50)
    supplier_code: str | None = Field(None, max_length=50)
    internal_code: str | None = Field(None, max_length=50)
    spec: str | None = Field(None, max_length=200)
    unit: str = Field("個", max_length=20)
    sell_price: float = Field(..., ge=0)
    cost_price: float | None = Field(None, ge=0)
    min_stock: int | None = None
    item_type: str = "finished"


class SKUUpdate(BaseModel):
    brand: str | None = Field(None, max_length=100)
    barcode: str | None = Field(None, max_length=50)
    supplier_code: str | None = Field(None, max_length=50)
    internal_code: str | None = Field(None, max_length=50)
    spec: str | None = Field(None, max_length=200)
    unit: str | None = Field(None, max_length=20)
    sell_price: float | None = Field(None, ge=0)
    cost_price: float | None = Field(None, ge=0)
    min_stock: int | None = None
    item_type: str | None = None
    version: int  # optimistic lock


class SKUResponse(BaseModel):
    sku_id: UUID
    product_id: UUID
    brand: str | None
    barcode: str | None
    supplier_code: str | None
    internal_code: str | None
    spec: str | None
    unit: str
    sell_price: float
    cost_price: float | None
    min_stock: int | None
    item_type: str
    is_active: bool
    version: int

    model_config = {"from_attributes": True}