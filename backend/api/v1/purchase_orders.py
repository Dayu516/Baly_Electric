"""採購單 API — HTTP 轉接層，不含業務邏輯或 SQL。"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from application.procurement import build_po_service
from application.procurement.purchase_order_service import PurchaseOrderService
from core.dependencies import CurrentUser, require_role
from database import get_session
from application.support import build_audit_service

router = APIRouter()


# ── Schemas ─────────────────────────────────────────────

class POLineCreate(BaseModel):
    sku_id: str
    ordered_quantity: int
    unit_cost: float | None = None


class POCreate(BaseModel):
    supplier_id: str
    note: str | None = None
    lines: list[POLineCreate]


class POLineUpdate(BaseModel):
    po_line_id: str
    ordered_quantity: int
    unit_cost: float | None = None


class POUpdate(BaseModel):
    note: str | None = None
    lines: list[POLineUpdate] | None = None
    new_lines: list[POLineCreate] | None = None


class ReceivePOLine(BaseModel):
    po_line_id: str
    received_quantity: int
    unit_cost: float | None = None


class ReceivePORequest(BaseModel):
    lines: list[ReceivePOLine]
    note: str | None = None


# ── Helper ─────────────────────────────────────────────

def _build_service(session: Session) -> PurchaseOrderService:
    return build_po_service(session)


def _to_response(result, *, status_code: int = 200):
    if not result.success:
        code = 404 if result.code == "ERR-BIZ-002" else 400
        raise HTTPException(status_code=code, detail={"code": result.code, "message": result.message})
    return {"success": True, "data": result.data, "message": result.message}


# ── Routes ──────────────────────────────────────────────

@router.get("/")
def list_purchase_orders(
    status_filter: str | None = Query(None, alias="status"),
    supplier_id: str | None = None,
    keyword: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    user: CurrentUser = Depends(require_role(["staff", "manager", "owner"])),
    session: Session = Depends(get_session),
):
    svc = _build_service(session)
    result = svc.list_orders(status=status_filter, supplier_id=supplier_id,
                              keyword=keyword, date_from=date_from, date_to=date_to,
                              page=page, per_page=per_page)
    return _to_response(result)


@router.get("/{po_id}")
def get_purchase_order(
    po_id: UUID,
    user: CurrentUser = Depends(require_role(["staff", "manager", "owner"])),
    session: Session = Depends(get_session),
):
    svc = _build_service(session)
    result = svc.get_order(po_id)
    return _to_response(result)


@router.post("/", status_code=status.HTTP_201_CREATED)
def create_purchase_order(
    body: POCreate,
    user: CurrentUser = Depends(require_role(["manager", "owner"])),
    session: Session = Depends(get_session),
):
    svc = _build_service(session)
    lines = [l.model_dump() for l in body.lines]
    result = svc.create_order(body.supplier_id, body.note, lines)
    if result.success:
        build_audit_service(session).log(user.user_id, "create_po", "purchase_order", detail=result.data)
        session.commit()
    return _to_response(result, status_code=201)


@router.put("/{po_id}")
def update_purchase_order(
    po_id: UUID,
    body: POUpdate,
    user: CurrentUser = Depends(require_role(["manager", "owner"])),
    session: Session = Depends(get_session),
):
    svc = _build_service(session)
    lines = [l.model_dump() for l in body.lines] if body.lines else None
    new_lines = [l.model_dump() for l in body.new_lines] if body.new_lines else None
    result = svc.update_order(po_id, body.note, lines, new_lines)
    if result.success:
        build_audit_service(session).log(user.user_id, "update_po", "purchase_order", entity_id=po_id, detail=result.data)
        session.commit()
    return _to_response(result)


@router.post("/{po_id}/confirm")
def confirm_purchase_order(
    po_id: UUID,
    user: CurrentUser = Depends(require_role(["manager", "owner"])),
    session: Session = Depends(get_session),
):
    svc = _build_service(session)
    result = svc.confirm_order(po_id)
    if result.success:
        build_audit_service(session).log(user.user_id, "confirm_po", "purchase_order", entity_id=po_id, detail=result.data)
        session.commit()
    return _to_response(result)


@router.post("/{po_id}/cancel")
def cancel_purchase_order(
    po_id: UUID,
    user: CurrentUser = Depends(require_role(["manager", "owner"])),
    session: Session = Depends(get_session),
):
    svc = _build_service(session)
    result = svc.cancel_order(po_id)
    if result.success:
        build_audit_service(session).log(user.user_id, "cancel_po", "purchase_order", entity_id=po_id, detail=result.data)
        session.commit()
    return _to_response(result)


@router.post("/{po_id}/receive")
def receive_purchase_order(
    po_id: UUID,
    body: ReceivePORequest,
    user: CurrentUser = Depends(require_role(["manager", "owner"])),
    session: Session = Depends(get_session),
):
    svc = _build_service(session)
    lines = [l.model_dump() for l in body.lines]
    result = svc.receive_order(po_id, lines, body.note, user.user_id)
    if result.success:
        build_audit_service(session).log(
            user.user_id, "receive_po", "purchase_order", entity_id=po_id,
            detail=result.data,
        )
        session.commit()
    return _to_response(result)


@router.delete("/{po_id}")
def delete_purchase_order(
    po_id: UUID,
    user: CurrentUser = Depends(require_role(["manager", "owner"])),
    session: Session = Depends(get_session),
):
    svc = _build_service(session)
    result = svc.delete_order(po_id)
    if result.success:
        build_audit_service(session).log(user.user_id, "delete_po", "purchase_order", entity_id=po_id, detail=result.data)
        session.commit()
    return _to_response(result)
