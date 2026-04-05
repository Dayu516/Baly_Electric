"""StockRecalcService — 庫存重算 use case。

規則：
  - InventoryBalance.current_stock = SUM(StockMovement.quantity)
  - 重算後如果不一致 → OperationalAlert(critical)
  - 以 SUM(movements) 為準修正
"""

import uuid

from core.logging import get_logger
from core.results import Result
from domain.alert.repository import OperationalAlertRepository
from domain.inventory.repository import InventoryBalanceRepository
from infrastructure.persistence.query_services.inventory_query_service import InventoryQueryService

logger = get_logger("stock_recalc")


class StockRecalcService:
    def __init__(
        self,
        query_service: InventoryQueryService,
        balance_repo: InventoryBalanceRepository,
        alert_repo: OperationalAlertRepository | None = None,
    ):
        self._query = query_service
        self._balance_repo = balance_repo
        self._alert_repo = alert_repo

    def recalc(self, sku_id: uuid.UUID) -> Result:
        """重算單一 SKU 的庫存。"""
        correct_stock = self._query.recalc_inventory_balance(str(sku_id))
        self._balance_repo.set_stock(sku_id, correct_stock)

        logger.info("stock_recalced", sku_id=str(sku_id), correct_stock=correct_stock)

        return Result.ok(
            data={"sku_id": str(sku_id), "current_stock": correct_stock},
            message=f"庫存重算完成：{correct_stock}",
        )
