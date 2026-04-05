"""POS / 銷售 API routes。

權限矩陣：
  POST /sales（結帳） — Staff / Manager / Owner
  GET /sales — Staff(自己) / Manager / Owner
  POST /sales/{id}/void — Manager / Owner
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from application.sales import build_checkout_service, build_void_sale_service
from application.sales.schemas import CheckoutRequest, CheckoutResponse, VoidSaleRequest
from core.dependencies import CurrentUser, require_role
from database import get_session
from application.support import build_audit_service

router = APIRouter()


@router.post("/", response_model=dict, status_code=status.HTTP_201_CREATED)
def checkout(
    body: CheckoutRequest,
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(require_role(["staff", "manager", "owner"])),
):
    service = build_checkout_service(session)
    result = service.checkout(body, cashier_id=user.user_id)

    if not result.success:
        raise HTTPException(status_code=400, detail={"code": result.code, "message": result.message})

    build_audit_service(session).log(
        user.user_id, "checkout", "sale",
        entity_id=UUID(result.data["sale_id"]) if result.data else None,
        detail=result.data,
    )
    session.commit()

    # Transaction 外：低庫存 alert（Constitution 1.2）
    service.check_low_stock(body.items)

    return {"success": True, "code": "OK", "message": result.message, "data": result.data}


@router.post("/{sale_id}/void")
def void_sale(
    sale_id: UUID,
    body: VoidSaleRequest,
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(require_role(["manager", "owner"])),
):
    service = build_void_sale_service(session)
    result = service.void(sale_id, user_id=user.user_id, reason=body.reason)

    if not result.success:
        raise HTTPException(status_code=400, detail={"code": result.code, "message": result.message})

    build_audit_service(session).log(
        user.user_id, "void_sale", "sale", entity_id=sale_id,
        detail={"reason": body.reason},
    )
    session.commit()

    return {"success": True, "code": "OK", "message": result.message}
