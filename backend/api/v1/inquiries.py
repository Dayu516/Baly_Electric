"""詢價單 API — HTTP 轉接層，不含業務邏輯或 SQL。"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from application.procurement import build_inquiry_service
from application.procurement.inquiry_service import InquiryService
from application.support import build_audit_service
from core.dependencies import CurrentUser, require_role
from database import get_session

router = APIRouter()


# ── Schemas ─────────────────────────────────────────────

class InquiryLineCreate(BaseModel):
    sku_id: str
    quantity: int
    note: str | None = None


class InquiryCreate(BaseModel):
    title: str
    note: str | None = None
    lines: list[InquiryLineCreate] = []


class QuoteCreate(BaseModel):
    line_id: str
    supplier_id: str
    unit_price: float
    note: str | None = None


class SelectQuotes(BaseModel):
    quote_ids: list[str]


# ── Helper ─────────────────────────────────────────────

def _build_service(session: Session) -> InquiryService:
    return build_inquiry_service(session)


def _to_response(result, *, status_code: int = 200):
    if not result.success:
        code = 404 if result.code == "ERR-BIZ-002" else 400
        raise HTTPException(status_code=code, detail={"code": result.code, "message": result.message})
    return {"success": True, "data": result.data, "message": result.message}


# ── Routes ──────────────────────────────────────────────

@router.get("/")
def list_inquiries(
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
    result = svc.list_inquiries(status=status_filter, keyword=keyword,
                                 date_from=date_from, date_to=date_to,
                                 page=page, per_page=per_page)
    return _to_response(result)


@router.get("/{inquiry_id}")
def get_inquiry(
    inquiry_id: UUID,
    user: CurrentUser = Depends(require_role(["staff", "manager", "owner"])),
    session: Session = Depends(get_session),
):
    svc = _build_service(session)
    result = svc.get_inquiry(inquiry_id)
    return _to_response(result)


@router.post("/", status_code=status.HTTP_201_CREATED)
def create_inquiry(
    body: InquiryCreate,
    user: CurrentUser = Depends(require_role(["manager", "owner"])),
    session: Session = Depends(get_session),
):
    svc = _build_service(session)
    lines = [l.model_dump() for l in body.lines]
    result = svc.create_inquiry(body.title, body.note, lines, user.user_id)
    if result.success:
        build_audit_service(session).log(user.user_id, "create_inquiry", "inquiry", detail=result.data)
        session.commit()
    return _to_response(result, status_code=201)


@router.post("/{inquiry_id}/lines")
def add_inquiry_line(
    inquiry_id: UUID,
    body: InquiryLineCreate,
    user: CurrentUser = Depends(require_role(["manager", "owner"])),
    session: Session = Depends(get_session),
):
    svc = _build_service(session)
    result = svc.add_line(inquiry_id, body.sku_id, body.quantity, body.note)
    if result.success:
        build_audit_service(session).log(user.user_id, "add_inquiry_line", "inquiry", entity_id=inquiry_id, detail=result.data)
        session.commit()
    return _to_response(result)


@router.post("/{inquiry_id}/quotes")
def add_quote(
    inquiry_id: UUID,
    body: QuoteCreate,
    user: CurrentUser = Depends(require_role(["manager", "owner"])),
    session: Session = Depends(get_session),
):
    svc = _build_service(session)
    result = svc.add_quote(inquiry_id, body.line_id, body.supplier_id, body.unit_price, body.note, user.user_id)
    if result.success:
        build_audit_service(session).log(user.user_id, "add_inquiry_quote", "inquiry", entity_id=inquiry_id, detail=result.data)
        session.commit()
    return _to_response(result)


@router.post("/{inquiry_id}/select")
def select_quotes(
    inquiry_id: UUID,
    body: SelectQuotes,
    user: CurrentUser = Depends(require_role(["manager", "owner"])),
    session: Session = Depends(get_session),
):
    svc = _build_service(session)
    result = svc.select_quotes(inquiry_id, body.quote_ids)
    if result.success:
        build_audit_service(session).log(user.user_id, "select_inquiry_quotes", "inquiry", entity_id=inquiry_id, detail=result.data)
        session.commit()
    return _to_response(result)


@router.post("/{inquiry_id}/convert")
def convert_to_po(
    inquiry_id: UUID,
    user: CurrentUser = Depends(require_role(["manager", "owner"])),
    session: Session = Depends(get_session),
):
    svc = _build_service(session)
    result = svc.convert_to_po(inquiry_id)
    if result.success:
        build_audit_service(session).log(user.user_id, "convert_inquiry_to_po", "inquiry", entity_id=inquiry_id, detail=result.data)
        session.commit()
    return _to_response(result)


@router.post("/{inquiry_id}/cancel")
def cancel_inquiry(
    inquiry_id: UUID,
    user: CurrentUser = Depends(require_role(["manager", "owner"])),
    session: Session = Depends(get_session),
):
    svc = _build_service(session)
    result = svc.cancel_inquiry(inquiry_id)
    if result.success:
        build_audit_service(session).log(user.user_id, "cancel_inquiry", "inquiry", entity_id=inquiry_id, detail=result.data)
        session.commit()
    return _to_response(result)


@router.delete("/{inquiry_id}")
def delete_inquiry(
    inquiry_id: UUID,
    user: CurrentUser = Depends(require_role(["owner"])),
    session: Session = Depends(get_session),
):
    svc = _build_service(session)
    result = svc.delete_inquiry(inquiry_id)
    if result.success:
        build_audit_service(session).log(user.user_id, "delete_inquiry", "inquiry", entity_id=inquiry_id, detail=result.data)
        session.commit()
    return _to_response(result)
