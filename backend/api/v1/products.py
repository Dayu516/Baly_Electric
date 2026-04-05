"""品項 CRUD API routes。

權限矩陣：
  GET  — Staff / Manager / Owner
  POST — Manager / Owner
  PUT  — Manager / Owner
  DELETE — Owner only
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from application.product import (
    build_category_service,
    build_search_product_service,
)
from application.product.schemas import (
    CategoryCreate,
    CategoryResponse,
    CategoryUpdate,
    ProductCreate,
    ProductResponse,
    ProductUpdate,
    SKUCreate,
    SKUResponse,
    SKUUpdate,
)
from core.dependencies import CurrentUser, require_role
from core.errors import ERR_BIZ_002, ERR_BIZ_004
from database import get_session
from domain.product.models import Category, Product, SKU
from application.inventory import build_inventory_balance_repository
from application.product import (
    build_category_repository,
    build_product_repository,
    build_sku_repository,
)
from application.support import build_audit_service

router = APIRouter()


# ── Category ─────────────────────────────────────────
@router.get("/categories", response_model=list[CategoryResponse])
def list_categories(
    session: Session = Depends(get_session),
    _user: CurrentUser = Depends(require_role(["staff", "manager", "owner"])),
):
    repo = build_category_repository(session)
    return [CategoryResponse.model_validate(c.__dict__) for c in repo.list_all()]


@router.get("/categories/tree")
def get_category_tree(
    session: Session = Depends(get_session),
    _user: CurrentUser = Depends(require_role(["staff", "manager", "owner"])),
):
    """回傳樹狀分類結構。"""
    repo = build_category_repository(session)
    all_cats = repo.list_all()

    # 建樹
    by_parent: dict[str | None, list] = {}
    for c in all_cats:
        key = str(c.parent_id) if c.parent_id else None
        by_parent.setdefault(key, []).append(c)

    def build(parent_id: str | None) -> list[dict]:
        children = by_parent.get(parent_id, [])
        return [
            {
                "category_id": str(c.category_id),
                "name": c.name,
                "sort_order": c.sort_order,
                "children": build(str(c.category_id)),
            }
            for c in sorted(children, key=lambda x: x.sort_order)
        ]

    return {"success": True, "data": build(None)}


@router.post("/categories", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
def create_category(
    body: CategoryCreate,
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(require_role(["manager", "owner"])),
):
    repo = build_category_repository(session)
    cat = Category(name=body.name, parent_id=body.parent_id, sort_order=body.sort_order)
    saved = repo.save(cat)
    build_audit_service(session).log(user.user_id, "create_category", "category", saved.category_id)
    session.commit()
    return CategoryResponse.model_validate(saved.__dict__)


@router.put("/categories/{category_id}", response_model=CategoryResponse)
def update_category(
    category_id: UUID,
    body: CategoryUpdate,
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(require_role(["manager", "owner"])),
):
    repo = build_category_repository(session)
    existing = repo.get_by_id(category_id)
    if not existing:
        raise HTTPException(status_code=404, detail={"code": ERR_BIZ_002, "message": "分類不存在"})

    if body.name is not None:
        existing.name = body.name
    if body.parent_id is not None:
        existing.parent_id = body.parent_id
    if body.sort_order is not None:
        existing.sort_order = body.sort_order

    saved = repo.save(existing)
    build_audit_service(session).log(user.user_id, "update_category", "category", saved.category_id)
    session.commit()
    return CategoryResponse.model_validate(saved.__dict__)


@router.delete("/categories/{category_id}")
def delete_category(
    category_id: UUID,
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(require_role(["owner"])),
):
    svc = build_category_service(session)
    result = svc.delete_category(category_id)

    if not result.success:
        status_code = 404 if result.code == "ERR-BIZ-002" else 400
        raise HTTPException(status_code=status_code, detail={"code": result.code, "message": result.message})

    build_audit_service(session).log(user.user_id, "delete_category", "category", category_id,
                               detail={"deleted_count": result.data["deleted_count"]})
    session.commit()
    return {"success": True, "message": result.message}


# ── Search（必須在 /{product_id} 之前）────────────────
@router.get("/search")
def search_products(
    q: str = Query(..., min_length=1, description="搜尋關鍵字"),
    customer_id: UUID | None = Query(None, description="客戶 ID（帶出歷史售價）"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    session: Session = Depends(get_session),
    _user: CurrentUser = Depends(require_role(["staff", "manager", "owner"])),
):
    service = build_search_product_service(session)
    result = service.search(q, page=page, per_page=per_page)
    if not result.success:
        return {"success": False, "code": result.code, "message": result.message, "data": []}

    data = result.data

    # 如果有指定客戶，附上歷史售價
    if customer_id and data:
        from application.sales import build_sales_query_service
        sales_qs = build_sales_query_service(session)
        sku_ids = [str(item["sku_id"]) for item in data if item.get("sku_id")]
        price_history = sales_qs.get_customer_prices(str(customer_id), sku_ids)
        for item in data:
            sid = str(item.get("sku_id", ""))
            if sid in price_history:
                item["customer_last_price"] = price_history[sid]["last_price"]
                item["customer_last_cost"] = price_history[sid]["last_cost"]
                item["customer_last_sold_at"] = price_history[sid]["last_sold_at"]

    return {"success": True, "code": "OK", "message": result.message, "data": data}


# ── Product ──────────────────────────────────────────
@router.get("/", response_model=list[ProductResponse])
def list_products(
    page: int = 1,
    per_page: int = 20,
    session: Session = Depends(get_session),
    _user: CurrentUser = Depends(require_role(["staff", "manager", "owner"])),
):
    repo = build_product_repository(session)
    offset = (page - 1) * per_page
    products = repo.list_products(offset=offset, limit=per_page)
    return [ProductResponse.model_validate(p.__dict__) for p in products]


@router.get("/{product_id}", response_model=ProductResponse)
def get_product(
    product_id: UUID,
    session: Session = Depends(get_session),
    _user: CurrentUser = Depends(require_role(["staff", "manager", "owner"])),
):
    repo = build_product_repository(session)
    product = repo.get_by_id(product_id)
    if not product:
        raise HTTPException(status_code=404, detail={"code": ERR_BIZ_002, "message": "品項不存在"})
    return ProductResponse.model_validate(product.__dict__)


@router.post("/", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
def create_product(
    body: ProductCreate,
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(require_role(["manager", "owner"])),
):
    repo = build_product_repository(session)
    product = Product(
        name=body.name,
        raw_name=body.raw_name,
        series=body.series,
        model_number=body.model_number,
        category_id=body.category_id,
        description=body.description,
    )
    saved = repo.save(product)
    build_audit_service(session).log(user.user_id, "create_product", "product", saved.product_id)
    session.commit()
    return ProductResponse.model_validate(saved.__dict__)


@router.put("/{product_id}", response_model=ProductResponse)
def update_product(
    product_id: UUID,
    body: ProductUpdate,
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(require_role(["manager", "owner"])),
):
    repo = build_product_repository(session)
    existing = repo.get_by_id(product_id)
    if not existing:
        raise HTTPException(status_code=404, detail={"code": ERR_BIZ_002, "message": "品項不存在"})

    if existing.version != body.version:
        raise HTTPException(status_code=409, detail={"code": ERR_BIZ_004, "message": "資料已被他人修改，請重新載入"})

    if body.name is not None:
        existing.name = body.name
    if body.series is not None:
        existing.series = body.series
    if body.model_number is not None:
        existing.model_number = body.model_number
    if body.category_id is not None:
        existing.category_id = body.category_id
    if body.description is not None:
        existing.description = body.description
    existing.version += 1

    saved = repo.save(existing)
    build_audit_service(session).log(user.user_id, "update_product", "product", saved.product_id)
    session.commit()
    return ProductResponse.model_validate(saved.__dict__)


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product(
    product_id: UUID,
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(require_role(["owner"])),
):
    repo = build_product_repository(session)
    existing = repo.get_by_id(product_id)
    if not existing:
        raise HTTPException(status_code=404, detail={"code": ERR_BIZ_002, "message": "品項不存在"})

    repo.delete(product_id)
    build_audit_service(session).log(
        user.user_id, "delete_product", "product", product_id, detail={"name": existing.name}
    )
    session.commit()


# ── SKU ──────────────────────────────────────────────
@router.get("/{product_id}/skus", response_model=list[SKUResponse])
def list_skus(
    product_id: UUID,
    session: Session = Depends(get_session),
    _user: CurrentUser = Depends(require_role(["staff", "manager", "owner"])),
):
    repo = build_sku_repository(session)
    skus = repo.list_by_product(product_id)
    return [SKUResponse.model_validate(s.__dict__) for s in skus]


@router.post("/skus", response_model=SKUResponse, status_code=status.HTTP_201_CREATED)
def create_sku(
    body: SKUCreate,
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(require_role(["manager", "owner"])),
):
    repo = build_sku_repository(session)

    # 條碼唯一檢查
    if body.barcode:
        existing_barcode = repo.get_by_barcode(body.barcode)
        if existing_barcode:
            raise HTTPException(status_code=409, detail={"code": ERR_BIZ_004, "message": f"條碼 {body.barcode} 已存在"})

    sku = SKU(
        product_id=body.product_id,
        brand=body.brand,
        barcode=body.barcode,
        supplier_code=body.supplier_code,
        internal_code=body.internal_code,
        spec=body.spec,
        unit=body.unit,
        sell_price=body.sell_price,
        cost_price=body.cost_price,
        min_stock=body.min_stock,
    )
    saved = repo.save(sku)

    # 建立 InventoryBalance（初始庫存 0）
    balance_repo = build_inventory_balance_repository(session)
    balance_repo.ensure_exists(saved.sku_id)

    build_audit_service(session).log(user.user_id, "create_sku", "sku", saved.sku_id)
    session.commit()
    return SKUResponse.model_validate(saved.__dict__)


@router.put("/skus/{sku_id}", response_model=SKUResponse)
def update_sku(
    sku_id: UUID,
    body: SKUUpdate,
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(require_role(["manager", "owner"])),
):
    repo = build_sku_repository(session)
    existing = repo.get_by_id(sku_id)
    if not existing:
        raise HTTPException(status_code=404, detail={"code": ERR_BIZ_002, "message": "SKU 不存在"})

    if existing.version != body.version:
        raise HTTPException(status_code=409, detail={"code": ERR_BIZ_004, "message": "資料已被他人修改"})

    old_price = existing.sell_price
    if body.brand is not None:
        existing.brand = body.brand
    if body.barcode is not None:
        existing.barcode = body.barcode
    if body.supplier_code is not None:
        existing.supplier_code = body.supplier_code
    if body.internal_code is not None:
        existing.internal_code = body.internal_code
    if body.spec is not None:
        existing.spec = body.spec
    if body.unit is not None:
        existing.unit = body.unit
    if body.sell_price is not None:
        existing.sell_price = body.sell_price
    if body.cost_price is not None:
        existing.cost_price = body.cost_price
    if body.min_stock is not None:
        existing.min_stock = body.min_stock
    existing.version += 1

    saved = repo.save(existing)

    # 改價記 AuditEvent
    action = "update_price" if body.sell_price is not None and body.sell_price != old_price else "update_sku"
    build_audit_service(session).log(
        user.user_id, action, "sku", saved.sku_id,
        detail={"old_price": old_price, "new_price": saved.sell_price} if action == "update_price" else None,
    )
    session.commit()
    return SKUResponse.model_validate(saved.__dict__)


@router.delete("/skus/{sku_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_sku(
    sku_id: UUID,
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(require_role(["owner"])),
):
    repo = build_sku_repository(session)
    existing = repo.get_by_id(sku_id)
    if not existing:
        raise HTTPException(status_code=404, detail={"code": ERR_BIZ_002, "message": "SKU 不存在"})

    # 軟刪除
    existing.is_active = False
    existing.version += 1
    repo.save(existing)
    build_audit_service(session).log(user.user_id, "delete_sku", "sku", sku_id)
    session.commit()
