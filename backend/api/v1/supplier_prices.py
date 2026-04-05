"""供應商報價追蹤 API — HTTP 轉接層，不含業務邏輯或 SQL。"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from application.product import build_supplier_price_service
from core.dependencies import CurrentUser, require_role
from database import get_session
from application.procurement import build_procurement_query_service

router = APIRouter()


# ── Schemas ─────────────────────────────────────────────

class CreateQuoteRequest(BaseModel):
    supplier_id: str
    sku_id: str
    unit_price: float
    unit: str | None = None
    quoted_at: str | None = None
    note: str | None = None


# ── Routes ──────────────────────────────────────────────

@router.post("/{product_id}/supplier-prices", status_code=status.HTTP_201_CREATED)
def create_quote(
    product_id: UUID,
    body: CreateQuoteRequest,
    user: CurrentUser = Depends(require_role(["manager", "owner"])),
    session: Session = Depends(get_session),
):
    svc = build_supplier_price_service(session)
    result = svc.create_quote(
        product_id=product_id,
        supplier_id=body.supplier_id,
        sku_id=body.sku_id,
        unit_price=body.unit_price,
        user_id=user.user_id,
        unit=body.unit,
        quoted_at=body.quoted_at,
        note=body.note,
    )
    if not result.success:
        raise HTTPException(status_code=404, detail={"code": result.code, "message": result.message})
    session.commit()
    return {"success": True, "data": result.data, "message": result.message}


@router.get("/{product_id}/supplier-prices")
def list_quotes(
    product_id: UUID,
    supplier_id: str | None = None,
    user: CurrentUser = Depends(require_role(["staff", "manager", "owner"])),
    session: Session = Depends(get_session),
):
    qs = build_procurement_query_service(session)
    rows = qs.list_supplier_price_quotes(str(product_id), supplier_id)

    return {
        "success": True,
        "data": [
            {
                "quote_id": str(r["quote_id"]),
                "supplier_id": str(r["supplier_id"]),
                "supplier_name": r["supplier_name"],
                "sku_id": str(r["sku_id"]),
                "sku_spec": r["sku_spec"],
                "unit_price": float(r["unit_price"]),
                "unit": r["unit"],
                "quoted_at": r["quoted_at"].isoformat() if r["quoted_at"] else "",
                "note": r["note"],
            }
            for r in rows
        ],
    }


@router.get("/{product_id}/compare-prices")
def compare_prices(
    product_id: UUID,
    user: CurrentUser = Depends(require_role(["staff", "manager", "owner"])),
    session: Session = Depends(get_session),
):
    qs = build_procurement_query_service(session)
    rows = qs.compare_supplier_prices(str(product_id))

    return {
        "success": True,
        "data": [
            {
                "supplier_id": str(r["supplier_id"]),
                "supplier_name": r["supplier_name"],
                "supplier_phone": r["supplier_phone"],
                "sku_id": str(r["sku_id"]),
                "sku_spec": r["sku_spec"],
                "unit_price": float(r["unit_price"]),
                "unit": r["unit"],
                "quoted_at": r["quoted_at"].isoformat() if r["quoted_at"] else "",
                "note": r["note"],
                "is_preferred": bool(r["is_preferred"]) if r["is_preferred"] is not None else False,
            }
            for r in rows
        ],
    }
