"""ReviewTask domain model."""

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4


@dataclass
class ReviewTask:
    task_id: UUID = field(default_factory=uuid4)
    review_type: str = ""  # product_confirm / stock_discrepancy / monthly_reconcile
    status: str = "pending"  # pending / claimed / completed / rejected
    resolution: str | None = None  # approved / modified / rejected
    reference_type: str | None = None
    reference_id: UUID | None = None
    title: str = ""
    detail: str | None = None
    claimed_by: UUID | None = None
    claimed_at: datetime | None = None
    resolved_by: UUID | None = None
    resolved_at: datetime | None = None
    created_at: datetime | None = None
