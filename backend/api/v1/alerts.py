"""通知中心 API routes。"""

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from core.dependencies import CurrentUser, require_role
from database import get_session
from application.support import build_alert_repository, build_audit_service

router = APIRouter()


@router.get("/")
def list_alerts(
    session: Session = Depends(get_session),
    _user: CurrentUser = Depends(require_role(["staff", "manager", "owner"])),
):
    repo = build_alert_repository(session)
    alerts = repo.list_unread()
    return {"success": True, "data": [a.__dict__ for a in alerts]}


@router.post("/{alert_id}/read")
def mark_read(
    alert_id: UUID,
    session: Session = Depends(get_session),
    _user: CurrentUser = Depends(require_role(["staff", "manager", "owner"])),
):
    repo = build_alert_repository(session)
    repo.mark_read(alert_id)
    build_audit_service(session).log(_user.user_id, "mark_alert_read", "alert", entity_id=alert_id)
    session.commit()
    return {"success": True, "message": "已標記已讀"}