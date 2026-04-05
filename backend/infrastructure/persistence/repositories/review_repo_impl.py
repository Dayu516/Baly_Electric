"""ReviewTask repository 實作。"""

from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from domain.review.models import ReviewTask
from domain.review.repository import ReviewTaskRepository
from infrastructure.persistence.orm_models import ReviewTaskORM


class SqlReviewTaskRepository(ReviewTaskRepository):
    def __init__(self, session: Session):
        self._session = session

    def get_by_id(self, task_id: UUID) -> Optional[ReviewTask]:
        orm = self._session.get(ReviewTaskORM, task_id)
        return self._to_domain(orm) if orm else None

    def save(self, task: ReviewTask) -> ReviewTask:
        existing = self._session.get(ReviewTaskORM, task.task_id)
        if existing:
            existing.status = task.status
            existing.resolution = task.resolution
            existing.title = task.title
            existing.detail = task.detail
            existing.claimed_by = task.claimed_by
            existing.claimed_at = task.claimed_at
            existing.resolved_by = task.resolved_by
            existing.resolved_at = task.resolved_at
            self._session.flush()
            return self._to_domain(existing)

        orm = ReviewTaskORM(
            task_id=task.task_id,
            review_type=task.review_type,
            status=task.status,
            resolution=task.resolution,
            reference_type=task.reference_type,
            reference_id=task.reference_id,
            title=task.title,
            detail=task.detail,
            claimed_by=task.claimed_by,
            claimed_at=task.claimed_at,
            resolved_by=task.resolved_by,
            resolved_at=task.resolved_at,
        )
        self._session.add(orm)
        self._session.flush()
        return self._to_domain(orm)

    def find_by_reference(self, reference_type: str, reference_id: UUID) -> Optional[ReviewTask]:
        orm = (
            self._session.query(ReviewTaskORM)
            .filter(
                ReviewTaskORM.reference_type == reference_type,
                ReviewTaskORM.reference_id == reference_id,
            )
            .order_by(ReviewTaskORM.created_at.desc())
            .first()
        )
        return self._to_domain(orm) if orm else None

    def list_pending(self, review_type: str | None = None) -> list[ReviewTask]:
        q = self._session.query(ReviewTaskORM).filter(ReviewTaskORM.status.in_(["pending", "claimed"]))
        if review_type:
            q = q.filter(ReviewTaskORM.review_type == review_type)
        orms = q.order_by(ReviewTaskORM.created_at.desc()).all()
        return [self._to_domain(o) for o in orms]

    @staticmethod
    def _to_domain(orm: ReviewTaskORM) -> ReviewTask:
        return ReviewTask(
            task_id=orm.task_id,
            review_type=orm.review_type,
            status=orm.status,
            resolution=orm.resolution,
            reference_type=orm.reference_type,
            reference_id=orm.reference_id,
            title=orm.title,
            detail=orm.detail,
            claimed_by=orm.claimed_by,
            claimed_at=orm.claimed_at,
            resolved_by=orm.resolved_by,
            resolved_at=orm.resolved_at,
            created_at=orm.created_at,
        )