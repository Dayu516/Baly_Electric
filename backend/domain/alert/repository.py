from abc import ABC, abstractmethod
from uuid import UUID

from domain.alert.models import OperationalAlert


class OperationalAlertRepository(ABC):
    @abstractmethod
    def save(self, alert: OperationalAlert) -> OperationalAlert: ...

    @abstractmethod
    def list_unread(self) -> list[OperationalAlert]: ...

    @abstractmethod
    def mark_read(self, alert_id: UUID) -> None: ...

    @abstractmethod
    def list_active_by_reference(self, reference_type: str, reference_id: UUID, alert_type: str) -> list[OperationalAlert]:
        """查詢未讀的 active alert（同 reference + type）。"""
        ...
