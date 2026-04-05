"""報表 API — HTTP 轉接層，不含業務邏輯或 SQL。"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from core.dependencies import CurrentUser, require_role
from database import get_session
from application.procurement import build_procurement_query_service

router = APIRouter()


@router.get("/supplier-monthly")
def supplier_monthly_stats(
    period: str = Query(..., description="YYYY-MM"),
    user: CurrentUser = Depends(require_role(["manager", "owner"])),
    session: Session = Depends(get_session),
):
    qs = build_procurement_query_service(session)
    rows = qs.supplier_monthly_stats(period)
    total_amount = sum(float(r["total_amount"] or 0) for r in rows)

    return {
        "success": True,
        "data": {
            "period": period,
            "total_amount": total_amount,
            "suppliers": [
                {
                    "supplier_id": str(r["supplier_id"]),
                    "supplier_name": r["supplier_name"],
                    "phone": r["phone"],
                    "receipt_count": r["receipt_count"],
                    "total_quantity": int(r["total_quantity"] or 0),
                    "total_amount": float(r["total_amount"] or 0),
                }
                for r in rows
            ],
        },
    }
