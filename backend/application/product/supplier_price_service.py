"""SupplierPriceService — 供應商報價記錄 use case。"""

from datetime import datetime, timezone
from uuid import UUID

from core.errors import ERR_BIZ_002
from core.results import Result
from domain.product.models import SupplierPriceQuote
from domain.product.repository import SupplierPriceQuoteRepository
from infrastructure.persistence.query_services.product_query_service import ProductQueryService
from infrastructure.persistence.query_services.procurement_query_service import ProcurementQueryService


class SupplierPriceService:
    def __init__(
        self,
        quote_repo: SupplierPriceQuoteRepository,
        product_query: ProductQueryService,
        procurement_query: ProcurementQueryService,
    ):
        self._quote_repo = quote_repo
        self._product_query = product_query
        self._procurement_query = procurement_query

    def create_quote(
        self,
        product_id: UUID,
        supplier_id: str,
        sku_id: str,
        unit_price: float,
        user_id: UUID,
        unit: str | None = None,
        quoted_at: str | None = None,
        note: str | None = None,
    ) -> Result:
        # 驗證 SKU 屬於品項
        if not self._product_query.verify_sku_belongs_to_product(sku_id, str(product_id)):
            return Result.fail(ERR_BIZ_002, "SKU 不存在或不屬於此品項")

        # 驗證供應商存在
        sup_name = self._product_query.get_active_supplier_name(supplier_id)
        if not sup_name:
            return Result.fail(ERR_BIZ_002, "供應商不存在")

        # 解析報價日期
        quoted_dt = datetime.now(timezone.utc)
        if quoted_at:
            try:
                quoted_dt = datetime.fromisoformat(quoted_at)
                if quoted_dt.tzinfo is None:
                    quoted_dt = quoted_dt.replace(tzinfo=timezone.utc)
            except ValueError:
                pass

        quote = SupplierPriceQuote(
            supplier_id=UUID(supplier_id),
            sku_id=UUID(sku_id),
            unit_price=unit_price,
            unit=unit,
            quoted_at=quoted_dt,
            note=note,
            created_by=user_id,
            created_at=datetime.now(timezone.utc),
        )
        self._quote_repo.save(quote)

        # 更新 supplier_products.unit_cost
        self._procurement_query.update_supplier_product_cost(supplier_id, sku_id, unit_price)

        return Result.ok(
            data={
                "quote_id": str(quote.quote_id),
                "supplier_name": sup_name,
                "unit_price": unit_price,
                "quoted_at": quoted_dt.isoformat(),
            },
            message=f"已記錄 {sup_name} 報價 ${unit_price}",
        )
