"""Dashboard API — HTTP 轉接層，不含業務邏輯或 SQL。"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from application.procurement import build_po_service
from core.dependencies import CurrentUser, require_role
from database import get_session
from application.support import build_dashboard_query_service

router = APIRouter()


@router.get("/stats")
def get_dashboard_stats(
    user: CurrentUser = Depends(require_role(["staff", "manager", "owner"])),
    session: Session = Depends(get_session),
):
    """首頁摘要數據 — 今日營業額、低庫存、待審核、未讀警示等。"""
    qs = build_dashboard_query_service(session)
    stats = qs.dashboard_stats()
    return {"success": True, "data": stats}


@router.get("/today-sales")
def get_today_sales(
    limit: int = Query(10, ge=1, le=50),
    user: CurrentUser = Depends(require_role(["staff", "manager", "owner"])),
    session: Session = Depends(get_session),
):
    """今日銷售明細。"""
    qs = build_dashboard_query_service(session)
    rows = qs.dashboard_today_sales(limit=limit)
    return {"success": True, "data": [
        {
            "sale_id": str(r["sale_id"]),
            "customer_id": str(r["customer_id"]) if r["customer_id"] else None,
            "customer_name": r["customer_name"],
            "total": float(r["total"]),
            "payment_method": r["payment_method"],
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            "line_count": r["line_count"],
        }
        for r in rows
    ]}


@router.get("/low-stock")
def get_low_stock_items(
    limit: int = Query(20, ge=1, le=100),
    user: CurrentUser = Depends(require_role(["staff", "manager", "owner"])),
    session: Session = Depends(get_session),
):
    """低庫存品項清單。"""
    qs = build_dashboard_query_service(session)
    rows = qs.dashboard_low_stock_items(limit=limit)
    return {"success": True, "data": [
        {
            "sku_id": str(r["sku_id"]),
            "name": r["name"],
            "brand": r["brand"],
            "spec": r["spec"],
            "unit": r["unit"],
            "current_stock": int(r["current_stock"]),
            "min_stock": int(r["min_stock"]),
            "shortage": int(r["shortage"]),
        }
        for r in rows
    ]}


@router.post("/auto-purchase-orders")
def auto_create_purchase_orders(
    user: CurrentUser = Depends(require_role(["manager", "owner"])),
    session: Session = Depends(get_session),
):
    """低庫存一鍵建採購單 — 按首選供應商分組建立草稿 PO。"""
    svc = build_po_service(session)
    result = svc.auto_create_from_low_stock()
    if not result.success:
        raise HTTPException(status_code=400, detail={"code": result.code, "message": result.message})
    session.commit()
    return {"success": True, "data": result.data, "message": result.message}


@router.get("/backorder-worklist")
def get_backorder_worklist(
    status: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    user: CurrentUser = Depends(require_role(["staff", "manager", "owner"])),
    session: Session = Depends(get_session),
):
    """欠貨待補工作台。"""
    qs = build_dashboard_query_service(session)
    rows = qs.backorder_worklist(status_filter=status, limit=limit)
    return {"success": True, "data": rows}
