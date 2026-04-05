"""OperationalAlert repository 實作。"""

from uuid import UUID

from sqlalchemy.orm import Session

from domain.alert.models import OperationalAlert
from domain.alert.repository import OperationalAlertRepository
from infrastructure.persistence.orm_models import OperationalAlertORM


class SqlOperationalAlertRepository(OperationalAlertRepository):
    def __init__(self, session: Session):
        self._session = session

    def save(self, alert: OperationalAlert) -> OperationalAlert:
        orm = OperationalAlertORM(
            alert_id=alert.alert_id,
            alert_type=alert.alert_type,
            severity=alert.severity,
            title=alert.title,
            detail=alert.detail,
            reference_type=alert.reference_type,
            reference_id=alert.reference_id,
            is_read=alert.is_read,
            expires_at=alert.expires_at,
        )
        self._session.add(orm)
        self._session.flush()
        return alert

    def list_unread(self) -> list[OperationalAlert]:
        orms = (
            self._session.query(OperationalAlertORM)
            .filter(OperationalAlertORM.is_read == False)  # noqa: E712
            .order_by(OperationalAlertORM.created_at.desc())
            .limit(100)
            .all()
        )
        return [self._to_domain(o) for o in orms]

    def mark_read(self, alert_id: UUID) -> None:
        orm = self._session.get(OperationalAlertORM, alert_id)
        if orm:
            orm.is_read = True
            self._session.flush()

    @staticmethod
    def _to_domain(orm: OperationalAlertORM) -> OperationalAlert:
        return OperationalAlert(
            alert_id=orm.alert_id,
            alert_type=orm.alert_type,
            severity=orm.severity,
            title=orm.title,
            detail=orm.detail,
            reference_type=orm.reference_type,
            reference_id=orm.reference_id,
            is_read=orm.is_read,
            expires_at=orm.expires_at,
            created_at=orm.created_at,
        )