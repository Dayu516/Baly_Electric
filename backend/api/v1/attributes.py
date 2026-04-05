"""品項屬性 + 分類屬性模板 API — HTTP 轉接層，不含業務邏輯或 SQL。"""

import json
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from application.product import build_attribute_service
from application.support import build_audit_service
from core.dependencies import CurrentUser, require_role
from database import get_session
from domain.product.models import CategoryAttributeTemplate, ProductAttribute
from application.product import build_attribute_query_service

router = APIRouter()


# ── 分類屬性模板 ─────────────────────────────────────
@router.get("/templates/{category_id}")
def get_category_attributes(
    category_id: UUID,
    session: Session = Depends(get_session),
    _user: CurrentUser = Depends(require_role(["staff", "manager", "owner"])),
):
    qs = build_attribute_query_service(session)
    templates = qs.get_category_templates(str(category_id))

    return {"success": True, "data": [
        {
            "template_id": str(t["template_id"]),
            "key": t["attr_key"], "unit": t["attr_unit"], "required": t["is_required"],
            "options": json.loads(t["attr_options"]) if t["attr_options"] else None,
            "match_priority": t["match_priority"],
            "match_type": t["match_type"],
        }
        for t in templates
    ]}


# ── 品項屬性 ─────────────────────────────────────────
@router.get("/product/{product_id}")
def get_product_attributes(
    product_id: UUID,
    session: Session = Depends(get_session),
    _user: CurrentUser = Depends(require_role(["staff", "manager", "owner"])),
):
    qs = build_attribute_query_service(session)
    attrs = qs.get_product_attributes(str(product_id))

    return {"success": True, "data": [
        {"attr_id": str(a["attr_id"]), "key": a["attr_key"], "value": a["attr_value"], "unit": a["attr_unit"]}
        for a in attrs
    ]}


class TemplateSave(BaseModel):
    key: str
    unit: str | None = None
    required: bool = False
    options: list[str] | None = None
    match_priority: int | None = None
    match_type: str | None = "prefer"


@router.put("/templates/{category_id}")
def save_category_templates(
    category_id: UUID,
    templates: list[TemplateSave],
    session: Session = Depends(get_session),
    _user: CurrentUser = Depends(require_role(["owner"])),
):
    svc = build_attribute_service(session)
    domain_templates = [
        CategoryAttributeTemplate(
            template_id=uuid4(),
            category_id=category_id,
            attr_key=t.key.strip(),
            attr_unit=t.unit,
            is_required=t.required,
            sort_order=i,
            attr_options=json.dumps(t.options, ensure_ascii=False) if t.options else None,
            match_priority=t.match_priority,
            match_type=t.match_type,
        )
        for i, t in enumerate(templates)
        if t.key.strip()
    ]
    count = svc.replace_category_templates(category_id, domain_templates)
    build_audit_service(session).log(_user.user_id, "save_category_templates", "category", entity_id=category_id)
    session.commit()
    return {"success": True, "count": count, "message": f"已儲存 {count} 個屬性欄位"}


class AttrSave(BaseModel):
    key: str
    value: str
    unit: str | None = None


@router.put("/product/{product_id}")
def save_product_attributes(
    product_id: UUID,
    attrs: list[AttrSave],
    session: Session = Depends(get_session),
    _user: CurrentUser = Depends(require_role(["manager", "owner"])),
):
    svc = build_attribute_service(session)
    domain_attrs = [
        ProductAttribute(
            attr_id=uuid4(),
            product_id=product_id,
            attr_key=a.key,
            attr_value=a.value.strip(),
            attr_unit=a.unit,
        )
        for a in attrs
        if a.value.strip()
    ]
    count = svc.replace_product_attributes(product_id, domain_attrs)
    build_audit_service(session).log(_user.user_id, "save_product_attributes", "product", entity_id=product_id)
    session.commit()
    return {"success": True, "count": count}


# ── 全部分類的屬性模板（給清洗系統用）────────────────
@router.get("/templates")
def get_all_category_attributes(
    session: Session = Depends(get_session),
    _user: CurrentUser = Depends(require_role(["staff", "manager", "owner"])),
):
    qs = build_attribute_query_service(session)
    rows = qs.get_all_category_templates()

    result: dict[str, list] = {}
    for r in rows:
        cat_name = r["category_name"]
        if cat_name not in result:
            result[cat_name] = []
        result[cat_name].append({
            "key": r["attr_key"], "unit": r["attr_unit"], "required": r["is_required"],
            "options": json.loads(r["attr_options"]) if r["attr_options"] else None,
            "match_priority": r["match_priority"],
            "match_type": r["match_type"],
        })

    return {"success": True, "data": result}
