"""QuotationService — 報價單完整流程 use case。

流程：建立報價 → 送出 → 客戶確認 → 轉銷貨結帳。

依賴：
  - QuotationRepository / LineRepository（報價寫入）
  - SaleRepository / StockMovementRepository / InventoryBalanceRepository（轉銷貨）
  - ProcurementQueryService（查詢）
"""

from datetime import datetime, timezone
from uuid import UUID

from core.errors import ERR_BIZ_001, ERR_BIZ_002
from core.logging import get_logger
from core.results import Result
from domain.alert.models import OperationalAlert
from domain.alert.repository import OperationalAlertRepository
from domain.inventory.models import StockMovement
from domain.inventory.repository import InventoryBalanceRepository, StockMovementRepository
from domain.product.repository import SKURepository
from domain.procurement.models import SalesQuotation, SalesQuotationLine
from domain.procurement.repository import QuotationLineRepository, QuotationRepository
from domain.sales.models import Sale
from domain.sales.repository import SaleRepository
from infrastructure.persistence.query_services.procurement_query_service import ProcurementQueryService

logger = get_logger("quotation")


class QuotationService:
    def __init__(
        self,
        quotation_repo: QuotationRepository,
        quotation_line_repo: QuotationLineRepository,
        sale_repo: SaleRepository,
        movement_repo: StockMovementRepository,
        balance_repo: InventoryBalanceRepository,
        query_service: ProcurementQueryService,
        alert_repo: OperationalAlertRepository | None = None,
        sku_repo: SKURepository | None = None,
    ):
        self._q_repo = quotation_repo
        self._ql_repo = quotation_line_repo
        self._sale_repo = sale_repo
        self._movement_repo = movement_repo
        self._balance_repo = balance_repo
        self._qs = query_service
        self._alert_repo = alert_repo
        self._sku_repo = sku_repo

    # ── 查詢 ──────────────────────────────────────────

    def list_quotations(self, *, status: str | None, keyword: str | None = None,
                          date_from: str | None = None, date_to: str | None = None,
                          page: int, per_page: int) -> Result:
        offset = (page - 1) * per_page
        rows = self._qs.list_quotations(status=status, keyword=keyword,
                                         date_from=date_from, date_to=date_to,
                                         offset=offset, limit=per_page)
        data = [
            {
                "quotation_id": str(r["quotation_id"]),
                "customer_id": str(r["customer_id"]) if r["customer_id"] else None,
                "customer_name": r["customer_name"],
                "title": r["title"],
                "status": r["status"],
                "valid_until": r["valid_until"].isoformat() if r["valid_until"] else None,
                "note": r["note"],
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
                "line_count": r["line_count"],
                "total_amount": float(r["total_amount"]),
            }
            for r in rows
        ]
        return Result.ok(data=data)

    def get_quotation(self, quotation_id: UUID) -> Result:
        header = self._qs.get_quotation_detail(str(quotation_id))
        if not header:
            return Result.fail(ERR_BIZ_002, "報價單不存在")

        lines = self._qs.get_quotation_lines(str(quotation_id))
        data = {
            "quotation_id": str(header["quotation_id"]),
            "customer_id": str(header["customer_id"]) if header["customer_id"] else None,
            "customer_name": header["customer_name"],
            "title": header["title"],
            "status": header["status"],
            "valid_until": header["valid_until"].isoformat() if header["valid_until"] else None,
            "note": header["note"],
            "created_at": header["created_at"].isoformat() if header["created_at"] else None,
            "lines": [
                {
                    "line_id": str(l["line_id"]),
                    "sku_id": str(l["sku_id"]),
                    "product_name": l["product_name"],
                    "brand": l["brand"],
                    "spec": l["spec"],
                    "unit": l["unit"],
                    "quantity": l["quantity"],
                    "unit_price": float(l["unit_price"]),
                    "note": l["note"],
                }
                for l in lines
            ],
        }
        return Result.ok(data=data)

    # ── 建單 ──────────────────────────────────────────

    def create_quotation(
        self, customer_id: str | None, title: str, valid_until: str | None,
        note: str | None, lines: list[dict], user_id: UUID,
    ) -> Result:
        valid_dt = None
        if valid_until:
            try:
                valid_dt = datetime.fromisoformat(valid_until)
            except ValueError:
                pass

        now = datetime.now(timezone.utc)
        q = self._q_repo.save(SalesQuotation(
            customer_id=UUID(customer_id) if customer_id else None,
            title=title, status="draft", valid_until=valid_dt, note=note,
            created_by=user_id, created_at=now, updated_at=now,
        ))

        for line in lines:
            self._ql_repo.save(SalesQuotationLine(
                quotation_id=q.quotation_id,
                sku_id=UUID(line["sku_id"]),
                quantity=line["quantity"],
                unit_price=line["unit_price"],
                note=line.get("note"),
            ))

        logger.info("quotation_created", quotation_id=str(q.quotation_id))
        return Result.ok(data={"quotation_id": str(q.quotation_id)}, message="報價單已建立")

    # ── 新增品項 ──────────────────────────────────────

    def add_line(
        self, quotation_id: UUID, sku_id: str, quantity: int, unit_price: float, note: str | None,
    ) -> Result:
        q = self._q_repo.get_by_id(quotation_id)
        if not q:
            return Result.fail(ERR_BIZ_002, "報價單不存在")
        if q.status not in ("draft", "sent"):
            return Result.fail(ERR_BIZ_001, "此狀態無法新增品項")

        self._ql_repo.save(SalesQuotationLine(
            quotation_id=quotation_id, sku_id=UUID(sku_id),
            quantity=quantity, unit_price=unit_price, note=note,
        ))
        return Result.ok(message="品項已加入報價單")

    # ── 狀態轉換 ──────────────────────────────────────

    def send_quotation(self, quotation_id: UUID) -> Result:
        q = self._q_repo.get_by_id(quotation_id)
        if not q:
            return Result.fail(ERR_BIZ_002, "報價單不存在")
        q.status = "sent"
        q.updated_at = datetime.now(timezone.utc)
        self._q_repo.save(q)
        return Result.ok(message="報價單已標記為已送出")

    def accept_quotation(self, quotation_id: UUID) -> Result:
        q = self._q_repo.get_by_id(quotation_id)
        if not q:
            return Result.fail(ERR_BIZ_002, "報價單不存在")
        q.status = "accepted"
        q.updated_at = datetime.now(timezone.utc)
        self._q_repo.save(q)
        return Result.ok(message="客戶已確認")

    def cancel_quotation(self, quotation_id: UUID) -> Result:
        q = self._q_repo.get_by_id(quotation_id)
        if not q:
            return Result.fail(ERR_BIZ_002, "報價單不存在")
        q.status = "cancelled"
        q.updated_at = datetime.now(timezone.utc)
        self._q_repo.save(q)
        return Result.ok(message="報價單已取消")

    # ── 轉銷貨結帳 ────────────────────────────────────

    def convert_to_sale(self, quotation_id: UUID, user_id: UUID) -> Result:
        q = self._q_repo.get_by_id(quotation_id)
        if not q:
            return Result.fail(ERR_BIZ_002, "報價單不存在")
        if q.status not in ("accepted", "sent", "draft"):
            return Result.fail(ERR_BIZ_001, f"狀態 {q.status} 無法轉單")

        lines = self._qs.get_quotation_lines_for_convert(str(quotation_id))
        if not lines:
            return Result.fail(ERR_BIZ_001, "報價單沒有明細")

        # 純計算
        from application.procurement.rules import (
            build_sale_lines_from_quotation,
            calculate_subtotal,
            determine_payment_method,
        )
        subtotal = calculate_subtotal(lines)
        payment_method = determine_payment_method(q.customer_id)

        # 建立 Sale
        sale = Sale(
            customer_id=q.customer_id,
            cashier_id=user_id,
            status="completed",
            payment_method=payment_method,
            tax_included=False,
            subtotal=subtotal,
            tax_amount=0,
            total=subtotal,
            note=f"來自報價單: {q.title}",
        )
        saved_sale = self._sale_repo.save(sale)

        # 建立 SaleLines
        sale_lines = build_sale_lines_from_quotation(saved_sale.sale_id, lines)
        self._sale_repo.save_lines(sale_lines)

        # 扣庫存
        for l in lines:
            self._movement_repo.save(StockMovement(
                sku_id=l["sku_id"],
                quantity=-l["quantity"],
                movement_type="sale",
                reference_type="sale",
                reference_id=saved_sale.sale_id,
                created_by=user_id,
            ))
            self._balance_repo.atomic_update(l["sku_id"], -l["quantity"])

        q.status = "converted"
        q.updated_at = datetime.now(timezone.utc)
        self._q_repo.save(q)

        logger.info("quotation_converted", quotation_id=str(quotation_id), sale_id=str(saved_sale.sale_id))
        return Result.ok(
            data={
                "sale_id": str(saved_sale.sale_id),
                "total": subtotal,
                "sku_ids": [str(l["sku_id"]) for l in lines],
            },
            message=f"已轉成銷貨單，金額 ${subtotal:.0f}",
        )

    def check_low_stock(self, sku_ids: list[str]) -> None:
        """Post-commit best-effort：低庫存建立 OperationalAlert（Constitution 1.2）。"""
        if not self._alert_repo or not self._sku_repo:
            return
        for sid in sku_ids:
            try:
                sku_uuid = UUID(sid)
                balance = self._balance_repo.get_by_sku(sku_uuid)
                if not balance:
                    continue
                sku = self._sku_repo.get_by_id(sku_uuid)
                if not sku:
                    continue
                threshold = sku.min_stock if sku.min_stock is not None else 0
                if balance.current_stock <= threshold:
                    self._alert_repo.save(OperationalAlert(
                        alert_type="low_stock",
                        severity="warning",
                        title=f"低庫存警告：{sku.brand or ''} {sku.spec or ''}",
                        detail=f"目前庫存 {balance.current_stock}，安全庫存 {threshold}",
                        reference_type="sku",
                        reference_id=sku_uuid,
                    ))
            except Exception:
                logger.warning("low_stock_check_failed", sku_id=sid, exc_info=True)

    def delete_quotation(self, quotation_id: UUID) -> Result:
        q = self._q_repo.get_by_id(quotation_id)
        if not q:
            return Result.fail(ERR_BIZ_002, "報價單不存在")
        if q.status != "cancelled":
            return Result.fail(ERR_BIZ_001, "只有已取消的報價單可以刪除")
        self._q_repo.delete(quotation_id)
        logger.info("quotation_deleted", quotation_id=str(quotation_id))
        return Result.ok(message="報價單已刪除")


