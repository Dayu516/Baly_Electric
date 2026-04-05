"""OperationalAlert domain model."""

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4


@dataclass
class OperationalAlert:
    alert_id: UUID = field(default_factory=uuid4)
    alert_type: str = ""  # low_stock / overdue / backup_failed / sync_failed / stock_inconsistency
    severity: str = "info"  # info / warning / critical
    title: str = ""
    detail: str | None = None
    reference_type: str | None = None
    reference_id: UUID | None = None
    is_read: bool = False
    expires_at: datetime | None = None
    created_at: datetime | None = None
