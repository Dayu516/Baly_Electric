"""CheckoutUseCase + VoidSaleUseCase — 結帳 / 作廢正式流程。

CheckoutUseCase：
  1. Idempotency（client_tx_id，由 CheckoutService 內部處理）
  2. 呼叫 CheckoutService.checkout()
  3. Audit
  4. Commit
  5. Post-commit：low stock alert（去重 + 建立）

VoidSaleUseCase：
  1. 呼叫 VoidSaleService.void()
  2. Audit
  3. Commit
"""

from uuid import UUID

from core.logging import get_logger
from core.results import Result
from domain.alert.models import OperationalAlert
from domain.alert.repository import OperationalAlertRepository
from domain.inventory.repository import InventoryBalanceRepository
from domain.product.repository import SKURepository
from infrastructure.persistence.repositories.audit_repo_impl import AuditService

logger = get_logger("use_case.checkout")


class CheckoutUseCase:
    def __init__(
        self,
        checkout_service,
        audit_service: AuditService,
        alert_repo: OperationalAlertRepository,
        balance_repo: InventoryBalanceRepository,
        sku_repo: SKURepository,
        session,
    ):
        self._checkout = checkout_service
        self._audit = audit_service
        self._alert_repo = alert_repo
        self._balance_repo = balance_repo
        self._sku_repo = sku_repo
        self._session = session

    def execute(self, request, cashier_id: UUID) -> Result:
        # 1. 呼叫 service（idempotency 在 service 內部處理）
        result = self._checkout.checkout(request, cashier_id)
        if not result.success:
            return result

        # 2. Audit
        self._audit.log(
            cashier_id, "checkout", "sale",
            entity_id=UUID(result.data["sale_id"]) if result.data else None,
            detail=result.data,
        )

        # 3. Commit
        self._session.commit()

        # 4. Post-commit：low stock alert（去重）
        if result.data and result.data.get("status") != "already_exists":
            self._check_low_stock(request.items)

        return result

    def _check_low_stock(self, items) -> None:
        """Post-commit best-effort：低庫存 alert 去重建立。

        規則：
          - current_stock <= min_stock 時檢查
          - 已有 active alert（同 SKU + low_stock + is_read=false） → 不重建
          - 無 active → 建立新 alert
          - min_stock 為 None 時 fallback 為 <= 0

        NOTE: Phase B 應拆分 read_status 與 resolution_status，避免語意混淆。
              目前沿用 is_read=false 當 active、is_read=true 當 resolved。
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
                    # 去重：檢查是否已有 active alert
                    active = self._alert_repo.list_active_by_reference("sku", item.sku_id, "low_stock")
                    if active:
                        continue  # 已有 active alert，不重建

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


class VoidSaleUseCase:
    def __init__(self, void_service, audit_service: AuditService, session):
        self._void = void_service
        self._audit = audit_service
        self._session = session

    def execute(self, sale_id: UUID, user_id: UUID, reason: str | None = None) -> Result:
        # 1. 呼叫 service
        result = self._void.void(sale_id, user_id, reason)
        if not result.success:
            return result

        # 2. Audit
        self._audit.log(
            user_id, "void_sale", "sale",
            entity_id=sale_id,
            detail={"reason": reason},
        )

        # 3. Commit
        self._session.commit()

        return result
