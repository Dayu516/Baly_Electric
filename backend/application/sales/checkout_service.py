"""CheckoutService — 結帳 use case。

Transaction 邊界（Phase A 開發憲法 1.3）：
  Transaction 內（同步，強一致）：
    INSERT sale
    INSERT sale_lines（N 筆）
    INSERT stock_movements（N 筆，quantity 為負）
    UPDATE inventory_balance（N 筆 SKU 的 current_stock）
    INSERT/UPDATE accounts_receivable（月結客戶）
    INSERT audit_event

  Transaction 外（commit 後，失敗不影響交易）：
    檢查低庫存 → 建立 OperationalAlert
"""

import uuid

from core.logging import get_logger
from core.results import Result
from application.sales.schemas import CheckoutRequest
from application.sales.rules import build_sale_lines, calculate_line_total, calculate_tax
from domain.alert.models import OperationalAlert
from domain.alert.repository import OperationalAlertRepository
from domain.customer.repository import AccountsReceivableRepository, CustomerRepository
from domain.inventory.models import StockMovement
from domain.inventory.repository import InventoryBalanceRepository, StockMovementRepository
from domain.product.repository import SKURepository
from domain.sales.models import Sale
from domain.sales.repository import CustomerPriceHistoryRepository, SaleRepository

logger = get_logger("checkout")


class CheckoutService:
    def __init__(
        self,
        sale_repo: SaleRepository,
        movement_repo: StockMovementRepository,
        balance_repo: InventoryBalanceRepository,
        customer_repo: CustomerRepository | None = None,
        ar_repo: AccountsReceivableRepository | None = None,
        price_history_repo: CustomerPriceHistoryRepository | None = None,
        alert_repo: OperationalAlertRepository | None = None,
        sku_repo: SKURepository | None = None,
    ):
        self._sale_repo = sale_repo
        self._movement_repo = movement_repo
        self._balance_repo = balance_repo
        self._customer_repo = customer_repo
        self._ar_repo = ar_repo
        self._price_history_repo = price_history_repo
        self._alert_repo = alert_repo
        self._sku_repo = sku_repo

    def checkout(
        self,
        request: CheckoutRequest,
        cashier_id: uuid.UUID,
    ) -> Result:
        """執行結帳。所有寫入在同一個 transaction 內。"""

        # 離線冪等檢查
        if request.client_tx_id:
            existing = self._sale_repo.get_by_client_tx_id(request.client_tx_id)
            if existing:
                logger.info("duplicate_checkout_skipped", client_tx_id=request.client_tx_id)
                return Result.ok(
                    data={"sale_id": str(existing.sale_id), "total": existing.total, "status": "already_exists"},
                    message="此交易已存在（冪等檢查）",
                )

        # ── Transaction 內 ────────────────────────────

        # 1. 計算金額
        line_total = sum(
            calculate_line_total(item.unit_price, item.quantity, item.discount_amount)
            for item in request.items
        )
        after_discount = line_total - request.discount_amount
        subtotal, tax_amount, total, tax_included = calculate_tax(after_discount, request.tax_mode)

        # 2. 建立 Sale
        sale = Sale(
            customer_id=request.customer_id,
            cashier_id=cashier_id,
            status="completed",
            payment_method=request.payment_method,
            tax_included=tax_included,
            subtotal=subtotal,
            tax_amount=tax_amount,
            discount_amount=request.discount_amount,
            total=total,
            note=request.note,
            client_tx_id=request.client_tx_id,
        )
        saved_sale = self._sale_repo.save(sale)

        # 3. 建立 SaleLines
        sale_lines = build_sale_lines(saved_sale.sale_id, request.items)
        self._sale_repo.save_lines(sale_lines)

        # 4. 建立 StockMovements + 更新 InventoryBalance
        for item in request.items:
            movement = StockMovement(
                sku_id=item.sku_id,
                quantity=-item.quantity,  # 出庫為負
                movement_type="sale",
                reference_type="sale",
                reference_id=saved_sale.sale_id,
                created_by=cashier_id,
            )
            self._movement_repo.save(movement)
            self._balance_repo.atomic_update(item.sku_id, -item.quantity)

        # 5. 月結客戶累計應收
        if request.payment_method == "monthly_credit" and request.customer_id and self._ar_repo:
            self._accumulate_ar(request.customer_id, total, saved_sale)

        # 6. 更新客戶歷史售價（有客戶時才記）
        if request.customer_id and self._price_history_repo:
            self._update_price_history(request.customer_id, request.items, saved_sale)

        logger.info(
            "checkout_completed",
            sale_id=str(saved_sale.sale_id),
            total=total,
            items=len(request.items),
        )

        return Result.ok(
            data={
                "sale_id": str(saved_sale.sale_id),
                "total": total,
                "status": "completed",
                "item_count": len(request.items),
            },
            message="結帳成功",
        )

    def _accumulate_ar(self, customer_id: uuid.UUID, amount: float, sale: Sale) -> None:
        """月結累計 — Phase A 放 transaction 內，確保不漏算。"""
        from datetime import datetime, timezone
        period = datetime.now(timezone.utc).strftime("%Y-%m")

        ar = self._ar_repo.get_by_customer_period(customer_id, period)
        if ar:
            ar.total_amount += amount
            self._ar_repo.save(ar)
        else:
            from domain.customer.models import AccountsReceivable
            new_ar = AccountsReceivable(
                customer_id=customer_id,
                period=period,
                total_amount=amount,
                status="open",
            )
            self._ar_repo.save(new_ar)

    def _update_price_history(self, customer_id, items, sale):
        """更新客戶歷史售價 — 結帳後自動記錄。"""
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        for item in items:
            self._price_history_repo.upsert(
                customer_id=customer_id,
                sku_id=item.sku_id,
                price=item.unit_price,
                cost=None,
                sold_at=now,
                sale_id=sale.sale_id,
            )

    def check_low_stock(self, items) -> None:
        """Post-transaction best-effort：低庫存建立 OperationalAlert。

        規則：current_stock <= min_stock 時建 alert。
        min_stock 為 None 時 fallback 為 <= 0。
        失敗不影響結帳。
        """
        for item in items:
            try:
                balance = self._balance_repo.get_by_sku(item.sku_id)
                if not balance:
                    continue
                sku = self._sku_repo.get_by_id(item.sku_id)
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
                        reference_id=item.sku_id,
                    ))
            except Exception:
                logger.warning("low_stock_check_failed", sku_id=str(item.sku_id), exc_info=True)
