"""PurchaseOrderService — 採購單完整流程 use case。

依賴：
  - PurchaseOrderRepository / LineRepository / ReceiptRepository（寫入）
  - StockMovementRepository / InventoryBalanceRepository（庫存）
  - ProcurementQueryService（查詢）
  - 不直接依賴 Session 或 ORM
"""

from datetime import datetime, timezone
from uuid import UUID

from core.errors import ERR_BIZ_001, ERR_BIZ_002
from core.logging import get_logger
from core.results import Result
from domain.alert.models import OperationalAlert
from domain.alert.repository import OperationalAlertRepository
from domain.inventory.repository import InventoryBalanceRepository, StockMovementRepository
from domain.inventory.models import StockMovement
from domain.procurement.models import (
    PurchaseOrder,
    PurchaseOrderLine,
    PurchaseReceipt,
    PurchaseReceiptLine,
)
from domain.procurement.repository import (
    PurchaseOrderLineRepository,
    PurchaseOrderRepository,
    PurchaseReceiptLineRepository,
    PurchaseReceiptRepository,
)
from infrastructure.persistence.query_services.procurement_query_service import ProcurementQueryService

logger = get_logger("purchase_order")


class PurchaseOrderService:
    def __init__(
        self,
        po_repo: PurchaseOrderRepository,
        po_line_repo: PurchaseOrderLineRepository,
        receipt_repo: PurchaseReceiptRepository,
        receipt_line_repo: PurchaseReceiptLineRepository,
        movement_repo: StockMovementRepository,
        balance_repo: InventoryBalanceRepository,
        query_service: ProcurementQueryService,
        backorder_service=None,
        alert_repo: OperationalAlertRepository | None = None,
    ):
        self._po_repo = po_repo
        self._po_line_repo = po_line_repo
        self._receipt_repo = receipt_repo
        self._receipt_line_repo = receipt_line_repo
        self._movement_repo = movement_repo
        self._balance_repo = balance_repo
        self._qs = query_service
        self._backorder_service = backorder_service
        self._alert_repo = alert_repo

    # ── 查詢 ──────────────────────────────────────────

    def list_orders(
        self, *, status: str | None, supplier_id: str | None,
        keyword: str | None = None, date_from: str | None = None, date_to: str | None = None,
        page: int, per_page: int,
    ) -> Result:
        offset = (page - 1) * per_page
        rows = self._qs.list_purchase_orders(
            status=status, supplier_id=supplier_id,
            keyword=keyword, date_from=date_from, date_to=date_to,
            offset=offset, limit=per_page,
        )
        data = [
            {
                "po_id": str(r["po_id"]),
                "supplier_id": str(r["supplier_id"]),
                "supplier_name": r["supplier_name"],
                "status": r["status"],
                "note": r["note"],
                "ordered_at": r["ordered_at"].isoformat() if r["ordered_at"] else None,
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
                "line_count": r["line_count"],
                "total_amount": float(r["total_amount"]),
            }
            for r in rows
        ]
        return Result.ok(data=data)

    def get_order(self, po_id: UUID) -> Result:
        header = self._qs.get_purchase_order_detail(str(po_id))
        if not header:
            return Result.fail(ERR_BIZ_002, "採購單不存在")

        lines = self._qs.get_purchase_order_lines(str(po_id))

        ordered_total = sum(
            (l["ordered_quantity"] or 0) * float(l["unit_cost"] or 0) for l in lines
        )
        received_total = sum(
            (l["received_quantity"] or 0) * float(l["unit_cost"] or 0) for l in lines
        )

        data = {
            "po_id": str(header["po_id"]),
            "supplier_id": str(header["supplier_id"]),
            "supplier_name": header["supplier_name"],
            "status": header["status"],
            "note": header["note"],
            "ordered_at": header["ordered_at"].isoformat() if header["ordered_at"] else None,
            "created_at": header["created_at"].isoformat() if header["created_at"] else None,
            "ordered_total": ordered_total,
            "received_total": received_total,
            "lines": [
                {
                    "po_line_id": str(l["po_line_id"]),
                    "sku_id": str(l["sku_id"]),
                    "product_name": l["product_name"],
                    "brand": l["brand"],
                    "spec": l["spec"],
                    "unit": l["unit"],
                    "ordered_quantity": l["ordered_quantity"],
                    "received_quantity": l["received_quantity"],
                    "unit_cost": float(l["unit_cost"]) if l["unit_cost"] else None,
                    "line_total": (l["ordered_quantity"] or 0) * float(l["unit_cost"] or 0),
                }
                for l in lines
            ],
        }
        return Result.ok(data=data)

    # ── 建單 ──────────────────────────────────────────

    def create_order(
        self, supplier_id: str, note: str | None, lines: list[dict],
    ) -> Result:
        po = PurchaseOrder(
            supplier_id=UUID(supplier_id),
            status="draft",
            note=note,
        )
        saved_po = self._po_repo.save(po)

        for line in lines:
            self._po_line_repo.save(PurchaseOrderLine(
                po_id=saved_po.po_id,
                sku_id=UUID(line["sku_id"]),
                ordered_quantity=line["ordered_quantity"],
                unit_cost=line.get("unit_cost"),
            ))

        logger.info("po_created", po_id=str(saved_po.po_id))
        return Result.ok(data={"po_id": str(saved_po.po_id)}, message="採購單已建立")

    # ── 更新 ──────────────────────────────────────────

    def update_order(
        self, po_id: UUID, note: str | None,
        lines: list[dict] | None, new_lines: list[dict] | None,
    ) -> Result:
        po = self._po_repo.get_by_id(po_id)
        if not po:
            return Result.fail(ERR_BIZ_002, "採購單不存在")
        if po.status != "draft":
            return Result.fail(ERR_BIZ_001, "只有草稿狀態可以修改")

        if note is not None:
            po.note = note
        self._po_repo.save(po)

        if lines:
            for line in lines:
                existing_line = self._po_line_repo.get_by_id(UUID(line["po_line_id"]))
                if existing_line and str(existing_line.po_id) == str(po_id):
                    existing_line.ordered_quantity = line["ordered_quantity"]
                    existing_line.unit_cost = line.get("unit_cost")
                    self._po_line_repo.save(existing_line)

        if new_lines:
            for line in new_lines:
                self._po_line_repo.save(PurchaseOrderLine(
                    po_id=po_id,
                    sku_id=UUID(line["sku_id"]),
                    ordered_quantity=line["ordered_quantity"],
                    unit_cost=line.get("unit_cost"),
                ))

        logger.info("po_updated", po_id=str(po_id))
        return Result.ok(message="採購單已更新")

    # ── 確認下單 ──────────────────────────────────────

    def confirm_order(self, po_id: UUID) -> Result:
        po = self._po_repo.get_by_id(po_id)
        if not po:
            return Result.fail(ERR_BIZ_002, "採購單不存在")
        if po.status != "draft":
            return Result.fail(ERR_BIZ_001, "只有草稿狀態可以確認")

        po.status = "ordered"
        po.ordered_at = datetime.now(timezone.utc)
        self._po_repo.save(po)
        logger.info("po_confirmed", po_id=str(po_id))
        return Result.ok(message="採購單已確認下單")

    # ── 取消 ──────────────────────────────────────────

    def cancel_order(self, po_id: UUID) -> Result:
        po = self._po_repo.get_by_id(po_id)
        if not po:
            return Result.fail(ERR_BIZ_002, "採購單不存在")
        if po.status in ("received", "cancelled"):
            return Result.fail(ERR_BIZ_001, f"狀態 {po.status} 無法取消")

        po.status = "cancelled"
        self._po_repo.save(po)
        logger.info("po_cancelled", po_id=str(po_id))
        return Result.ok(message="採購單已取消")

    # ── 刪除（僅限已取消）─────────────────────────────

    def delete_order(self, po_id: UUID) -> Result:
        po = self._po_repo.get_by_id(po_id)
        if not po:
            return Result.fail(ERR_BIZ_002, "採購單不存在")
        if po.status != "cancelled":
            return Result.fail(ERR_BIZ_001, "只有已取消的採購單可以刪除")

        self._po_line_repo.delete_by_po(po_id)
        self._po_repo.delete(po_id)
        logger.info("po_deleted", po_id=str(po_id))
        return Result.ok(message="採購單已刪除")

    # ── 驗收 ──────────────────────────────────────────

    def receive_order(
        self, po_id: UUID, lines: list[dict], note: str | None, user_id: UUID,
    ) -> Result:
        po = self._po_repo.get_by_id(po_id)
        if not po:
            return Result.fail(ERR_BIZ_002, "採購單不存在")
        if po.status not in ("ordered", "partial_received"):
            return Result.fail(ERR_BIZ_001, f"狀態 {po.status} 無法驗收")
        if not lines:
            return Result.fail(ERR_BIZ_001, "至少需要一筆驗收明細")

        receipt = self._receipt_repo.save(PurchaseReceipt(
            po_id=po_id,
            supplier_id=po.supplier_id,
            received_by=user_id,
            note=note,
        ))

        for line in lines:
            po_line = self._po_line_repo.get_by_id(UUID(line["po_line_id"]))
            if not po_line or str(po_line.po_id) != str(po_id):
                continue

            qty = line["received_quantity"]
            if qty <= 0:
                continue

            cost = line.get("unit_cost") if line.get("unit_cost") is not None else po_line.unit_cost

            self._receipt_line_repo.save(PurchaseReceiptLine(
                receipt_id=receipt.receipt_id,
                sku_id=po_line.sku_id,
                quantity=qty,
                unit_cost=cost,
            ))

            self._movement_repo.save(StockMovement(
                sku_id=po_line.sku_id,
                quantity=qty,
                movement_type="purchase_receive",
                reference_type="purchase_receipt",
                reference_id=receipt.receipt_id,
                created_by=user_id,
            ))

            self._balance_repo.ensure_exists(po_line.sku_id)
            self._balance_repo.atomic_update(po_line.sku_id, qty)

            # 更新 PO 明細已收量
            po_line.received_quantity = (po_line.received_quantity or 0) + qty
            self._po_line_repo.save(po_line)

        # 判斷 PO 狀態
        all_lines_qty = self._qs.get_po_line_quantities(str(po_id))
        all_received = all(l["received_quantity"] >= l["ordered_quantity"] for l in all_lines_qty)
        any_received = any(l["received_quantity"] > 0 for l in all_lines_qty)

        if all_received:
            po.status = "received"
        elif any_received:
            po.status = "partial_received"
        self._po_repo.save(po)

        # Post-transaction best-effort side effects
        self._update_backorder_on_receive(po_id)
        self._check_price_anomaly(po.supplier_id, lines)

        logger.info("po_received", po_id=str(po_id), receipt_id=str(receipt.receipt_id))
        return Result.ok(
            data={"receipt_id": str(receipt.receipt_id)},
            message=f"驗收完成，採購單狀態：{po.status}",
        )

    # ── 一鍵建採購單（低庫存補貨）─────────────────────

    def auto_create_from_low_stock(self) -> Result:
        items = self._qs.low_stock_with_preferred_supplier()
        if not items:
            return Result.fail(ERR_BIZ_001, "沒有需要補貨的品項（或品項尚未設定首選供應商）")

        # 按供應商分組（純邏輯）
        from application.procurement.rules import group_by_supplier
        by_supplier = group_by_supplier(items)

        po_ids = []
        for supplier_id, supplier_lines in by_supplier.items():
            supplier_name = supplier_lines[0]["supplier_name"]
            saved_po = self._po_repo.save(PurchaseOrder(
                supplier_id=UUID(supplier_id),
                status="draft",
                note=f"低庫存自動補貨 — {supplier_name}",
            ))

            for line in supplier_lines:
                qty = max(1, int(line["shortage"]))
                self._po_line_repo.save(PurchaseOrderLine(
                    po_id=saved_po.po_id,
                    sku_id=line["sku_id"],
                    ordered_quantity=qty,
                    unit_cost=float(line["unit_cost"]) if line["unit_cost"] else None,
                ))

            po_ids.append(str(saved_po.po_id))

        logger.info("auto_po_created", count=len(po_ids))
        return Result.ok(
            data={"po_ids": po_ids, "count": len(po_ids)},
            message=f"已自動建立 {len(po_ids)} 張採購單草稿",
        )

    # ── PO 驗收 → 欠貨到貨回寫（best-effort，不影響主交易）────
    def _update_backorder_on_receive(self, po_id: UUID) -> None:
        if not self._backorder_service:
            return

        po_lines = self._qs.get_purchase_order_lines(str(po_id))

        for pol in po_lines:
            sale_line_id = pol.get("source_sale_line_id")
            if not sale_line_id:
                continue
            received = pol.get("received_quantity", 0)
            if received > 0:
                try:
                    self._backorder_service.mark_arrived(
                        UUID(str(sale_line_id)), received, po_id,
                    )
                except Exception:
                    logger.warning(
                        "backorder_update_failed",
                        sale_line_id=str(sale_line_id),
                        exc_info=True,
                    )

    # ── PO 驗收 → 進價異常檢查（best-effort）──────────────
    def _check_price_anomaly(self, supplier_id: UUID, lines: list[dict]) -> None:
        """Constitution 1.2：進價異常 → OperationalAlert(warning)。

        規則：unit_cost > 基準 × 1.2（漲幅超過 20%）。
        基準 = supplier_products.unit_cost。
        """
        if not self._alert_repo:
            return

        for line in lines:
            try:
                cost = line.get("unit_cost")
                if cost is None:
                    continue
                sku_id = line.get("sku_id") or (
                    self._po_line_repo.get_by_id(UUID(line["po_line_id"])).sku_id
                    if line.get("po_line_id") else None
                )
                if not sku_id:
                    continue

                baseline = self._qs.get_supplier_product_cost(str(supplier_id), str(sku_id))
                if baseline is None:
                    continue  # 首次進貨，不觸發

                if float(cost) > baseline * 1.2:
                    self._alert_repo.save(OperationalAlert(
                        alert_type="price_anomaly",
                        severity="warning",
                        title=f"進價異常：SKU {sku_id}",
                        detail=f"本次進價 {cost}，基準 {baseline}，漲幅 {(float(cost)/baseline - 1)*100:.0f}%",
                        reference_type="purchase_order",
                        reference_id=None,
                    ))
            except Exception:
                logger.warning("price_anomaly_check_failed", exc_info=True)
