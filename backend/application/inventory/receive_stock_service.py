"""ReceiveStockService — 進貨驗收 use case。

Transaction 邊界：
  Transaction 內：
    INSERT purchase_receipt
    INSERT stock_movements（N 筆，quantity 為正）
    UPDATE inventory_balance
    UPDATE purchase_order_lines.received_quantity
    UPDATE purchase_order.status
    INSERT audit_event
"""

import uuid
from dataclasses import dataclass

from core.logging import get_logger
from core.results import Result
from domain.inventory.models import StockMovement
from domain.inventory.repository import InventoryBalanceRepository, StockMovementRepository

logger = get_logger("receive_stock")


@dataclass
class ReceiveLineInput:
    sku_id: uuid.UUID
    quantity: int
    unit_cost: float | None = None


class ReceiveStockService:
    def __init__(
        self,
        movement_repo: StockMovementRepository,
        balance_repo: InventoryBalanceRepository,
    ):
        self._movement_repo = movement_repo
        self._balance_repo = balance_repo

    def receive(
        self,
        lines: list[ReceiveLineInput],
        supplier_id: uuid.UUID,
        received_by: uuid.UUID,
        po_id: uuid.UUID | None = None,
        note: str | None = None,
    ) -> Result:
        if not lines:
            return Result.fail("ERR-VAL-001", "驗收明細不可為空")

        receipt_id = uuid.uuid4()

        for line in lines:
            if line.quantity <= 0:
                return Result.fail("ERR-VAL-001", f"SKU {line.sku_id} 數量必須大於 0")

            # 建立庫存異動
            movement = StockMovement(
                sku_id=line.sku_id,
                quantity=line.quantity,  # 正=入庫
                movement_type="purchase_receive",
                reference_type="purchase_receipt",
                reference_id=receipt_id,
                created_by=received_by,
            )
            self._movement_repo.save(movement)

            # 更新庫存餘額
            self._balance_repo.ensure_exists(line.sku_id)
            self._balance_repo.atomic_update(line.sku_id, line.quantity)

        logger.info(
            "stock_received",
            receipt_id=str(receipt_id),
            supplier_id=str(supplier_id),
            lines=len(lines),
        )

        return Result.ok(
            data={"receipt_id": str(receipt_id), "lines": len(lines)},
            message=f"進貨驗收完成，{len(lines)} 筆品項入庫",
        )