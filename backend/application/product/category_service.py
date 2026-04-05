"""CategoryService — 分類刪除 use case。

規則：
- 遞迴找出目標分類及所有子孫分類
- 檢查是否仍有品項綁定
- 有品項 → 拒絕刪除
- 無品項 → 批次刪除分類 + 屬性模板
"""

from uuid import UUID

from core.results import Result
from domain.product.repository import CategoryRepository
from infrastructure.persistence.query_services.product_query_service import ProductQueryService


class CategoryService:
    def __init__(
        self,
        category_repo: CategoryRepository,
        query_service: ProductQueryService,
    ):
        self._category_repo = category_repo
        self._query = query_service

    def delete_category(self, category_id: UUID) -> Result:
        """刪除分類（含子孫分類），有品項綁定時拒絕。"""
        existing = self._category_repo.get_by_id(category_id)
        if not existing:
            return Result.fail("ERR-BIZ-002", "分類不存在")

        # 遞迴取得所有子孫分類（含自己）
        all_ids = self._query.get_all_descendant_ids(str(category_id))

        # 檢查是否有品項使用這些分類
        product_count = self._query.count_products_in_categories(all_ids)
        if product_count > 0:
            return Result.fail(
                "ERR-BIZ-004",
                f"此分類（含子分類）底下有 {product_count} 個品項，請先移除品項的分類",
            )

        # 批次刪除
        self._category_repo.delete_batch_with_templates(all_ids)

        return Result.ok(
            data={"deleted_count": len(all_ids), "name": existing.name},
            message=f"已刪除「{existing.name}」及 {len(all_ids) - 1} 個子分類",
        )
