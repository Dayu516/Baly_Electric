"""AuditEvent domain model."""

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4


@dataclass
class AuditEvent:
    event_id: UUID = field(default_factory=uuid4)
    user_id: UUID = field(default_factory=uuid4)
    action: str = ""  # create_product / update_price / void_sale / adjust_stock / login / ...
    entity_type: str = ""
    entity_id: UUID | None = None
    detail: str | None = None  # JSON snapshot
    ip_address: str | None = None
    created_at: datetime | None = None
