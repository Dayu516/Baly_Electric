"""BackorderService — 欠貨待補核心服務。

職責：
  - 建立欠貨（POS 結帳時部分交付）
  - 綁定 PO（欠貨對應採購）
  - 標記到貨（PO 驗收觸發）
  - 補交（出庫 + 結清）
  - 通知客人
  - 取消欠貨

狀態變更只在這裡，不在 API 層。
所有狀態由 rules.update_line_statuses 推導，不手動設。
"""

import uuid
from datetime import datetime, timezone

from core.logging import get_logger
from core.results import Result
from application.sales.rules import derive_has_backorder, update_line_statuses
from domain.alert.models import OperationalAlert
from domain.alert.repository import OperationalAlertRepository
from domain.inventory.models import StockMovement
from domain.inventory.repository import InventoryBalanceRepository, StockMovementRepository
from domain.sales.models import CustomerPickupNotification, SaleLineFulfillment
from domain.sales.repository import (
    CustomerPickupNotificationRepository,
    SaleLineFulfillmentRepository,
    SaleLineRepository,
    SaleRepository,
)

logger = get_logger("backorder")


class BackorderService:
    def __init__(
        self,
        sale_repo: SaleRepository,
        sale_line_repo: SaleLineRepository,
        fulfillment_repo: SaleLineFulfillmentRepository,
        notification_repo: CustomerPickupNotificationRepository,
        movement_repo: StockMovementRepository,
        balance_repo: InventoryBalanceRepository,
        alert_repo: OperationalAlertRepository | None = None,
    ):
        self._sale_repo = sale_repo
        self._sale_line_repo = sale_line_repo
        self._fulfillment_repo = fulfillment_repo
        self._notification_repo = notification_repo
        self._movement_repo = movement_repo
        self._balance_repo = balance_repo
        self._alert_repo = alert_repo

    # ── 建立欠貨（POS 結帳時） ───────────────────────────
    def create_backorder(
        self,
        sale_line_id: uuid.UUID,
        delivered_qty: int,
        note: str | None = None,
    ) -> Result:
        """POS 結帳後，店員輸入實交數量，差額自動變 backorder。"""
        sl = self._sale_line_repo.get_by_id(sale_line_id)
        if not sl:
            return Result.fail("ERR-BIZ-001", "銷貨明細不存在")

        total_qty = sl.ordered_qty or sl.quantity
        if delivered_qty >= total_qty:
            return Result.fail("ERR-BIZ-002", "實交量 >= 訂購量，不需要建欠貨")
        if delivered_qty < 0:
            return Result.fail("ERR-BIZ-003", "實交量不可為負")

        backorder_qty = total_qty - delivered_qty
        sl.delivered_qty = delivered_qty
        sl.backorder_qty = backorder_qty
        if note:
            sl.reserved_customer_note = note

        update_line_statuses(sl)
        self._sale_line_repo.save(sl)
        self._update_sale_has_backorder(sl.sale_id)

        logger.info("backorder_created", sale_line_id=str(sale_line_id),
                     delivered=delivered_qty, backorder=backorder_qty)
        return Result.ok(
            data={"backorder_qty": backorder_qty},
            message=f"已建立欠貨 {backorder_qty} 個",
        )

    # ── 綁定 PO（欠貨 → 採購） ──────────────────────────
    def link_to_po(
        self,
        sale_line_id: uuid.UUID,
        po_id: uuid.UUID,
        po_line_id: uuid.UUID | None,
        allocated_qty: int,
    ) -> Result:
        sl = self._sale_line_repo.get_by_id(sale_line_id)
        if not sl or sl.backorder_qty == 0:
            return Result.fail("ERR-BIZ-004", "明細不存在或沒有欠貨")

        # 建立履約分配記錄
        fulfillment = SaleLineFulfillment(
            sale_id=sl.sale_id,
            sale_line_id=sale_line_id,
            source_type="purchase_order",
            source_doc_id=po_id,
            source_line_id=po_line_id,
            allocated_qty=allocated_qty,
            status="pending",
        )
        self._fulfillment_repo.save(fulfillment)

        sl.backorder_ordered_qty = (sl.backorder_ordered_qty or 0) + allocated_qty
        update_line_statuses(sl)
        self._sale_line_repo.save(sl)

        logger.info("backorder_linked_po", sale_line_id=str(sale_line_id), po_id=str(po_id))
        return Result.ok(message="已綁定採購單")

    # ── 標記到貨（PO 驗收觸發） ──────────────────────────
    def mark_arrived(
        self,
        sale_line_id: uuid.UUID,
        arrived_qty: int,
        po_id: uuid.UUID | None = None,
    ) -> Result:
        sl = self._sale_line_repo.get_by_id(sale_line_id)
        if not sl or sl.backorder_qty == 0:
            return Result.fail("ERR-BIZ-004", "明細不存在或沒有欠貨")

        sl.backorder_arrived_qty = arrived_qty
        update_line_statuses(sl)
        self._sale_line_repo.save(sl)

        # 更新對應的 fulfillment 記錄
        if po_id:
            fulfillments = self._fulfillment_repo.list_by_sale_line_and_source(sale_line_id, po_id)
            for f in fulfillments:
                f.arrived_qty = min(arrived_qty, f.allocated_qty)
                if f.arrived_qty >= f.allocated_qty:
                    f.status = "arrived"
                elif f.arrived_qty > 0:
                    f.status = "partial_arrived"
                self._fulfillment_repo.save(f)

        # 自動建 OperationalAlert 通知（best-effort，失敗不回滾主流程）
        sale = self._sale_repo.get_by_id(sl.sale_id)
        if sale and sale.customer_id and self._alert_repo:
            try:
                self._alert_repo.save(OperationalAlert(
                    alert_type="backorder_arrived",
                    severity="info",
                    title=f"客戶欠貨到貨：{sl.product_name}",
                    detail=f"到貨 {arrived_qty} 個，請通知客戶取貨",
                    reference_type="sale_line",
                    reference_id=sale_line_id,
                ))
            except Exception:
                logger.warning("alert_create_failed", sale_line_id=str(sale_line_id), exc_info=True)

        logger.info("backorder_arrived", sale_line_id=str(sale_line_id), arrived_qty=arrived_qty)
        return Result.ok(message=f"已標記到貨 {arrived_qty} 個")

    # ── 補交（出庫 + 結清） ──────────────────────────────
    def deliver_backorder(
        self,
        sale_line_id: uuid.UUID,
        deliver_qty: int,
        user_id: uuid.UUID,
    ) -> Result:
        """補交：扣庫存 + 更新 backorder_delivered_qty。帳務掛在原 sale。"""
        sl = self._sale_line_repo.get_by_id(sale_line_id)
        if not sl or sl.backorder_qty == 0:
            return Result.fail("ERR-BIZ-004", "明細不存在或沒有欠貨")
        if deliver_qty <= 0:
            return Result.fail("ERR-BIZ-005", "補交量必須大於 0")

        remaining = sl.backorder_qty - (sl.backorder_delivered_qty or 0)
        if deliver_qty > remaining:
            return Result.fail("ERR-BIZ-006", f"補交量 {deliver_qty} 超過剩餘欠貨 {remaining}")

        # 庫存出庫（atomic update，避免 race condition）
        movement = StockMovement(
            sku_id=sl.sku_id,
            quantity=-deliver_qty,
            movement_type="backorder_delivery",
            reference_type="sale",
            reference_id=sl.sale_id,
            created_by=user_id,
        )
        self._movement_repo.save(movement)
        self._balance_repo.atomic_update(sl.sku_id, -deliver_qty)

        # 更新數量
        sl.backorder_delivered_qty = (sl.backorder_delivered_qty or 0) + deliver_qty
        sl.delivered_qty = (sl.delivered_qty or 0) + deliver_qty

        now = datetime.now(timezone.utc)
        if sl.backorder_delivered_qty >= sl.backorder_qty:
            sl.pickup_completed_at = now
            sl.closed_at = now

        update_line_statuses(sl)
        self._sale_line_repo.save(sl)
        self._update_sale_has_backorder(sl.sale_id)

        # 更新 fulfillment 記錄
        fulfillments = self._fulfillment_repo.list_by_sale_line_id(sale_line_id)
        remaining_deliver = deliver_qty
        for f in fulfillments:
            if remaining_deliver <= 0:
                break
            can_deliver = f.arrived_qty - f.delivered_qty
            if can_deliver > 0:
                actual = min(can_deliver, remaining_deliver)
                f.delivered_qty += actual
                remaining_deliver -= actual
                if f.delivered_qty >= f.allocated_qty:
                    f.status = "completed"
                self._fulfillment_repo.save(f)

        logger.info("backorder_delivered", sale_line_id=str(sale_line_id), deliver_qty=deliver_qty)
        return Result.ok(message=f"已補交 {deliver_qty} 個")

    # ── 通知客人 ─────────────────────────────────────────
    def notify_customer(
        self,
        sale_id: uuid.UUID,
        sale_line_id: uuid.UUID | None,
        channel: str = "manual",
        message: str | None = None,
        sent_by: uuid.UUID | None = None,
        remark: str | None = None,
    ) -> Result:
        sale = self._sale_repo.get_by_id(sale_id)
        if not sale or not sale.customer_id:
            return Result.fail("ERR-BIZ-007", "銷貨單不存在或無客戶")

        now = datetime.now(timezone.utc)

        # 建通知紀錄
        notification = CustomerPickupNotification(
            customer_id=sale.customer_id,
            sale_id=sale_id,
            sale_line_id=sale_line_id,
            channel=channel,
            message_snapshot=message,
            status="sent",
            sent_by=sent_by,
            sent_at=now,
            remark=remark,
        )
        self._notification_repo.save(notification)

        # 更新 sale_line 通知欄位
        if sale_line_id:
            sl = self._sale_line_repo.get_by_id(sale_line_id)
            if sl:
                if sl.notified_at is None:
                    sl.notified_at = now
                sl.notify_count = (sl.notify_count or 0) + 1
                sl.last_notify_channel = channel
                self._sale_line_repo.save(sl)
        else:
            # 整張 sale 的所有欠貨 line 都更新
            lines = self._sale_line_repo.list_by_sale_id(sale_id)
            for sl in lines:
                if sl.backorder_qty > 0:
                    if sl.notified_at is None:
                        sl.notified_at = now
                    sl.notify_count = (sl.notify_count or 0) + 1
                    sl.last_notify_channel = channel
                    self._sale_line_repo.save(sl)

        return Result.ok(message="已通知客戶")

    # ── 取消欠貨 ─────────────────────────────────────────
    def cancel_backorder(self, sale_line_id: uuid.UUID) -> Result:
        sl = self._sale_line_repo.get_by_id(sale_line_id)
        if not sl or sl.backorder_qty == 0:
            return Result.fail("ERR-BIZ-004", "明細不存在或沒有欠貨")

        sl.backorder_qty = 0
        sl.backorder_status = "cancelled"
        sl.closed_at = datetime.now(timezone.utc)
        update_line_statuses(sl)
        self._sale_line_repo.save(sl)
        self._update_sale_has_backorder(sl.sale_id)

        return Result.ok(message="已取消欠貨")

    # ── 內部：重算 sale.has_backorder ───────────────────
    def _update_sale_has_backorder(self, sale_id: uuid.UUID) -> None:
        """重算 sale.has_backorder 快取欄位。"""
        sale = self._sale_repo.get_by_id(sale_id)
        if not sale:
            return
        lines = self._sale_line_repo.list_by_sale_id(sale_id)
        sale.has_backorder = derive_has_backorder(lines)
        self._sale_repo.save(sale)
