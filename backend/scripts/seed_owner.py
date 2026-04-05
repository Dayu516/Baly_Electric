"""建立初始 Owner 帳號。

Usage:
    cd backend
    python -m scripts.seed_owner
"""

import sys
from pathlib import Path

# 確保 backend 在 sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy.orm import Session

from config import settings  # noqa: E402
from core.security import hash_password  # noqa: E402
from database import SessionLocal  # noqa: E402
from infrastructure.persistence.orm_models import UserORM  # noqa: E402


def seed_owner():
    session: Session = SessionLocal()
    try:
        existing = session.query(UserORM).filter(UserORM.username == "owner").first()
        if existing:
            print("Owner 帳號已存在，跳過。")
            return

        owner = UserORM(
            username="owner",
            display_name="老闆",
            role="owner",
            password_hash=hash_password("changeme"),
            is_active=True,
        )
        session.add(owner)
        session.commit()
        print(f"Owner 帳號建立成功: username=owner, user_id={owner.user_id}")
        print("請立即修改預設密碼！")
    finally:
        session.close()


if __name__ == "__main__":
    seed_owner()
