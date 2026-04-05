"""Support 模組 — 跨模組輔助 service 的組裝入口。

提供 AuditService、非核心 repo / query service 的 builder，
讓 API 層不需要直接 import infrastructure。
"""

from sqlalchemy.orm import Session

from infrastructure.persistence.query_services.dashboard_query_service import DashboardQueryService
from infrastructure.persistence.repositories.alert_repo_impl import (
    AuditService,
    SqlOperationalAlertRepository,
)
from infrastructure.persistence.repositories.review_repo_impl import SqlReviewTaskRepository
from infrastructure.persistence.repositories.user_repo_impl import SqlUserRepository

# ── re-export AuditService（API 層最常用的跨模組輔助）────
# Usage: from application.support import build_audit_service
#        audit = build_audit_service(session)


def build_audit_service(session: Session) -> AuditService:
    return AuditService(session)


def build_user_repository(session: Session) -> SqlUserRepository:
    return SqlUserRepository(session)


def build_review_task_repository(session: Session) -> SqlReviewTaskRepository:
    return SqlReviewTaskRepository(session)


def build_alert_repository(session: Session) -> SqlOperationalAlertRepository:
    return SqlOperationalAlertRepository(session)


def build_dashboard_query_service(session: Session) -> DashboardQueryService:
    return DashboardQueryService(session)


def build_settings_repository(session: Session):
    from infrastructure.persistence.repositories.settings_repo_impl import SqlSettingsRepository
    return SqlSettingsRepository(session)
