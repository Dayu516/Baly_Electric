"""Product 模組組裝入口。

所有 Product service 的建立都透過這裡，API 層不可自行組裝 repo。

Usage（API 層）：
    from application.product import build_bom_service, build_category_service
    svc = build_bom_service(session)
"""

from sqlalchemy.orm import Session

from application.product.alias_service import AliasService
from application.product.attribute_service import AttributeService
from application.product.bom_service import BomService
from application.product.category_service import CategoryService
from application.product.import_catalog_service import ImportCatalogService
from application.product.search_service import SearchProductService
from application.product.supplier_price_service import SupplierPriceService
from infrastructure.persistence.query_services.attribute_query_service import AttributeQueryService
from infrastructure.persistence.query_services.procurement_query_service import ProcurementQueryService
from infrastructure.persistence.query_services.product_query_service import ProductQueryService
from infrastructure.persistence.repositories.product_repo_impl import (
    SqlBomRepository,
    SqlCategoryAttributeTemplateRepository,
    SqlCategoryRepository,
    SqlProductAliasRepository,
    SqlProductAttributeRepository,
    SqlProductRepository,
    SqlSKURepository,
    SqlSupplierPriceQuoteRepository,
)
from infrastructure.persistence.repositories.review_repo_impl import SqlReviewTaskRepository


def build_bom_service(session: Session) -> BomService:
    return BomService(
        sku_repo=SqlSKURepository(session),
        bom_repo=SqlBomRepository(session),
    )


def build_search_product_service(session: Session) -> SearchProductService:
    return SearchProductService(
        query_service=ProductQueryService(session),
    )


def build_import_catalog_service(session: Session) -> ImportCatalogService:
    return ImportCatalogService(
        product_repo=SqlProductRepository(session),
        sku_repo=SqlSKURepository(session),
        review_repo=SqlReviewTaskRepository(session),
        category_repo=SqlCategoryRepository(session),
        attribute_writer=AttributeQueryService(session),
    )


def build_category_service(session: Session) -> CategoryService:
    return CategoryService(
        category_repo=SqlCategoryRepository(session),
        query_service=ProductQueryService(session),
    )


def build_attribute_service(session: Session) -> AttributeService:
    return AttributeService(
        template_repo=SqlCategoryAttributeTemplateRepository(session),
        attr_repo=SqlProductAttributeRepository(session),
    )


def build_supplier_price_service(session: Session) -> SupplierPriceService:
    return SupplierPriceService(
        quote_repo=SqlSupplierPriceQuoteRepository(session),
        product_query=ProductQueryService(session),
        procurement_query=ProcurementQueryService(session),
    )


def build_alias_service(session: Session) -> AliasService:
    return AliasService(
        alias_repo=SqlProductAliasRepository(session),
    )


def build_product_query_service(session: Session):
    return ProductQueryService(session)


def build_attribute_query_service(session: Session):
    return AttributeQueryService(session)


def build_product_repository(session: Session):
    return SqlProductRepository(session)


def build_sku_repository(session: Session):
    return SqlSKURepository(session)


def build_category_repository(session: Session):
    return SqlCategoryRepository(session)
