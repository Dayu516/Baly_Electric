from abc import ABC, abstractmethod
from typing import Optional
from uuid import UUID

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


class ProductRepository(ABC):
    @abstractmethod
    def get_by_id(self, product_id: UUID) -> Optional[Product]: ...

    @abstractmethod
    def save(self, product: Product) -> Product: ...

    @abstractmethod
    def delete(self, product_id: UUID) -> None: ...

    @abstractmethod
    def list_products(self, offset: int = 0, limit: int = 20) -> list[Product]: ...


class SKURepository(ABC):
    @abstractmethod
    def get_by_id(self, sku_id: UUID) -> Optional[SKU]: ...

    @abstractmethod
    def get_by_barcode(self, barcode: str) -> Optional[SKU]: ...

    @abstractmethod
    def save(self, sku: SKU) -> SKU: ...

    @abstractmethod
    def list_by_product(self, product_id: UUID) -> list[SKU]: ...


class CategoryRepository(ABC):
    @abstractmethod
    def get_by_id(self, category_id: UUID) -> Optional[Category]: ...

    @abstractmethod
    def save(self, category: Category) -> Category: ...

    @abstractmethod
    def list_all(self) -> list[Category]: ...

    @abstractmethod
    def delete_batch_with_templates(self, category_ids: list[str]) -> None:
        """批次刪除分類及其屬性模板。"""
        ...


class BomRepository(ABC):
    @abstractmethod
    def replace_children(self, parent_sku_id: UUID, children: list[BomChild]) -> None:
        """全量覆蓋 BOM（delete + insert）。"""
        ...

    @abstractmethod
    def has_children(self, sku_id: UUID) -> bool: ...

    @abstractmethod
    def is_child(self, sku_id: UUID) -> bool: ...


class ProductAliasRepository(ABC):
    @abstractmethod
    def save(self, alias: ProductAlias) -> ProductAlias: ...

    @abstractmethod
    def get_by_id(self, alias_id: UUID) -> Optional[ProductAlias]: ...

    @abstractmethod
    def delete(self, alias_id: UUID) -> None: ...


class SupplierPriceQuoteRepository(ABC):
    @abstractmethod
    def save(self, quote: SupplierPriceQuote) -> SupplierPriceQuote: ...


class CategoryAttributeTemplateRepository(ABC):
    @abstractmethod
    def replace_for_category(self, category_id: UUID, templates: list[CategoryAttributeTemplate]) -> None:
        """全量覆蓋分類屬性模板（delete + insert）。"""
        ...


class ProductAttributeRepository(ABC):
    @abstractmethod
    def replace_for_product(self, product_id: UUID, attrs: list[ProductAttribute]) -> None:
        """全量覆蓋品項屬性（delete + insert）。"""
        ...
