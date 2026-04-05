"""帳號管理 API — 使用者 CRUD + 改密碼 + 重設密碼。"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.dependencies import CurrentUser, require_role, get_current_user
from core.errors import ERR_AUTH_001, ERR_BIZ_002, ERR_BIZ_003, ERR_VAL_001
from core.security import hash_password, verify_password
from database import get_session
from domain.user.models import User
from application.support import build_audit_service, build_user_repository

router = APIRouter()


# ── Schemas ─────────────────────────────────────────────

class UserResponse(BaseModel):
    user_id: str
    username: str
    display_name: str
    role: str
    is_active: bool
    last_login_at: str | None = None
    created_at: str | None = None


class CreateUserRequest(BaseModel):
    username: str
    display_name: str
    password: str
    role: str = "staff"


class UpdateUserRequest(BaseModel):
    display_name: str | None = None
    role: str | None = None
    is_active: bool | None = None


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


class ResetPasswordRequest(BaseModel):
    new_password: str


# ── Routes ──────────────────────────────────────────────

@router.get("/")
def list_users(
    user: CurrentUser = Depends(require_role(["manager", "owner"])),
    session: Session = Depends(get_session),
):
    repo = build_user_repository(session)
    users = repo.list_all()
    return {
        "success": True,
        "data": [_to_response(u).model_dump() for u in users],
    }


@router.post("/", status_code=status.HTTP_201_CREATED)
def create_user(
    body: CreateUserRequest,
    user: CurrentUser = Depends(require_role(["owner"])),
    session: Session = Depends(get_session),
):
    if body.role not in ("staff", "manager", "owner"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": ERR_VAL_001, "message": "角色必須是 staff / manager / owner"},
        )

    repo = build_user_repository(session)

    # 檢查帳號重複
    existing = repo.get_by_username(body.username)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": ERR_BIZ_003, "message": f"帳號 '{body.username}' 已存在"},
        )

    new_user = User(
        username=body.username,
        display_name=body.display_name,
        role=body.role,
        password_hash=hash_password(body.password),
        is_active=True,
    )
    saved = repo.save(new_user)
    build_audit_service(session).log(user.user_id, "create_user", "user", detail={"user_id": str(saved.user_id), "username": saved.username})
    session.commit()
    return {"success": True, "data": _to_response(saved).model_dump(), "message": "帳號已建立"}


@router.put("/{user_id}")
def update_user(
    user_id: UUID,
    body: UpdateUserRequest,
    user: CurrentUser = Depends(require_role(["owner"])),
    session: Session = Depends(get_session),
):
    repo = build_user_repository(session)
    target = repo.get_by_id(user_id)
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": ERR_BIZ_002, "message": "帳號不存在"},
        )

    if body.display_name is not None:
        target.display_name = body.display_name
    if body.role is not None:
        if body.role not in ("staff", "manager", "owner"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": ERR_VAL_001, "message": "角色必須是 staff / manager / owner"},
            )
        target.role = body.role
    if body.is_active is not None:
        target.is_active = body.is_active

    repo.save(target)
    build_audit_service(session).log(user.user_id, "update_user", "user", entity_id=user_id)
    session.commit()
    return {"success": True, "message": "帳號已更新"}


@router.post("/change-password")
def change_password(
    body: ChangePasswordRequest,
    user: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    if len(body.new_password) < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": ERR_VAL_001, "message": "新密碼不能為空"},
        )

    repo = build_user_repository(session)
    db_user = repo.get_by_id(user.user_id)
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": ERR_BIZ_002, "message": "帳號不存在"},
        )

    if not verify_password(body.old_password, db_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": ERR_AUTH_001, "message": "舊密碼錯誤"},
        )

    db_user.password_hash = hash_password(body.new_password)
    repo.save(db_user)
    build_audit_service(session).log(user.user_id, "change_password", "user")
    session.commit()
    return {"success": True, "message": "密碼已更新"}


@router.post("/{user_id}/reset-password")
def reset_password(
    user_id: UUID,
    body: ResetPasswordRequest,
    user: CurrentUser = Depends(require_role(["owner"])),
    session: Session = Depends(get_session),
):
    repo = build_user_repository(session)
    target = repo.get_by_id(user_id)
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": ERR_BIZ_002, "message": "帳號不存在"},
        )

    target.password_hash = hash_password(body.new_password)
    repo.save(target)
    build_audit_service(session).log(user.user_id, "reset_password", "user", entity_id=user_id)
    session.commit()
    return {"success": True, "message": f"已重設 {target.display_name} 的密碼"}


def _to_response(u: User) -> UserResponse:
    return UserResponse(
        user_id=str(u.user_id),
        username=u.username,
        display_name=u.display_name,
        role=u.role,
        is_active=u.is_active,
        last_login_at=u.last_login_at.isoformat() if u.last_login_at else None,
        created_at=u.created_at.isoformat() if u.created_at else None,
    )
