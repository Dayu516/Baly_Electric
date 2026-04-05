"""User repository 介面 — ABC。"""

from abc import ABC, abstractmethod
from typing import Optional
from uuid import UUID

from domain.user.models import User


class UserRepository(ABC):
    @abstractmethod
    def get_by_id(self, user_id: UUID) -> Optional[User]:
        ...

    @abstractmethod
    def get_by_username(self, username: str) -> Optional[User]:
        ...

    @abstractmethod
    def save(self, user: User) -> User:
        ...

    @abstractmethod
    def list_all(self) -> list[User]:
        ...
