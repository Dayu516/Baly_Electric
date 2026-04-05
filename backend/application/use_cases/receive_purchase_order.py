"""ReceivePurchaseOrderUseCase — 採購收貨入庫正式流程。

職責（Use Case 層）：
  1. Idempotency 檢查（同 key 同數量 → 回既有；同 key 不同數量 → 同日覆蓋修正）
  2. Over-receive line-level 防護
  3. 呼叫 PurchaseOrderService.receive_order()（transaction 內）
  4. Audit（transaction 內）
  5. Commit
  6. Post-commit side effects（backorder + 進價異常 + low stock resolve）

不做：金額計算 / 狀態推導 / repo 呼叫（下沉到 service）
"""

import uuid
from datetime import datetime, timezone
from uuid import UUID

from core.logging import get_logger
from core.results import Result
from domain.alert.repository import OperationalAlertRepository
from domain.inventory.repository import InventoryBalanceRepository
from domain.procurement.repository import PurchaseReceiptLineRepository, PurchaseReceiptRepository
from domain.product.repository import SKURepository
from infrastructure.persistence.query_services.procurement_query_service import ProcurementQueryService
from infrastructure.persistence.repositories.audit_repo_impl import AuditService

logger = get_logger("use_case.receive_po")


class ReceivePurchaseOrderUseCase:
    def __init__(
        self,
        po_service,  # PurchaseOrderService
        receipt_repo: PurchaseReceiptRepository,
        receipt_line_repo: PurchaseReceiptLineRepository,
        audit_service: AuditService,
        alert_repo: OperationalAlertRepository,
        balance_repo: InventoryBalanceRepository,
        sku_repo: SKURepository,
        query_service: ProcurementQueryService,
        session,
    ):
        self._po_service = po_service
        self._receipt_repo = receipt_repo
        self._receipt_line_repo = receipt_line_repo
        self._audit = audit_service
        self._alert_repo = alert_repo
        self._balance_repo = balance_repo
        self._sku_repo = sku_repo
        self._qs = query_service
        self._session = session

    def execute(
        self,
        po_id: UUID,
        lines: list[dict],
        note: str | None,
        user_id: UUID,
        idempotency_key: str | None = None,
    ) -> Result:
        """執行收貨。lines: [{po_line_id, received_quantity, unit_cost?}]"""

        # ── 1. Idempotency 檢查 ──────────────────────────
        if idempotency_key:
            existing_receipt = self._receipt_repo.find_by_idempotency_key(po_id, idempotency_key)
            if existing_receipt:
                existing_lines = self._receipt_line_repo.list_by_receipt(existing_receipt.receipt_id)
                if self._lines_match(existing_lines, lines):
                    # 完全相同 → 回既有結果（真冪等）
                    return Result.ok(
                        data={"receipt_id": str(existing_receipt.receipt_id)},
                        message="此驗收已存在（冪等檢查）",
                    )
                else:
                    # 數量不同 → 同日覆蓋修正
                    return self._overwrite_receipt(
                        existing_receipt, existing_lines, lines, user_id,
                    )

        # ── 2. Over-receive line-level 防護 ───────────────
        validation = self._validate_no_over_receive(po_id, lines)
        if not validation.success:
            return validation

        # ── 3. 呼叫 service（transaction 內）──────────────
        # 傳入 idempotency_key 讓 service 記錄到 receipt
        if idempotency_key:
            # 暫存 key，讓 service 建 receipt 時帶上
            self._po_service._pending_idempotency_key = idempotency_key

        result = self._po_service.receive_order(po_id, lines, note, user_id)

        if hasattr(self._po_service, '_pending_idempotency_key'):
            del self._po_service._pending_idempotency_key

        if not result.success:
            return result

        # ── 4. Audit（transaction 內）─────────────────────
        self._audit.log(
            user_id, "receive_po", "purchase_order",
            entity_id=po_id, detail=result.data,
        )

        # ── 5. Commit ─────────────────────────────────────
        self._session.commit()

        # ── 6. Post-commit side effects ───────────────────
        # backorder + 進價異常已在 po_service 內 best-effort 處理
        # 補：進貨恢復 low stock alert resolve
        self._resolve_low_stock_alerts(lines)

        return result

    def _lines_match(self, existing_lines: list, new_lines: list[dict]) -> bool:
        """比較已存在的 receipt lines 與新提交的 lines 數量是否一致。"""
        existing_map = {str(l.sku_id): l.quantity for l in existing_lines}
        for line in new_lines:
            po_line_id = line.get("po_line_id")
            qty = line.get("received_quantity", 0)
            # 簡化比較：只比數量總和
            # TODO: Phase B 可做 line-level 精確比較
            if qty <= 0:
                continue
        # 如果新 lines 有不同的行或數量，視為不匹配
        new_total = sum(l.get("received_quantity", 0) for l in new_lines if l.get("received_quantity", 0) > 0)
        existing_total = sum(l.quantity for l in existing_lines)
        return new_total == existing_total

    def _overwrite_receipt(
        self, existing_receipt, existing_lines, new_lines, user_id,
    ) -> Result:
        """同日覆蓋修正：計算差額、修正 movement + balance + PO line。

        保護：
          - 僅建立者可覆蓋
          - 僅同日可覆蓋
          TODO: Phase B 加覆蓋次數限制
        """
        # 保護 1：僅建立者可覆蓋
        if existing_receipt.received_by != user_id:
            return Result.fail("ERR-BIZ-010", "僅建立者可修正此驗收")

        # 保護 2：僅同日可覆蓋
        # receipt 的 created_at 在 ORM TimestampMixin 自動設定
        # 這裡用 UTC 日期比較
        today = datetime.now(timezone.utc).date()
        # 由於 domain model 沒有 created_at，用「允許覆蓋」的方式簡化
        # TODO: Phase B 加 created_at 到 domain model 做嚴格日期檢查

        # 計算差額並修正
        from domain.inventory.models import StockMovement

        for new_line in new_lines:
            new_qty = new_line.get("received_quantity", 0)
            if new_qty < 0:
                continue

            # 找到原 receipt line 對應的 SKU
            po_line = self._po_service._po_line_repo.get_by_id(UUID(new_line["po_line_id"]))
            if not po_line:
                continue

            # 找原 receipt 中同一 SKU 的行
            old_qty = 0
            for el in existing_lines:
                if el.sku_id == po_line.sku_id:
                    old_qty = el.quantity
                    break

            diff = new_qty - old_qty
            if diff == 0:
                continue

            # 修正 StockMovement
            movement = StockMovement(
                sku_id=po_line.sku_id,
                quantity=diff,
                movement_type="receive_correction",
                reference_type="purchase_receipt",
                reference_id=existing_receipt.receipt_id,
                note=f"覆蓋修正：{old_qty} → {new_qty}",
                created_by=user_id,
            )
            self._po_service._movement_repo.save(movement)
            self._po_service._balance_repo.atomic_update(po_line.sku_id, diff)

            # 修正 PO line received_quantity
            po_line.received_quantity = (po_line.received_quantity or 0) + diff
            self._po_service._po_line_repo.save(po_line)

        # 重算 PO status
        po = self._po_service._po_repo.get_by_id(existing_receipt.po_id)
        if po:
            all_lines_qty = self._qs.get_po_line_quantities(str(existing_receipt.po_id))
            all_received = all(l["received_quantity"] >= l["ordered_quantity"] for l in all_lines_qty)
            any_received = any(l["received_quantity"] > 0 for l in all_lines_qty)
            if all_received:
                po.status = "received"
            elif any_received:
                po.status = "partial_received"
            self._po_service._po_repo.save(po)

        # Audit
        self._audit.log(
            user_id, "correct_receive", "purchase_order",
            entity_id=existing_receipt.po_id,
            detail={"receipt_id": str(existing_receipt.receipt_id), "action": "overwrite"},
        )

        self._session.commit()

        return Result.ok(
            data={"receipt_id": str(existing_receipt.receipt_id)},
            message="驗收已覆蓋修正",
        )

    def _validate_no_over_receive(self, po_id: UUID, lines: list[dict]) -> Result:
        """檢查每一行 received_quantity + 本次 不超過 ordered_quantity。"""
        all_lines = self._qs.get_po_line_quantities_by_line(str(po_id))
        if not all_lines:
            return Result.ok()

        line_map = {str(l["po_line_id"]): l for l in all_lines}

        for line in lines:
            po_line_id = line.get("po_line_id")
            qty = line.get("received_quantity", 0)
            if qty <= 0:
                continue

            existing = line_map.get(po_line_id)
            if not existing:
                continue

            already_received = existing.get("received_quantity", 0) or 0
            ordered = existing.get("ordered_quantity", 0) or 0

            if already_received + qty > ordered:
                return Result.fail(
                    "ERR-BIZ-011",
                    f"超收：PO line {po_line_id} 已收 {already_received}，本次 {qty}，訂購 {ordered}",
                )

        return Result.ok()

    def _resolve_low_stock_alerts(self, lines: list[dict]) -> None:
        """進貨恢復後自動 resolve low_stock alert。

        規則：current_stock > min_stock → resolve（is_read=true）
        NOTE: Phase B 應拆分 read_status 與 resolution_status，避免語意混淆。
              目前沿用 is_read=false 當 active、is_read=true 當 resolved。
        """
        for line in lines:
            try:
                po_line_id = line.get("po_line_id")
                if not po_line_id:
                    continue
                po_line = self._po_service._po_line_repo.get_by_id(UUID(po_line_id))
                if not po_line:
                    continue

                balance = self._balance_repo.get_by_sku(po_line.sku_id)
                if not balance:
                    continue
                sku = self._sku_repo.get_by_id(po_line.sku_id)
                if not sku:
                    continue

                threshold = sku.min_stock if sku.min_stock is not None else 0
                if balance.current_stock > threshold:
                    # 庫存已恢復 → resolve active low_stock alerts
                    active_alerts = self._alert_repo.list_active_by_reference(
                        "sku", po_line.sku_id, "low_stock",
                    )
                    for alert in active_alerts:
                        self._alert_repo.mark_read(alert.alert_id)
            except Exception:
                logger.warning("low_stock_resolve_failed", exc_info=True)
