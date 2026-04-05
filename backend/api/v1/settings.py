"""系統設定 API — 公司資料 + 系統參數。"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.dependencies import CurrentUser, require_role
from database import get_session
from application.support import build_audit_service, build_settings_repository
from domain.settings.models import CompanyInfo, SystemParameter

router = APIRouter()


# ── Schemas ─────────────────────────────────────────────

class CompanyInfoResponse(BaseModel):
    name: str
    short_name: str | None = None
    tax_id: str | None = None
    phone: str | None = None
    fax: str | None = None
    address: str | None = None
    owner_name: str | None = None
    note: str | None = None
    updated_at: str | None = None


class CompanyInfoUpdate(BaseModel):
    name: str
    short_name: str | None = None
    tax_id: str | None = None
    phone: str | None = None
    fax: str | None = None
    address: str | None = None
    owner_name: str | None = None
    note: str | None = None


class ParameterResponse(BaseModel):
    key: str
    value: str
    description: str | None = None


class ParameterUpdate(BaseModel):
    value: str


# ── Routes ──────────────────────────────────────────────

@router.get("/company")
def get_company_info(
    user: CurrentUser = Depends(require_role(["staff", "manager", "owner"])),
    session: Session = Depends(get_session),
):
    repo = build_settings_repository(session)
    info = repo.get_company_info()
    return {
        "success": True,
        "data": CompanyInfoResponse(
            name=info.name,
            short_name=info.short_name,
            tax_id=info.tax_id,
            phone=info.phone,
            fax=info.fax,
            address=info.address,
            owner_name=info.owner_name,
            note=info.note,
            updated_at=info.updated_at.isoformat() if info.updated_at else None,
        ).model_dump(),
    }


@router.put("/company")
def update_company_info(
    body: CompanyInfoUpdate,
    user: CurrentUser = Depends(require_role(["owner"])),
    session: Session = Depends(get_session),
):
    repo = build_settings_repository(session)
    info = CompanyInfo(
        name=body.name,
        short_name=body.short_name,
        tax_id=body.tax_id,
        phone=body.phone,
        fax=body.fax,
        address=body.address,
        owner_name=body.owner_name,
        note=body.note,
    )
    saved = repo.save_company_info(info)
    build_audit_service(session).log(user.user_id, "update_company_info", "settings")
    session.commit()
    return {"success": True, "message": "公司資料已更新"}


@router.get("/parameters")
def get_parameters(
    user: CurrentUser = Depends(require_role(["staff", "manager", "owner"])),
    session: Session = Depends(get_session),
):
    repo = build_settings_repository(session)
    params = repo.get_all_parameters()
    return {
        "success": True,
        "data": [
            ParameterResponse(key=p.key, value=p.value, description=p.description).model_dump()
            for p in params
        ],
    }


@router.put("/parameters/{key}")
def update_parameter(
    key: str,
    body: ParameterUpdate,
    user: CurrentUser = Depends(require_role(["owner"])),
    session: Session = Depends(get_session),
):
    repo = build_settings_repository(session)
    existing = repo.get_parameter(key)
    if not existing:
        from fastapi import HTTPException, status
        from core.errors import ERR_BIZ_002
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": ERR_BIZ_002, "message": f"參數 '{key}' 不存在"},
        )
    param = SystemParameter(key=key, value=body.value, description=existing.description)
    repo.save_parameter(param)
    build_audit_service(session).log(user.user_id, "update_parameter", "settings")
    session.commit()
    return {"success": True, "message": f"參數 '{key}' 已更新"}
