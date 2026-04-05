from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from config import settings
from core.dependencies import CurrentUser, get_current_user
from core.errors import ERR_AUTH_001
from core.security import create_access_token, verify_password
from database import get_session
from application.support import build_user_repository

router = APIRouter()


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    username: str
    display_name: str
    role: str


class MeResponse(BaseModel):
    user_id: str
    username: str
    display_name: str
    role: str


@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest, session: Session = Depends(get_session)):
    repo = build_user_repository(session)
    user = repo.get_by_username(body.username)

    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": ERR_AUTH_001, "message": "帳號或密碼錯誤"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": ERR_AUTH_001, "message": "帳號已停用"},
        )

    # 更新最後登入時間
    user.last_login_at = datetime.now(timezone.utc)
    repo.save(user)
    session.commit()

    token = create_access_token(
        user_id=user.user_id,
        username=user.username,
        role=user.role,
        secret=settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
        expires_minutes=settings.JWT_EXPIRE_MINUTES,
    )

    return LoginResponse(
        access_token=token,
        user_id=str(user.user_id),
        username=user.username,
        display_name=user.display_name,
        role=user.role,
    )


@router.get("/me", response_model=MeResponse)
def get_me(user: CurrentUser = Depends(get_current_user)):
    return MeResponse(
        user_id=str(user.user_id),
        username=user.username,
        display_name="",  # A0 簡化，A1 可從 DB 查
        role=user.role,
    )
