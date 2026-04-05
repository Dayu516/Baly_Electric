"""品項搜尋 API route。"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from application.product import build_product_query_service
from application.product.search_service import SearchProductService
from core.dependencies import CurrentUser, require_role
from database import get_session

router = APIRouter()


@router.get("/search")
def search_products(
    q: str = Query(..., min_length=1, description="搜尋關鍵字（型號、品名、條碼）"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    session: Session = Depends(get_session),
    _user: CurrentUser = Depends(require_role(["staff", "manager", "owner"])),
):
    service = SearchProductService(build_product_query_service(session))
    result = service.search(q, page=page, per_page=per_page)

    if not result.success:
        return {"success": False, "code": result.code, "message": result.message, "data": []}

    return {
        "success": True,
        "code": "OK",
        "message": result.message,
        "data": result.data,
    }