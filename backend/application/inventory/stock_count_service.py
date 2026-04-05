"""StockCountService — 盤點 use case。

流程：
  1. 提交盤點清單（sku_id + 實際數量）
  2. 比對帳面數量
  3. 有差異 → 建立 ReviewTask (stock_discrepancy)
  4. 確認調整後 → 建立 StockMovement (adjustment) + 更新 InventoryBalance
"""

import uuid
from dataclasses import dataclass

from core.logging import get_logger
from core.results import Result
from domain.inventory.models import StockMovement
from domain.inventory.repository import InventoryBalanceRepository, StockMovementRepository
from domain.review.models import ReviewTask
from domain.review.repository import ReviewTaskRepository

logger = get_logger("stock_count")


@dataclass
class CountLineInput:
    sku_id: uuid.UUID
    actual_quantity: int


@dataclass
class CountDiscrepancy:
    sku_id: uuid.UUID
    book_quantity: int
    actual_quantity: int
    difference: int


class StockCountService:
    def __init__(
        self,
        balance_repo: InventoryBalanceRepository,
        movement_repo: StockMovementRepository,
        review_repo: ReviewTaskRepository,
    ):
        self._balance_repo = balance_repo
        self._movement_repo = movement_repo
        self._review_repo = review_repo

    def submit_count(
        self,
        lines: list[CountLineInput],
        counted_by: uuid.UUID,
    ) -> Result:
        """提交盤點清單。帳實不符產生 ReviewTask。"""
        discrepancies: list[CountDiscrepancy] = []

        for line in lines:
            balance = self._balance_repo.get_by_sku(line.sku_id)
            book_qty = balance.current_stock if balance else 0
            diff = line.actual_quantity - book_qty

            if diff != 0:
                discrepancies.append(CountDiscrepancy(
                    sku_id=line.sku_id,
                    book_quantity=book_qty,
                    actual_quantity=line.actual_quantity,
                    difference=diff,
                ))

        if not discrepancies:
            return Result.ok(message="盤點完成，帳實相符")

        # 建立 ReviewTask
        detail_lines = [
            f"SKU {d.sku_id}: 帳面 {d.book_quantity} / 實際 {d.actual_quantity} / 差異 {d.difference:+d}"
            for d in discrepancies
        ]
        review = ReviewTask(
            review_type="stock_discrepancy",
            title=f"盤點差異 {len(discrepancies)} 筆品項",
            detail="\n".join(detail_lines),
        )
        self._review_repo.save(review)

        logger.info("stock_count_submitted", discrepancies=len(discrepancies))

        return Result.ok(
            data={
                "discrepancies": [
                    {
                        "sku_id": str(d.sku_id),
                        "book_quantity": d.book_quantity,
                        "actual_quantity": d.actual_quantity,
                        "difference": d.difference,
                    }
                    for d in discrepancies
                ],
                "review_task_id": str(review.task_id),
            },
            message=f"盤點完成，{len(discrepancies)} 筆差異待確認",
        )

    def adjust(
        self,
        sku_id: uuid.UUID,
        actual_quantity: int,
        adjusted_by: uuid.UUID,
        note: str | None = None,
        review_task_id: uuid.UUID | None = None,
    ) -> Result:
        """確認差異後執行庫存調整。有 review_task_id 時同步結案。"""
        balance = self._balance_repo.get_by_sku(sku_id)
        book_qty = balance.current_stock if balance else 0
        diff = actual_quantity - book_qty

        if diff == 0:
            return Result.ok(message="帳實相符，無需調整")

        movement = StockMovement(
            sku_id=sku_id,
            quantity=diff,  # 正=補正增加，負=補正減少
            movement_type="adjustment",
            reference_type="stock_count",
            note=note or f"盤點調整：帳面 {book_qty} → 實際 {actual_quantity}",
            created_by=adjusted_by,
        )
        self._movement_repo.save(movement)
        self._balance_repo.atomic_update(sku_id, diff)

        # 結案 ReviewTask（Constitution 1.2 盤點調整）
        if review_task_id:
            from datetime import datetime, timezone
            task = self._review_repo.get_by_id(review_task_id)
            if task:
                task.status = "completed"
                task.resolved_at = datetime.now(timezone.utc)
                self._review_repo.save(task)

        logger.info("stock_adjusted", sku_id=str(sku_id), diff=diff)

        return Result.ok(message=f"庫存已調整：{book_qty} → {actual_quantity}")