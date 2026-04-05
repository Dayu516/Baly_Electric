"""SystemJob domain model."""

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4


@dataclass
class SystemJob:
    job_id: UUID = field(default_factory=uuid4)
    job_type: str = ""  # backup / recalc
    status: str = "running"  # running / completed / failed
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_message: str | None = None
    detail: str | None = None
