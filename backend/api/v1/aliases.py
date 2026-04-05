"""品項別名 API routes。"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from application.product import build_alias_service, build_product_query_service
from application.support import build_audit_service
from core.dependencies import CurrentUser, require_role
from database import get_session

router = APIRouter()


class AliasCreate(BaseModel):
    product_id: UUID
    alias: str = Field(..., min_length=1, max_length=200)
    alias_type: str = "common"  # common / customer / supplier / legacy


class AliasResponse(BaseModel):
    alias_id: UUID
    product_id: UUID
    alias: str
    alias_type: str


@router.get("/{product_id}")
def list_aliases(
    product_id: UUID,
    session: Session = Depends(get_session),
    _user: CurrentUser = Depends(require_role(["staff", "manager", "owner"])),
):
    qs = build_product_query_service(session)
    aliases = qs.list_aliases_by_product(str(product_id))
    return {"success": True, "data": aliases}


@router.post("/{product_id}", status_code=201)
def create_alias(
    product_id: UUID,
    body: AliasCreate,
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(require_role(["manager", "owner"])),
):
    svc = build_alias_service(session)
    result = svc.create_alias(product_id, body.alias, body.alias_type, created_by=user.user_id)
    if not result.success:
        raise HTTPException(status_code=400, detail={"code": result.code, "message": result.message})
    build_audit_service(session).log(user.user_id, "create_alias", "alias", entity_id=product_id, detail=result.data)
    session.commit()
    return {"success": True, "data": result.data}


@router.delete("/{product_id}/{alias_id}", status_code=204)
def delete_alias(
    product_id: UUID,
    alias_id: UUID,
    session: Session = Depends(get_session),
    _user: CurrentUser = Depends(require_role(["manager", "owner"])),
):
    svc = build_alias_service(session)
    result = svc.delete_alias(product_id, alias_id)
    if not result.success:
        raise HTTPException(status_code=404, detail="別名不存在")
    build_audit_service(session).log(_user.user_id, "delete_alias", "alias", entity_id=alias_id)
    session.commit()
