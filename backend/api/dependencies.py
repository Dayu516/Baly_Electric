"""API 層 DI 工廠 — Composition Root 的一部分。

所有 Application Service 的組裝在這裡。
API route 透過 Depends() 取得 service instance。
"""

from fastapi import Depends
from sqlalchemy.orm import Session

from application.support import build_user_repository
from database import get_session


def get_user_repository(session: Session = Depends(get_session)):
    return build_user_repository(session)
