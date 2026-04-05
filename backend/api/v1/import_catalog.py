"""凌越匯入 API route — 只做 HTTP 轉接。"""

from fastapi import APIRouter, Depends, UploadFile, File
from sqlalchemy.orm import Session

from application.product import build_import_catalog_service
from core.dependencies import CurrentUser, require_role
from database import get_session
from application.support import build_audit_service

router = APIRouter()


@router.post("/")
async def import_catalog(
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(require_role(["manager", "owner"])),
):
    content = await file.read()
    csv_text = content.decode("utf-8-sig")  # 處理 BOM

    service = build_import_catalog_service(session)
    result = service.import_csv(csv_text, created_by=user.user_id)

    if result.success:
        build_audit_service(session).log(
            user.user_id, "import_catalog", "product",
            detail=result.data,
        )
        session.commit()

    return {
        "success": result.success,
        "code": result.code,
        "message": result.message,
        "data": result.data,
    }
