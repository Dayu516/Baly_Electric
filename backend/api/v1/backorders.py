"""欠貨待補 API route — 只做 HTTP 轉接。"""

from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from application.sales import build_backorder_service
from application.support import build_audit_service
from core.dependencies import CurrentUser, require_role
from database import get_session

router = APIRouter()


# ── Schemas ──────────────────────────────────────────────

class CreateBackorderRequest(BaseModel):
    sale_line_id: UUID
    delivered_qty: int
    note: str | None = None


class LinkPoRequest(BaseModel):
    sale_line_id: UUID
    po_id: UUID
    po_line_id: UUID | None = None
    allocated_qty: int


class MarkArrivedRequest(BaseModel):
    sale_line_id: UUID
    arrived_qty: int
    po_id: UUID | None = None


class DeliverRequest(BaseModel):
    sale_line_id: UUID
    deliver_qty: int


class NotifyRequest(BaseModel):
    sale_id: UUID
    sale_line_id: UUID | None = None
    channel: str = "manual"
    message: str | None = None
    remark: str | None = None


class CancelRequest(BaseModel):
    sale_line_id: UUID


# ── Endpoints ────────────────────────────────────────────

@router.post("/create")
def create_backorder(
    body: CreateBackorderRequest,
    session: Session = Depends(get_session),
    _user: CurrentUser = Depends(require_role(["staff", "manager", "owner"])),
):
    svc = build_backorder_service(session)
    result = svc.create_backorder(body.sale_line_id, body.delivered_qty, body.note)
    if result.success:
        build_audit_service(session).log(_user.user_id, "create_backorder", "sale_line", entity_id=body.sale_line_id, detail=result.data)
        session.commit()
    return {"success": result.success, "code": result.code, "message": result.message, "data": result.data}


@router.post("/link-po")
def link_to_po(
    body: LinkPoRequest,
    session: Session = Depends(get_session),
    _user: CurrentUser = Depends(require_role(["manager", "owner"])),
):
    svc = build_backorder_service(session)
    result = svc.link_to_po(body.sale_line_id, body.po_id, body.po_line_id, body.allocated_qty)
    if result.success:
        build_audit_service(session).log(_user.user_id, "link_backorder_po", "sale_line", entity_id=body.sale_line_id, detail=result.data)
        session.commit()
    return {"success": result.success, "code": result.code, "message": result.message}


@router.post("/mark-arrived")
def mark_arrived(
    body: MarkArrivedRequest,
    session: Session = Depends(get_session),
    _user: CurrentUser = Depends(require_role(["staff", "manager", "owner"])),
):
    svc = build_backorder_service(session)
    result = svc.mark_arrived(body.sale_line_id, body.arrived_qty, body.po_id)
    if result.success:
        build_audit_service(session).log(_user.user_id, "mark_arrived", "sale_line", entity_id=body.sale_line_id, detail=result.data)
        session.commit()
    return {"success": result.success, "code": result.code, "message": result.message}


@router.post("/deliver")
def deliver_backorder(
    body: DeliverRequest,
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(require_role(["staff", "manager", "owner"])),
):
    svc = build_backorder_service(session)
    result = svc.deliver_backorder(body.sale_line_id, body.deliver_qty, user.user_id)
    if result.success:
        build_audit_service(session).log(user.user_id, "deliver_backorder", "sale_line", entity_id=body.sale_line_id, detail=result.data)
        session.commit()
    return {"success": result.success, "code": result.code, "message": result.message}


@router.post("/notify")
def notify_customer(
    body: NotifyRequest,
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(require_role(["staff", "manager", "owner"])),
):
    svc = build_backorder_service(session)
    result = svc.notify_customer(
        body.sale_id, body.sale_line_id, body.channel, body.message, user.user_id, body.remark,
    )
    if result.success:
        build_audit_service(session).log(user.user_id, "notify_customer", "sale", entity_id=body.sale_id, detail=result.data)
        session.commit()
    return {"success": result.success, "code": result.code, "message": result.message}


@router.post("/cancel")
def cancel_backorder(
    body: CancelRequest,
    session: Session = Depends(get_session),
    _user: CurrentUser = Depends(require_role(["manager", "owner"])),
):
    svc = build_backorder_service(session)
    result = svc.cancel_backorder(body.sale_line_id)
    if result.success:
        build_audit_service(session).log(_user.user_id, "cancel_backorder", "sale_line", entity_id=body.sale_line_id, detail=result.data)
        session.commit()
    return {"success": result.success, "code": result.code, "message": result.message}
