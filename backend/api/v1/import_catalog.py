"""凌越匯入 API route — 只做 HTTP 轉接。"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session

from core.dependencies import CurrentUser, require_role
from database import get_session

router = APIRouter()


@router.post("/")
async def import_catalog(
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(require_role(["manager", "owner"])),
):
    from application.use_cases import build_import_catalog_use_case
    use_case = build_import_catalog_use_case(session)

    content = await file.read()
    csv_text = content.decode("utf-8-sig")

    result = use_case.execute(csv_text, created_by=user.user_id)
    if not result.success:
        raise HTTPException(status_code=400, detail={"code": result.code, "message": result.message})

    return {
        "success": result.success,
        "code": result.code,
        "message": result.message,
        "data": result.data,
    }


@router.post("/deactivate-batch")
def deactivate_import_batch(
    batch_id: UUID,
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(require_role(["owner"])),
):
    from application.use_cases import build_deactivate_import_batch_use_case
    use_case = build_deactivate_import_batch_use_case(session)

    result = use_case.execute(batch_id, user.user_id)
    if not result.success:
        raise HTTPException(status_code=400, detail={"code": result.code, "message": result.message})

    return {"success": True, "data": result.data, "message": result.message}
