"""客戶 + 月結 API routes。"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from application.customer import build_generate_statement_service, build_payment_service
from core.dependencies import CurrentUser, require_role
from core.errors import ERR_BIZ_002, ERR_BIZ_004
from database import get_session
from domain.customer.models import Customer
from application.customer import build_customer_repository
from application.support import build_audit_service

router = APIRouter()


# ── Schemas ──────────────────────────────────────────
class CustomerCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    short_name: str | None = None
    tax_id: str | None = None
    customer_type: str = "general"
    customer_code: str | None = None
    phone: str | None = None
    contact_person: str | None = None
    mobile: str | None = None
    email: str | None = None
    line_id: str | None = None
    address: str | None = None
    shipping_address: str | None = None
    payment_terms: str = "cash"
    payment_days: int | None = None
    price_level: str = "retail"
    credit_limit: float | None = None
    discount_rate: float | None = None
    allow_debt: bool = True
    invoice_type: str | None = None
    invoice_title: str | None = None
    invoice_address: str | None = None
    invoice_delivery: str | None = None
    sales_rep: str | None = None
    source: str | None = None
    customer_level: str | None = None
    cooperation_status: str = "active"
    tags: str | None = None
    note: str | None = None


class CustomerUpdate(BaseModel):
    name: str | None = None
    short_name: str | None = None
    tax_id: str | None = None
    customer_type: str | None = None
    customer_code: str | None = None
    phone: str | None = None
    contact_person: str | None = None
    mobile: str | None = None
    email: str | None = None
    line_id: str | None = None
    address: str | None = None
    shipping_address: str | None = None
    payment_terms: str | None = None
    payment_days: int | None = None
    price_level: str | None = None
    credit_limit: float | None = None
    discount_rate: float | None = None
    allow_debt: bool | None = None
    invoice_type: str | None = None
    invoice_title: str | None = None
    invoice_address: str | None = None
    invoice_delivery: str | None = None
    sales_rep: str | None = None
    source: str | None = None
    customer_level: str | None = None
    cooperation_status: str | None = None
    tags: str | None = None
    note: str | None = None
    version: int


class GenerateStatementRequest(BaseModel):
    customer_id: UUID
    period: str = Field(..., pattern=r"^\d{4}-\d{2}$")


class PaymentRequest(BaseModel):
    amount: float = Field(..., gt=0)
    note: str | None = None


# ── Customer Routes ──────────────────────────────────
@router.get("/")
def list_customers(
    page: int = 1, per_page: int = 20,
    session: Session = Depends(get_session),
    _user: CurrentUser = Depends(require_role(["staff", "manager", "owner"])),
):
    repo = build_customer_repository(session)
    customers = repo.list_all(offset=(page - 1) * per_page, limit=per_page)
    return {"success": True, "data": [c.__dict__ for c in customers]}


@router.get("/{customer_id}")
def get_customer(
    customer_id: UUID,
    session: Session = Depends(get_session),
    _user: CurrentUser = Depends(require_role(["staff", "manager", "owner"])),
):
    repo = build_customer_repository(session)
    customer = repo.get_by_id(customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail={"code": ERR_BIZ_002, "message": "客戶不存在"})
    return {"success": True, "data": customer.__dict__}


@router.post("/", status_code=status.HTTP_201_CREATED)
def create_customer(
    body: CustomerCreate,
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(require_role(["manager", "owner"])),
):
    repo = build_customer_repository(session)
    data = body.model_dump(exclude_unset=False)
    customer = Customer(**data)
    saved = repo.save(customer)
    build_audit_service(session).log(user.user_id, "create_customer", "customer", saved.customer_id)
    session.commit()
    return {"success": True, "data": saved.__dict__}


@router.put("/{customer_id}")
def update_customer(
    customer_id: UUID, body: CustomerUpdate,
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(require_role(["manager", "owner"])),
):
    repo = build_customer_repository(session)
    existing = repo.get_by_id(customer_id)
    if not existing:
        raise HTTPException(status_code=404, detail={"code": ERR_BIZ_002, "message": "客戶不存在"})
    if existing.version != body.version:
        raise HTTPException(status_code=409, detail={"code": ERR_BIZ_004, "message": "資料已被他人修改"})

    updates = body.model_dump(exclude_unset=True, exclude={"version"})
    for field, value in updates.items():
        setattr(existing, field, value)
    existing.version += 1

    saved = repo.save(existing)
    build_audit_service(session).log(user.user_id, "update_customer", "customer", customer_id)
    session.commit()
    return {"success": True, "data": saved.__dict__}


# ── Accounts Receivable Routes ───────────────────────
@router.get("/{customer_id}/accounts-receivable")
def list_ar(
    customer_id: UUID,
    session: Session = Depends(get_session),
    _user: CurrentUser = Depends(require_role(["manager", "owner"])),
):
    """查詢某客戶的所有應收帳款。"""
    from application.sales import build_sales_query_service
    qs = build_sales_query_service(session)
    rows = qs.list_accounts_receivable(str(customer_id))
    return {"success": True, "data": rows}


@router.post("/accounts-receivable/generate")
def generate_statement(
    body: GenerateStatementRequest,
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(require_role(["manager", "owner"])),
):
    service = build_generate_statement_service(session)
    result = service.generate(body.customer_id, body.period, generated_by=user.user_id)

    if not result.success:
        raise HTTPException(status_code=400, detail={"code": result.code, "message": result.message})

    build_audit_service(session).log(user.user_id, "generate_statement", "accounts_receivable", detail=result.data)
    session.commit()
    return {"success": True, "code": "OK", "message": result.message, "data": result.data}


@router.post("/accounts-receivable/{ar_id}/payment")
def record_payment(
    ar_id: UUID, body: PaymentRequest,
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(require_role(["manager", "owner"])),
):
    service = build_payment_service(session)
    result = service.record_payment(ar_id, body.amount)

    if not result.success:
        raise HTTPException(status_code=404, detail={"code": result.code, "message": result.message})

    build_audit_service(session).log(
        user.user_id, "record_payment", "accounts_receivable", entity_id=ar_id,
        detail={"amount": body.amount, "new_paid": result.data["paid_amount"]},
    )
    session.commit()
    return {"success": True, "message": result.message}
