"""銷售紀錄查詢 API — HTTP 轉接層，不含業務邏輯或 SQL。"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from core.dependencies import CurrentUser, require_role
from database import get_session
from application.sales import build_sale_repository, build_sales_query_service

router = APIRouter()


@router.get("/history")
def list_sales_history(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    customer_id: str | None = None,
    period: str | None = None,
    keyword: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    user: CurrentUser = Depends(require_role(["staff", "manager", "owner"])),
    session: Session = Depends(get_session),
):
    qs = build_sales_query_service(session)
    offset = (page - 1) * per_page
    rows, total = qs.list_sales_history(
        customer_id=customer_id, period=period,
        keyword=keyword, date_from=date_from, date_to=date_to,
        offset=offset, limit=per_page,
    )

    return {"success": True, "data": [
        {
            "sale_id": str(r["sale_id"]),
            "customer_id": str(r["customer_id"]) if r["customer_id"] else None,
            "customer_name": r["customer_name"],
            "status": r["status"],
            "payment_method": r["payment_method"],
            "tax_included": r["tax_included"],
            "total": float(r["total"]),
            "note": r["note"],
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            "line_count": r["line_count"],
        }
        for r in rows
    ], "total": total}


@router.get("/history/{sale_id}")
def get_sale_detail(
    sale_id: str,
    user: CurrentUser = Depends(require_role(["staff", "manager", "owner"])),
    session: Session = Depends(get_session),
):
    qs = build_sales_query_service(session)
    sale = qs.get_sale_detail(sale_id)
    if not sale:
        return {"success": False, "message": "交易不存在"}

    lines = qs.get_sale_lines(sale_id)

    return {"success": True, "data": {
        "sale_id": str(sale["sale_id"]),
        "customer_name": sale["customer_name"],
        "status": sale["status"],
        "payment_method": sale["payment_method"],
        "tax_included": sale["tax_included"],
        "subtotal": float(sale["subtotal"]),
        "tax_amount": float(sale["tax_amount"]),
        "total": float(sale["total"]),
        "note": sale["note"],
        "created_at": sale["created_at"].isoformat() if sale["created_at"] else None,
        "lines": [
            {
                "product_name": l["product_name"],
                "spec": l["spec"],
                "quantity": l["quantity"],
                "unit_price": float(l["unit_price"]),
                "line_total": float(l["line_total"]),
            }
            for l in lines
        ],
    }}


@router.delete("/history/{sale_id}")
def delete_sale(
    sale_id: UUID,
    user: CurrentUser = Depends(require_role(["owner"])),
    session: Session = Depends(get_session),
):
    qs = build_sales_query_service(session)
    sale = qs.get_sale_detail(str(sale_id))
    if not sale:
        raise HTTPException(status_code=404, detail="交易不存在")
    if sale["status"] != "voided":
        raise HTTPException(status_code=400, detail={"message": "只有已作廢的交易可以刪除"})
    repo = build_sale_repository(session)
    repo.delete_with_children(sale_id)
    session.commit()
    return {"success": True, "message": "交易紀錄已刪除"}
