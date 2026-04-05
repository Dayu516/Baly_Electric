"""User domain model — 純 Python，不依賴外部套件。"""

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4


@dataclass
class User:
    user_id: UUID = field(default_factory=uuid4)
    username: str = ""
    display_name: str = ""
    role: str = "staff"  # owner / manager / staff
    is_active: bool = True
    password_hash: str = ""
    last_login_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def can_access(self, required_roles: list[str]) -> bool:
        return self.role in required_roles
