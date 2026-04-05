from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from domain.user.models import User
from domain.user.repository import UserRepository
from infrastructure.persistence.orm_models import UserORM


class SqlUserRepository(UserRepository):
    def __init__(self, session: Session):
        self._session = session

    def get_by_id(self, user_id: UUID) -> Optional[User]:
        orm = self._session.get(UserORM, user_id)
        return self._to_domain(orm) if orm else None

    def get_by_username(self, username: str) -> Optional[User]:
        orm = self._session.query(UserORM).filter(UserORM.username == username).first()
        return self._to_domain(orm) if orm else None

    def save(self, user: User) -> User:
        existing = self._session.get(UserORM, user.user_id)
        if existing:
            existing.username = user.username
            existing.display_name = user.display_name
            existing.role = user.role
            existing.password_hash = user.password_hash
            existing.is_active = user.is_active
            existing.last_login_at = user.last_login_at
            self._session.flush()
            return self._to_domain(existing)
        else:
            orm = UserORM(
                user_id=user.user_id,
                username=user.username,
                display_name=user.display_name,
                role=user.role,
                password_hash=user.password_hash,
                is_active=user.is_active,
                last_login_at=user.last_login_at,
            )
            self._session.add(orm)
            self._session.flush()
            return self._to_domain(orm)

    def list_all(self) -> list[User]:
        orms = self._session.query(UserORM).order_by(UserORM.username).all()
        return [self._to_domain(o) for o in orms]

    @staticmethod
    def _to_domain(orm: UserORM) -> User:
        return User(
            user_id=orm.user_id,
            username=orm.username,
            display_name=orm.display_name,
            role=orm.role,
            password_hash=orm.password_hash,
            is_active=orm.is_active,
            last_login_at=orm.last_login_at,
            created_at=orm.created_at,
            updated_at=orm.updated_at,
        )
