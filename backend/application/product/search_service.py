"""品項搜尋 — SearchProductService（Phase A 關鍵字版）。

搜尋策略：
  1. 條碼精確匹配（最優先）
  2. 品名 / 型號 / 廠牌 / 規格 ILIKE 模糊匹配
  搜尋 SQL 集中在 infrastructure/persistence/query_service.py
"""

from core.results import Result
from infrastructure.persistence.query_services.product_query_service import ProductQueryService


class SearchProductService:
    def __init__(self, query_service: ProductQueryService):
        self._query = query_service

    def search(self, keyword: str, page: int = 1, per_page: int = 20) -> Result:
        keyword = keyword.strip()
        if not keyword:
            return Result.fail("ERR-VAL-001", "搜尋關鍵字不可為空")

        offset = (page - 1) * per_page
        results = self._query.search_products(keyword, offset=offset, limit=per_page)

        return Result.ok(data=results, message=f"找到 {len(results)} 筆結果")