"""POS / 銷售 API routes — 只做 HTTP 轉接。

權限矩陣：
  POST /sales（結帳） — Staff / Manager / Owner
  POST /sales/{id}/void — Manager / Owner
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from application.sales.schemas import CheckoutRequest, CheckoutResponse, VoidSaleRequest
from core.dependencies import CurrentUser, require_role
from database import get_session

router = APIRouter()


@router.post("/", response_model=dict, status_code=status.HTTP_201_CREATED)
def checkout(
    body: CheckoutRequest,
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(require_role(["staff", "manager", "owner"])),
):
    from application.use_cases import build_checkout_use_case
    use_case = build_checkout_use_case(session)
    result = use_case.execute(body, cashier_id=user.user_id)

    if not result.success:
        raise HTTPException(status_code=400, detail={"code": result.code, "message": result.message})

    return {"success": True, "code": "OK", "message": result.message, "data": result.data}


@router.post("/{sale_id}/void")
def void_sale(
    sale_id: UUID,
    body: VoidSaleRequest,
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(require_role(["manager", "owner"])),
):
    from application.use_cases import build_void_sale_use_case
    use_case = build_void_sale_use_case(session)
    result = use_case.execute(sale_id, user_id=user.user_id, reason=body.reason)

    if not result.success:
        raise HTTPException(status_code=400, detail={"code": result.code, "message": result.message})

    return {"success": True, "code": "OK", "message": result.message}
