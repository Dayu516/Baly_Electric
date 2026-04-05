"""VoidSaleService — 退貨作廢 use case。

Transaction 邊界（Phase A 開發憲法 1.3）：
  Transaction 內：
    UPDATE sale.status = voided
    INSERT stock_movements（quantity 為正，退回庫存）
    UPDATE inventory_balance
    UPDATE accounts_receivable（月結客戶退款）
    INSERT audit_event
"""

import uuid

from core.logging import get_logger
from core.results import Result
from domain.inventory.models import StockMovement
from domain.inventory.repository import InventoryBalanceRepository, StockMovementRepository
from domain.sales.repository import SaleRepository
from domain.customer.repository import AccountsReceivableRepository

logger = get_logger("void_sale")


class VoidSaleService:
    def __init__(
        self,
        sale_repo: SaleRepository,
        movement_repo: StockMovementRepository,
        balance_repo: InventoryBalanceRepository,
        ar_repo: AccountsReceivableRepository | None = None,
    ):
        self._sale_repo = sale_repo
        self._movement_repo = movement_repo
        self._balance_repo = balance_repo
        self._ar_repo = ar_repo

    def void(self, sale_id: uuid.UUID, user_id: uuid.UUID, reason: str | None = None) -> Result:
        sale = self._sale_repo.get_by_id(sale_id)
        if not sale:
            return Result.fail("ERR-BIZ-002", "交易不存在")

        if sale.status == "voided":
            return Result.fail("ERR-BIZ-001", "交易已作廢")

        # 標記作廢
        sale.status = "voided"
        sale.note = f"[作廢] {reason or ''}" if reason else "[作廢]"
        self._sale_repo.save(sale)

        # 退回庫存：用 reference_id 找原始出庫異動
        original_movements = self._movement_repo.list_by_reference("sale", sale_id)
        for m in original_movements:
            return_movement = StockMovement(
                sku_id=m.sku_id,
                quantity=abs(m.quantity),  # 正數 = 入庫
                movement_type="return",
                reference_type="sale",
                reference_id=sale_id,
                note=f"退貨 - 作廢交易 {sale_id}",
                created_by=user_id,
            )
            self._movement_repo.save(return_movement)
            self._balance_repo.atomic_update(m.sku_id, abs(m.quantity))

        # 月結客戶退款
        if sale.payment_method == "monthly_credit" and sale.customer_id and self._ar_repo:
            from datetime import datetime, timezone
            period = datetime.now(timezone.utc).strftime("%Y-%m")
            ar = self._ar_repo.get_by_customer_period(sale.customer_id, period)
            if ar:
                ar.total_amount -= sale.total
                self._ar_repo.save(ar)

        logger.info("sale_voided", sale_id=str(sale_id), total=sale.total)

        return Result.ok(message="交易已作廢，庫存已退回")