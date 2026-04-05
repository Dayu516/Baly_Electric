"""審核待辦 API routes。"""

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.dependencies import CurrentUser, require_role
from core.errors import ERR_BIZ_002
from database import get_session
from application.support import build_audit_service, build_review_task_repository

router = APIRouter()


class ResolveRequest(BaseModel):
    resolution: str  # approved / modified / rejected


class ReviewCreate(BaseModel):
    review_type: str
    title: str
    detail: str | None = None
    reference_type: str | None = None
    reference_id: UUID | None = None


@router.post("/", status_code=201)
def create_review(
    body: ReviewCreate,
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(require_role(["staff", "manager", "owner"])),
):
    """新增 ReviewTask。"""
    from domain.review.models import ReviewTask
    task = ReviewTask(
        review_type=body.review_type,
        title=body.title,
        detail=body.detail,
        reference_type=body.reference_type,
        reference_id=body.reference_id,
    )
    repo = build_review_task_repository(session)
    saved = repo.save(task)
    build_audit_service(session).log(user.user_id, "create_review", "review_task", detail={"task_id": str(saved.task_id)})
    session.commit()
    return {"success": True, "data": {"task_id": str(saved.task_id)}}


@router.get("/")
def list_reviews(
    review_type: str | None = None,
    session: Session = Depends(get_session),
    _user: CurrentUser = Depends(require_role(["staff", "manager", "owner"])),
):
    repo = build_review_task_repository(session)
    tasks = repo.list_pending(review_type=review_type)
    return {"success": True, "data": [t.__dict__ for t in tasks]}


@router.post("/{task_id}/claim")
def claim_review(
    task_id: UUID,
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(require_role(["staff", "manager", "owner"])),
):
    repo = build_review_task_repository(session)
    task = repo.get_by_id(task_id)
    if not task:
        raise HTTPException(status_code=404, detail={"code": ERR_BIZ_002, "message": "審核任務不存在"})

    if task.status != "pending":
        raise HTTPException(status_code=400, detail={"code": "ERR-BIZ-001", "message": "任務已被領取"})

    task.status = "claimed"
    task.claimed_by = user.user_id
    task.claimed_at = datetime.now(timezone.utc)
    repo.save(task)
    build_audit_service(session).log(user.user_id, "claim_review", "review_task", entity_id=task_id)
    session.commit()
    return {"success": True, "message": "已領取"}


@router.post("/{task_id}/resolve")
def resolve_review(
    task_id: UUID, body: ResolveRequest,
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(require_role(["staff", "manager", "owner"])),
):
    repo = build_review_task_repository(session)
    task = repo.get_by_id(task_id)
    if not task:
        raise HTTPException(status_code=404, detail={"code": ERR_BIZ_002, "message": "審核任務不存在"})

    # 權限檢查：monthly_reconcile 需 manager 以上
    if task.review_type == "monthly_reconcile" and user.role == "staff":
        raise HTTPException(status_code=403, detail={"code": "ERR-SEC-001", "message": "Staff 不可處理月結確認"})

    task.status = "completed"
    task.resolution = body.resolution
    task.resolved_by = user.user_id
    task.resolved_at = datetime.now(timezone.utc)
    repo.save(task)

    build_audit_service(session).log(
        user.user_id, "resolve_review", "review_task", entity_id=task_id,
        detail={"resolution": body.resolution, "review_type": task.review_type},
    )
    session.commit()
    return {"success": True, "message": f"審核完成：{body.resolution}"}