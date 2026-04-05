"""AuditEvent repository — 稽核紀錄寫入。"""

import json
import uuid
from typing import Any

from sqlalchemy.orm import Session

from infrastructure.persistence.orm_models import AuditEventORM


class AuditService:
    """簡化的 audit 寫入，不走 domain layer（只是 insert）。"""

    def __init__(self, session: Session):
        self._session = session

    def log(
        self,
        user_id: uuid.UUID,
        action: str,
        entity_type: str,
        entity_id: uuid.UUID | None = None,
        detail: dict[str, Any] | None = None,
        ip_address: str | None = None,
    ) -> None:
        event = AuditEventORM(
            event_id=uuid.uuid4(),
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            detail=json.dumps(detail, default=str) if detail else None,
            ip_address=ip_address,
        )
        self._session.add(event)
        # 不 flush — 讓外層 transaction 一起 commit
