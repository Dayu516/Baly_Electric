"""庫存管理 API routes。"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from application.inventory import (
    build_receive_stock_service,
    build_stock_count_service,
    build_stock_recalc_service,
)
from application.inventory.receive_stock_service import ReceiveLineInput
from application.inventory.stock_count_service import CountLineInput
from core.dependencies import CurrentUser, require_role
from database import get_session
from application.inventory import build_inventory_query_service, build_stock_movement_repository
from application.support import build_audit_service

router = APIRouter()


# ── Schemas ──────────────────────────────────────────
class ReceiveLineSchema(BaseModel):
    sku_id: UUID
    quantity: int = Field(..., gt=0)
    unit_cost: float | None = None


class ReceiveRequest(BaseModel):
    supplier_id: UUID
    lines: list[ReceiveLineSchema] = Field(..., min_length=1)
    po_id: UUID | None = None
    note: str | None = None


class CountLineSchema(BaseModel):
    sku_id: UUID
    actual_quantity: int = Field(..., ge=0)


class CountRequest(BaseModel):
    lines: list[CountLineSchema] = Field(..., min_length=1)


class AdjustRequest(BaseModel):
    sku_id: UUID
    actual_quantity: int = Field(..., ge=0)
    note: str | None = None
    review_task_id: UUID | None = None


# ── Routes ───────────────────────────────────────────
@router.get("/")
def get_inventory(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    keyword: str | None = None,
    low_stock_only: bool = False,
    session: Session = Depends(get_session),
    _user: CurrentUser = Depends(require_role(["staff", "manager", "owner"])),
):
    qs = build_inventory_query_service(session)
    offset = (page - 1) * per_page
    rows, total = qs.list_inventory(keyword=keyword, low_stock_only=low_stock_only, offset=offset, limit=per_page)
    return {"success": True, "data": [dict(r) for r in rows], "total": total}


@router.get("/summary")
def get_inventory_summary(
    session: Session = Depends(get_session),
    _user: CurrentUser = Depends(require_role(["staff", "manager", "owner"])),
):
    qs = build_inventory_query_service(session)
    return {"success": True, "data": qs.inventory_summary()}


@router.get("/{sku_id}/movements")
def get_movements(
    sku_id: UUID,
    page: int = 1,
    per_page: int = 50,
    session: Session = Depends(get_session),
    _user: CurrentUser = Depends(require_role(["staff", "manager", "owner"])),
):
    repo = build_stock_movement_repository(session)
    offset = (page - 1) * per_page
    movements = repo.list_by_sku(sku_id, offset=offset, limit=per_page)
    return {"success": True, "data": [m.__dict__ for m in movements]}


@router.post("/receive", status_code=status.HTTP_201_CREATED)
def receive_stock(
    body: ReceiveRequest,
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(require_role(["manager", "owner"])),
):
    service = build_receive_stock_service(session)
    result = service.receive(
        lines=[ReceiveLineInput(sku_id=l.sku_id, quantity=l.quantity, unit_cost=l.unit_cost) for l in body.lines],
        supplier_id=body.supplier_id,
        received_by=user.user_id,
        po_id=body.po_id,
        note=body.note,
    )
    if not result.success:
        raise HTTPException(status_code=400, detail={"code": result.code, "message": result.message})

    build_audit_service(session).log(user.user_id, "receive_stock", "purchase_receipt", detail=result.data)
    session.commit()
    return {"success": True, "code": "OK", "message": result.message, "data": result.data}


@router.post("/count")
def submit_count(
    body: CountRequest,
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(require_role(["staff", "manager", "owner"])),
):
    service = build_stock_count_service(session)
    result = service.submit_count(
        lines=[CountLineInput(sku_id=l.sku_id, actual_quantity=l.actual_quantity) for l in body.lines],
        counted_by=user.user_id,
    )
    build_audit_service(session).log(user.user_id, "stock_count", "inventory", detail=result.data)
    session.commit()
    return {"success": True, "code": "OK", "message": result.message, "data": result.data}


@router.post("/adjust")
def adjust_stock(
    body: AdjustRequest,
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(require_role(["manager", "owner"])),
):
    service = build_stock_count_service(session)
    result = service.adjust(body.sku_id, body.actual_quantity, adjusted_by=user.user_id, note=body.note, review_task_id=body.review_task_id)
    build_audit_service(session).log(user.user_id, "adjust_stock", "inventory", entity_id=body.sku_id)
    session.commit()
    return {"success": True, "code": "OK", "message": result.message, "data": result.data}


@router.post("/recalc")
def recalc_inventory(
    sku_id: UUID,
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(require_role(["owner"])),
):
    service = build_stock_recalc_service(session)
    result = service.recalc(sku_id)
    build_audit_service(session).log(user.user_id, "recalc_inventory", "inventory", entity_id=sku_id)
    session.commit()
    return {"success": True, "code": "OK", "message": result.message, "data": result.data}


@router.post("/recalc-all")
def recalc_all_inventory(
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(require_role(["owner"])),
):
    """重算所有品項庫存。"""
    qs = build_inventory_query_service(session)
    sku_ids = qs.all_inventory_sku_ids()
    service = build_stock_recalc_service(session)
    fixed = 0
    for sid in sku_ids:
        result = service.recalc(sid)
        if result.data and result.data.get("adjusted"):
            fixed += 1
    build_audit_service(session).log(user.user_id, "recalc_all_inventory", "inventory")
    session.commit()
    return {"success": True, "message": f"已重算 {len(sku_ids)} 筆庫存，{fixed} 筆有差異已修正"}
