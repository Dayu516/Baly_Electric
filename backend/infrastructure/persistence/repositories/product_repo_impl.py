from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from domain.product.models import (
    BomChild,
    Category,
    CategoryAttributeTemplate,
    Product,
    ProductAlias,
    ProductAttribute,
    SKU,
    SupplierPriceQuote,
)
from domain.product.repository import (
    BomRepository,
    CategoryAttributeTemplateRepository,
    CategoryRepository,
    ProductAliasRepository,
    ProductAttributeRepository,
    ProductRepository,
    SKURepository,
    SupplierPriceQuoteRepository,
)
from infrastructure.persistence.orm_models import (
    CategoryAttributeTemplateORM,
    CategoryORM,
    ProductAliasORM,
    ProductAttributeORM,
    ProductBomORM,
    ProductORM,
    ProductSearchDocORM,
    SKUORM,
    SupplierPriceQuoteORM,
)


class SqlProductRepository(ProductRepository):
    def __init__(self, session: Session):
        self._session = session

    def get_by_id(self, product_id: UUID) -> Optional[Product]:
        orm = self._session.get(ProductORM, product_id)
        return self._to_domain(orm) if orm else None

    def save(self, product: Product) -> Product:
        existing = self._session.get(ProductORM, product.product_id)
        if existing:
            existing.name = product.name
            existing.raw_name = product.raw_name
            existing.series = product.series
            existing.model_number = product.model_number
            existing.category_id = product.category_id
            existing.description = product.description
            existing.is_active = product.is_active
            existing.version = product.version
            self._session.flush()
            return self._to_domain(existing)

        orm = ProductORM(
            product_id=product.product_id,
            name=product.name,
            raw_name=product.raw_name,
            series=product.series,
            model_number=product.model_number,
            category_id=product.category_id,
            description=product.description,
            is_active=product.is_active,
            version=product.version,
            source_batch_id=product.source_batch_id,
        )
        self._session.add(orm)
        self._session.flush()

        # 建立搜尋文件
        search_text = " ".join(
            filter(None, [product.name, product.raw_name, product.series, product.model_number])
        )
        search_doc = ProductSearchDocORM(
            product_id=product.product_id, search_text=search_text
        )
        self._session.add(search_doc)
        self._session.flush()

        return self._to_domain(orm)

    def delete(self, product_id: UUID) -> None:
        orm = self._session.get(ProductORM, product_id)
        if orm:
            orm.is_active = False
            self._session.flush()

    def list_products(self, offset: int = 0, limit: int = 20) -> list[Product]:
        orms = (
            self._session.query(ProductORM)
            .filter(ProductORM.is_active == True)  # noqa: E712
            .order_by(ProductORM.name)
            .offset(offset)
            .limit(limit)
            .all()
        )
        return [self._to_domain(o) for o in orms]

    @staticmethod
    def _to_domain(orm: ProductORM) -> Product:
        return Product(
            product_id=orm.product_id,
            name=orm.name,
            raw_name=orm.raw_name,
            series=orm.series,
            model_number=orm.model_number,
            category_id=orm.category_id,
            description=orm.description,
            is_active=orm.is_active,
            version=orm.version,
            created_at=orm.created_at,
            updated_at=orm.updated_at,
        )


