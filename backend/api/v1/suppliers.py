"""供應商 API routes。"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.dependencies import CurrentUser, require_role
from core.errors import ERR_BIZ_002
from database import get_session
from domain.procurement.models import Supplier
from application.procurement import build_procurement_query_service, build_supplier_repository
from application.product import build_product_query_service
from application.support import build_audit_service

router = APIRouter()


class SupplierCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    contact_name: str | None = None
    phone: str | None = None
    address: str | None = None
    note: str | None = None


@router.get("/")
def list_suppliers(
    session: Session = Depends(get_session),
    _user: CurrentUser = Depends(require_role(["staff", "manager", "owner"])),
):
    qs = build_product_query_service(session)
    return {"success": True, "data": qs.list_active_suppliers()}


@router.post("/", status_code=status.HTTP_201_CREATED)
def create_supplier(
    body: SupplierCreate,
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(require_role(["manager", "owner"])),
):
    repo = build_supplier_repository(session)
    supplier = Supplier(
        name=body.name,
        contact_name=body.contact_name,
        phone=body.phone,
        address=body.address,
        note=body.note,
    )
    saved = repo.save(supplier)
    build_audit_service(session).log(user.user_id, "create_supplier", "supplier", detail={"supplier_id": str(saved.supplier_id), "name": saved.name})
    session.commit()
    return {"success": True, "data": {
        "supplier_id": str(saved.supplier_id), "name": saved.name,
    }}


@router.get("/{supplier_id}/history")
def get_supplier_history(
    supplier_id: UUID,
    session: Session = Depends(get_session),
    _user: CurrentUser = Depends(require_role(["staff", "manager", "owner"])),
):
    """供應商歷史交易紀錄（進貨驗收）。"""
    qs = build_procurement_query_service(session)
    summary = qs.supplier_summary(str(supplier_id))
    history = qs.supplier_transaction_history(str(supplier_id))
    return {"success": True, "data": {
        "summary": {
            "total_receipts": int(summary.get("total_receipts") or 0),
            "total_quantity": int(summary.get("total_quantity") or 0),
            "total_amount": float(summary.get("total_amount") or 0),
            "last_receipt_date": str(summary["last_receipt_date"])[:10] if summary.get("last_receipt_date") else None,
        },
        "history": [
            {
                "receipt_id": str(r["receipt_id"]),
                "date": str(r["created_at"])[:10] if r["created_at"] else "",
                "po_note": r["po_note"],
                "line_count": int(r["line_count"]),
                "total_quantity": int(r["total_quantity"]),
                "total_amount": float(r["total_amount"]),
            }
            for r in history
        ],
    }}
