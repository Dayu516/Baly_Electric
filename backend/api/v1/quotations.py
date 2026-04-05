"""報價單 API — HTTP 轉接層，不含業務邏輯或 SQL。"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from application.procurement import build_quotation_service
from application.procurement.quotation_service import QuotationService
from core.dependencies import CurrentUser, require_role
from database import get_session
from application.support import build_audit_service

router = APIRouter()


# ── Schemas ─────────────────────────────────────────────

class QuotationLineCreate(BaseModel):
    sku_id: str
    quantity: int
    unit_price: float
    note: str | None = None


class QuotationCreate(BaseModel):
    customer_id: str | None = None
    title: str
    valid_until: str | None = None
    note: str | None = None
    lines: list[QuotationLineCreate] = []


# ── Helper ─────────────────────────────────────────────

def _build_service(session: Session) -> QuotationService:
    return build_quotation_service(session)


def _to_response(result, *, status_code: int = 200):
    if not result.success:
        code = 404 if result.code == "ERR-BIZ-002" else 400
        raise HTTPException(status_code=code, detail={"code": result.code, "message": result.message})
    return {"success": True, "data": result.data, "message": result.message}


# ── Routes ──────────────────────────────────────────────

@router.get("/")
def list_quotations(
    status_filter: str | None = Query(None, alias="status"),
    keyword: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    user: CurrentUser = Depends(require_role(["staff", "manager", "owner"])),
    session: Session = Depends(get_session),
):
    svc = _build_service(session)
    result = svc.list_quotations(status=status_filter, keyword=keyword,
                                  date_from=date_from, date_to=date_to,
                                  page=page, per_page=per_page)
    return _to_response(result)


@router.get("/{quotation_id}")
def get_quotation(
    quotation_id: UUID,
    user: CurrentUser = Depends(require_role(["staff", "manager", "owner"])),
    session: Session = Depends(get_session),
):
    svc = _build_service(session)
    result = svc.get_quotation(quotation_id)
    return _to_response(result)


@router.post("/", status_code=status.HTTP_201_CREATED)
def create_quotation(
    body: QuotationCreate,
    user: CurrentUser = Depends(require_role(["manager", "owner"])),
    session: Session = Depends(get_session),
):
    svc = _build_service(session)
    lines = [l.model_dump() for l in body.lines]
    result = svc.create_quotation(body.customer_id, body.title, body.valid_until, body.note, lines, user.user_id)
    if result.success:
        build_audit_service(session).log(user.user_id, "create_quotation", "quotation", detail=result.data)
        session.commit()
    return _to_response(result, status_code=201)


@router.post("/{quotation_id}/lines")
def add_quotation_line(
    quotation_id: UUID,
    body: QuotationLineCreate,
    user: CurrentUser = Depends(require_role(["manager", "owner"])),
    session: Session = Depends(get_session),
):
    svc = _build_service(session)
    result = svc.add_line(quotation_id, body.sku_id, body.quantity, body.unit_price, body.note)
    if result.success:
        build_audit_service(session).log(user.user_id, "add_quotation_line", "quotation", entity_id=quotation_id, detail=result.data)
        session.commit()
    return _to_response(result)


@router.post("/{quotation_id}/send")
def send_quotation(
    quotation_id: UUID,
    user: CurrentUser = Depends(require_role(["manager", "owner"])),
    session: Session = Depends(get_session),
):
    svc = _build_service(session)
    result = svc.send_quotation(quotation_id)
    if result.success:
        build_audit_service(session).log(user.user_id, "send_quotation", "quotation", entity_id=quotation_id, detail=result.data)
        session.commit()
    return _to_response(result)


@router.post("/{quotation_id}/accept")
def accept_quotation(
    quotation_id: UUID,
    user: CurrentUser = Depends(require_role(["manager", "owner"])),
    session: Session = Depends(get_session),
):
    svc = _build_service(session)
    result = svc.accept_quotation(quotation_id)
    if result.success:
        build_audit_service(session).log(user.user_id, "accept_quotation", "quotation", entity_id=quotation_id, detail=result.data)
        session.commit()
    return _to_response(result)


@router.post("/{quotation_id}/convert")
def convert_to_sale(
    quotation_id: UUID,
    user: CurrentUser = Depends(require_role(["manager", "owner"])),
    session: Session = Depends(get_session),
):
    svc = _build_service(session)
    result = svc.convert_to_sale(quotation_id, user.user_id)
    if result.success:
        build_audit_service(session).log(
            user.user_id, "convert_quotation", "sale",
            entity_id=UUID(result.data["sale_id"]) if result.data else None,
            detail=result.data,
        )
        session.commit()
        # Transaction 外：低庫存 alert（Constitution 1.2）
        if result.data and result.data.get("sku_ids"):
            svc.check_low_stock(result.data["sku_ids"])
    return _to_response(result)


@router.post("/{quotation_id}/cancel")
def cancel_quotation(
    quotation_id: UUID,
    user: CurrentUser = Depends(require_role(["manager", "owner"])),
    session: Session = Depends(get_session),
):
    svc = _build_service(session)
    result = svc.cancel_quotation(quotation_id)
    if result.success:
        build_audit_service(session).log(user.user_id, "cancel_quotation", "quotation", entity_id=quotation_id, detail=result.data)
        session.commit()
    return _to_response(result)


@router.delete("/{quotation_id}")
def delete_quotation(
    quotation_id: UUID,
    user: CurrentUser = Depends(require_role(["owner"])),
    session: Session = Depends(get_session),
):
    svc = _build_service(session)
    result = svc.delete_quotation(quotation_id)
    if result.success:
        build_audit_service(session).log(user.user_id, "delete_quotation", "quotation", entity_id=quotation_id, detail=result.data)
        session.commit()
    return _to_response(result)