class SqlSKURepository(SKURepository):
    def __init__(self, session: Session):
        self._session = session

    def get_by_id(self, sku_id: UUID) -> Optional[SKU]:
        orm = self._session.get(SKUORM, sku_id)
        return self._to_domain(orm) if orm else None

    def get_by_barcode(self, barcode: str) -> Optional[SKU]:
        orm = self._session.query(SKUORM).filter(SKUORM.barcode == barcode).first()
        return self._to_domain(orm) if orm else None

    def save(self, sku: SKU) -> SKU:
        existing = self._session.get(SKUORM, sku.sku_id)
        if existing:
            existing.product_id = sku.product_id
            existing.brand = sku.brand
            existing.barcode = sku.barcode
            existing.supplier_code = sku.supplier_code
            existing.internal_code = sku.internal_code
            existing.spec = sku.spec
            existing.unit = sku.unit
            existing.sell_price = sku.sell_price
            existing.cost_price = sku.cost_price
            existing.min_stock = sku.min_stock
            existing.item_type = sku.item_type
            existing.is_active = sku.is_active
            existing.version = sku.version
            self._session.flush()
            return self._to_domain(existing)

        orm = SKUORM(
            sku_id=sku.sku_id,
            product_id=sku.product_id,
            brand=sku.brand,
            barcode=sku.barcode,
            supplier_code=sku.supplier_code,
            internal_code=sku.internal_code,
            spec=sku.spec,
            unit=sku.unit,
            sell_price=sku.sell_price,
            cost_price=sku.cost_price,
            min_stock=sku.min_stock,
            item_type=sku.item_type,
            source_batch_id=sku.source_batch_id,
            is_active=sku.is_active,
            version=sku.version,
        )
        self._session.add(orm)
        self._session.flush()
        return self._to_domain(orm)

    def list_by_product(self, product_id: UUID) -> list[SKU]:
        orms = (
            self._session.query(SKUORM)
            .filter(SKUORM.product_id == product_id, SKUORM.is_active == True)  # noqa: E712
            .order_by(SKUORM.spec)
            .all()
        )
        return [self._to_domain(o) for o in orms]

    @staticmethod
    def _to_domain(orm: SKUORM) -> SKU:
        return SKU(
            sku_id=orm.sku_id,
            product_id=orm.product_id,
            brand=orm.brand,
            barcode=orm.barcode,
            supplier_code=orm.supplier_code,
            internal_code=orm.internal_code,
            spec=orm.spec,
            unit=orm.unit,
            sell_price=float(orm.sell_price),
            cost_price=float(orm.cost_price) if orm.cost_price else None,
            min_stock=orm.min_stock,
            item_type=orm.item_type,
            is_active=orm.is_active,
            version=orm.version,
        )


class SqlCategoryRepository(CategoryRepository):
    def __init__(self, session: Session):
        self._session = session

    def get_by_id(self, category_id: UUID) -> Optional[Category]:
        orm = self._session.get(CategoryORM, category_id)
        return self._to_domain(orm) if orm else None

    def save(self, category: Category) -> Category:
        existing = self._session.get(CategoryORM, category.category_id)
        if existing:
            existing.name = category.name
            existing.parent_id = category.parent_id
            existing.sort_order = category.sort_order
            self._session.flush()
            return self._to_domain(existing)

        orm = CategoryORM(
            category_id=category.category_id,
            name=category.name,
            parent_id=category.parent_id,
            sort_order=category.sort_order,
        )
        self._session.add(orm)
        self._session.flush()
        return self._to_domain(orm)

    def list_all(self) -> list[Category]:
        orms = self._session.query(CategoryORM).order_by(CategoryORM.sort_order, CategoryORM.name).all()
        return [self._to_domain(o) for o in orms]

    def delete_batch_with_templates(self, category_ids: list[str]) -> None:
        if not category_ids:
            return
        placeholders = ", ".join(f"'{cid}'" for cid in category_ids)
        self._session.execute(text(f"DELETE FROM category_attribute_templates WHERE category_id IN ({placeholders})"))
        self._session.execute(text(f"DELETE FROM categories WHERE category_id IN ({placeholders})"))
        self._session.flush()

    @staticmethod
    def _to_domain(orm: CategoryORM) -> Category:
        return Category(
            category_id=orm.category_id,
            name=orm.name,
            parent_id=orm.parent_id,
            sort_order=orm.sort_order,
        )


