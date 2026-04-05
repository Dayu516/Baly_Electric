from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.orm import Session

from config import settings
from core.errors import ERR_AUTH_002, ERR_AUTH_003, ERR_SEC_001
from core.security import decode_access_token
from database import get_session

security_scheme = HTTPBearer()

DbSession = Annotated[Session, Depends(get_session)]


class CurrentUser:
    """從 JWT 解析出的當前使用者資訊。"""

    def __init__(self, user_id: UUID, username: str, role: str):
        self.user_id = user_id
        self.username = username
        self.role = role


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
) -> CurrentUser:
    """從 Bearer token 解析當前使用者。"""
    token = credentials.credentials
    try:
        payload = decode_access_token(token, settings.JWT_SECRET_KEY, settings.JWT_ALGORITHM)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": ERR_AUTH_002, "message": "Token 過期或無效"},
        )

    user_id = payload.get("sub")
    username = payload.get("username")
    role = payload.get("role")

    if not user_id or not username or not role:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": ERR_AUTH_003, "message": "Token 資料不完整"},
        )

    return CurrentUser(user_id=UUID(user_id), username=username, role=role)


def require_role(allowed_roles: list[str]):
    """角色權限檢查 dependency。每個 API route 必須使用。"""

    def checker(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": ERR_SEC_001, "message": f"需要角色 {allowed_roles}，目前角色 {user.role}"},
            )
        return user

    return checker
