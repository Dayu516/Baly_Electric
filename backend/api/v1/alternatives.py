"""替代品搜尋 API — 同分類、庫存>0、按屬性匹配度排序。"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from core.dependencies import CurrentUser, require_role
from database import get_session
from application.product import build_product_query_service

router = APIRouter()


@router.get("/{product_id}/alternatives")
def find_alternatives(
    product_id: UUID,
    sku_id: UUID | None = Query(None, description="指定 SKU（預設取第一個）"),
    limit: int = Query(20, ge=1, le=50),
    user: CurrentUser = Depends(require_role(["staff", "manager", "owner"])),
    session: Session = Depends(get_session),
):
    """找替代品：同分類、有庫存、按屬性匹配度排序。"""
    qs = build_product_query_service(session)

    # 如果沒指定 sku_id，用 product 的第一個 SKU
    if not sku_id:
        first = qs.get_first_sku_id(str(product_id))
        if not first:
            return {"success": False, "message": "此品項沒有 SKU"}
        sku_id = first
    result = qs.find_alternatives(str(sku_id), limit=limit)

    if not result["target"]:
        return {"success": False, "message": "品項不存在或未設定分類"}

    return {
        "success": True,
        "data": result,
        "message": f"找到 {len(result['alternatives'])} 個替代品",
    }
