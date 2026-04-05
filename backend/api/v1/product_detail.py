"""品項詳情 API — HTTP 轉接層，不含業務邏輯或 SQL。"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from application.product import build_bom_service
from core.dependencies import CurrentUser, require_role
from database import get_session
from application.product import build_product_query_service

router = APIRouter()


@router.get("/by-product/{product_id}")
def get_product_detail(
    product_id: UUID,
    session: Session = Depends(get_session),
    _user: CurrentUser = Depends(require_role(["staff", "manager", "owner"])),
):
    """用 product_id 查詳情（找第一個 SKU）。"""
    qs = build_product_query_service(session)
    first_sku = qs.get_first_sku_id(str(product_id))
    if not first_sku:
        return {"success": False, "message": "此品項沒有 SKU"}
    return get_sku_detail(UUID(first_sku), session, _user)


@router.get("/{sku_id}/detail")
def get_sku_detail(
    sku_id: UUID,
    session: Session = Depends(get_session),
    _user: CurrentUser = Depends(require_role(["staff", "manager", "owner"])),
):
    """品項完整資訊 + 各供應商報價。"""
    qs = build_product_query_service(session)

    sku = qs.get_sku_detail(str(sku_id))
    if not sku:
        return {"success": False, "message": "SKU 不存在"}

    suppliers = qs.get_sku_suppliers(str(sku_id))
    aliases = qs.get_product_aliases(str(sku["product_id"]))
    movements = qs.get_recent_movements(str(sku_id))

    return {
        "success": True,
        "data": {
            "sku_id": str(sku["sku_id"]),
            "product_id": str(sku["product_id"]),
            "category_id": str(sku["category_id"]) if sku["category_id"] else None,
            "name": sku["name"],
            "raw_name": sku["raw_name"],
            "brand": sku["brand"],
            "series": sku["series"],
            "model_number": sku["model_number"],
            "spec": sku["spec"],
            "unit": sku["unit"],
            "barcode": sku["barcode"],
            "supplier_code": sku["supplier_code"],
            "internal_code": sku["internal_code"],
            "sell_price": float(sku["sell_price"]),
            "cost_price": float(sku["cost_price"]) if sku["cost_price"] else None,
            "min_stock": sku["min_stock"],
            "item_type": sku["item_type"],
            "current_stock": int(sku["current_stock"]),
            "suppliers": [
                {
                    "supplier_name": s["supplier_name"],
                    "supplier_phone": s["supplier_phone"],
                    "product_name": s["supplier_product_name"],
                    "product_code": s["supplier_product_code"],
                    "unit_cost": float(s["unit_cost"]) if s["unit_cost"] else None,
                    "pack_unit": s["pack_unit"],
                    "pack_qty": s["pack_qty"],
                    "min_order_qty": s["min_order_qty"],
                    "lead_days": s["lead_days"],
                    "is_preferred": s["is_preferred"],
                    "note": s["note"],
                }
                for s in suppliers
            ],
            "aliases": [{"alias": a["alias"], "type": a["alias_type"]} for a in aliases],
            "recent_movements": [
                {
                    "quantity": m["quantity"],
                    "type": m["movement_type"],
                    "note": m["note"],
                    "date": str(m["created_at"])[:10] if m["created_at"] else "",
                }
                for m in movements
            ],
        },
    }


# ── BOM ─────────────────────────────────────────────

class BomChildSchema(BaseModel):
    child_sku_id: str
    quantity: int = 1
    component_role: str | None = None
    sort_order: int = 0
    note: str | None = None


@router.get("/{sku_id}/bom")
def get_bom(
    sku_id: UUID,
    session: Session = Depends(get_session),
    _user: CurrentUser = Depends(require_role(["staff", "manager", "owner"])),
):
    qs = build_product_query_service(session)
    children = qs.get_bom_children(str(sku_id))
    parents = qs.get_bom_parents(str(sku_id))
    hint = qs.get_assembly_hint(str(sku_id))

    return {"success": True, "data": {
        "children": [
            {
                "bom_id": str(c["bom_id"]),
                "child_sku_id": str(c["child_sku_id"]),
                "product_name": c["product_name"],
                "brand": c["brand"],
                "spec": c["spec"],
                "unit": c["unit"],
                "item_type": c["item_type"],
                "quantity": c["quantity"],
                "component_role": c["component_role"],
                "current_stock": int(c["current_stock"]),
            }
            for c in children
        ],
        "parents": [
            {
                "parent_sku_id": str(p["parent_sku_id"]),
                "product_name": p["product_name"],
                "brand": p["brand"],
                "spec": p["spec"],
                "component_role": p["component_role"],
            }
            for p in parents
        ],
        "assembly_hint": hint,
    }}


@router.put("/{sku_id}/bom")
def save_bom(
    sku_id: UUID,
    children: list[BomChildSchema],
    user: CurrentUser = Depends(require_role(["owner"])),
    session: Session = Depends(get_session),
):
    svc = build_bom_service(session)
    result = svc.save_bom(sku_id, [c.model_dump() for c in children])
    if not result.success:
        raise HTTPException(status_code=400, detail={"code": result.code, "message": result.message})
    session.commit()
    return {"success": True, "message": result.message}
