from abc import ABC, abstractmethod
from typing import Optional
from uuid import UUID

from domain.review.models import ReviewTask


class ReviewTaskRepository(ABC):
    @abstractmethod
    def get_by_id(self, task_id: UUID) -> Optional[ReviewTask]: ...

    @abstractmethod
    def save(self, task: ReviewTask) -> ReviewTask: ...

    @abstractmethod
    def list_pending(self, review_type: str | None = None) -> list[ReviewTask]: ...

    @abstractmethod
    def find_by_reference(self, reference_type: str, reference_id: UUID) -> Optional[ReviewTask]: ...