class SqlBomRepository(BomRepository):
    def __init__(self, session: Session):
        self._session = session

    def replace_children(self, parent_sku_id: UUID, children: list[BomChild]) -> None:
        # 先刪舊
        self._session.execute(
            text("DELETE FROM product_bom WHERE parent_sku_id = :pid"),
            {"pid": str(parent_sku_id)},
        )
        # 再寫新
        for i, child in enumerate(children):
            self._session.add(ProductBomORM(
                parent_sku_id=parent_sku_id,
                child_sku_id=child.child_sku_id,
                quantity=child.quantity,
                component_role=child.component_role,
                sort_order=child.sort_order if child.sort_order else i,
                note=child.note,
            ))
        self._session.flush()

    def has_children(self, sku_id: UUID) -> bool:
        count = self._session.execute(
            text("SELECT COUNT(*) FROM product_bom WHERE parent_sku_id = :sid"),
            {"sid": str(sku_id)},
        ).scalar()
        return (count or 0) > 0

    def is_child(self, sku_id: UUID) -> bool:
        count = self._session.execute(
            text("SELECT COUNT(*) FROM product_bom WHERE child_sku_id = :sid"),
            {"sid": str(sku_id)},
        ).scalar()
        return (count or 0) > 0


class SqlProductAliasRepository(ProductAliasRepository):
    def __init__(self, session: Session):
        self._session = session

    def save(self, alias: ProductAlias) -> ProductAlias:
        orm = ProductAliasORM(
            alias_id=alias.alias_id,
            product_id=alias.product_id,
            alias=alias.alias,
            alias_type=alias.alias_type,
            created_by=alias.created_by,
        )
        self._session.add(orm)
        self._session.flush()
        return alias

    def get_by_id(self, alias_id: UUID) -> Optional[ProductAlias]:
        orm = self._session.get(ProductAliasORM, alias_id)
        if not orm:
            return None
        return ProductAlias(
            alias_id=orm.alias_id,
            product_id=orm.product_id,
            alias=orm.alias,
            alias_type=orm.alias_type,
            created_by=orm.created_by,
        )

    def delete(self, alias_id: UUID) -> None:
        orm = self._session.get(ProductAliasORM, alias_id)
        if orm:
            self._session.delete(orm)
            self._session.flush()


class SqlSupplierPriceQuoteRepository(SupplierPriceQuoteRepository):
    def __init__(self, session: Session):
        self._session = session

    def save(self, quote: SupplierPriceQuote) -> SupplierPriceQuote:
        orm = SupplierPriceQuoteORM(
            quote_id=quote.quote_id,
            supplier_id=quote.supplier_id,
            sku_id=quote.sku_id,
            unit_price=quote.unit_price,
            unit=quote.unit,
            quoted_at=quote.quoted_at,
            note=quote.note,
            created_by=quote.created_by,
            created_at=quote.created_at or datetime.now(timezone.utc),
        )
        self._session.add(orm)
        self._session.flush()
        return quote


class SqlCategoryAttributeTemplateRepository(CategoryAttributeTemplateRepository):
    def __init__(self, session: Session):
        self._session = session

    def replace_for_category(self, category_id: UUID, templates: list[CategoryAttributeTemplate]) -> None:
        self._session.execute(
            text("DELETE FROM category_attribute_templates WHERE category_id = :cid"),
            {"cid": str(category_id)},
        )
        for t in templates:
            self._session.add(CategoryAttributeTemplateORM(
                template_id=t.template_id,
                category_id=category_id,
                attr_key=t.attr_key,
                attr_unit=t.attr_unit,
                is_required=t.is_required,
                sort_order=t.sort_order,
                attr_options=t.attr_options,
                match_priority=t.match_priority,
                match_type=t.match_type,
            ))
        self._session.flush()


class SqlProductAttributeRepository(ProductAttributeRepository):
    def __init__(self, session: Session):
        self._session = session

    def replace_for_product(self, product_id: UUID, attrs: list[ProductAttribute]) -> None:
        self._session.execute(
            text("DELETE FROM product_attributes WHERE product_id = :pid"),
            {"pid": str(product_id)},
        )
        for a in attrs:
            self._session.add(ProductAttributeORM(
                attr_id=a.attr_id,
                product_id=product_id,
                attr_key=a.attr_key,
                attr_value=a.attr_value,
                attr_unit=a.attr_unit,
            ))
        self._session.flush()
