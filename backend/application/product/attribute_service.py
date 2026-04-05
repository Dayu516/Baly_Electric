"""AttributeService — 分類模板 / 品項屬性全量覆蓋 use case。"""

from uuid import UUID

from domain.product.models import CategoryAttributeTemplate, ProductAttribute
from domain.product.repository import (
    CategoryAttributeTemplateRepository,
    ProductAttributeRepository,
)


class AttributeService:
    def __init__(
        self,
        template_repo: CategoryAttributeTemplateRepository,
        attr_repo: ProductAttributeRepository,
    ):
        self._template_repo = template_repo
        self._attr_repo = attr_repo

    def replace_category_templates(
        self, category_id: UUID, templates: list[CategoryAttributeTemplate],
    ) -> int:
        """全量覆蓋分類屬性模板。回傳模板數量。"""
        self._template_repo.replace_for_category(category_id, templates)
        return len(templates)

    def replace_product_attributes(
        self, product_id: UUID, attrs: list[ProductAttribute],
    ) -> int:
        """全量覆蓋品項屬性。回傳屬性數量。"""
        self._attr_repo.replace_for_product(product_id, attrs)
        return len(attrs)
