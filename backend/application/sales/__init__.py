"""Sales 模���組裝入口。

所有 Sales service 的建立都透過���裡，API 層不��自行組裝 repo��

Usage（API 層）：
    from application.sales import build_checkout_service, build_void_sale_service, build_backorder_service
    svc = build_checkout_service(session)
"""

from sqlalchemy.orm import Session

from application.sales.backorder_service import BackorderService
from application.sales.checkout_service import CheckoutService
from application.sales.void_sale_service import VoidSaleService
from infrastructure.persistence.repositories.customer_repo_impl import (
    SqlAccountsReceivableRepository,
    SqlCustomerRepository,
)
from infrastructure.persistence.repositories.inventory_repo_impl import (
    SqlInventoryBalanceRepository,
    SqlStockMovementRepository,
)
from infrastructure.persistence.repositories.alert_repo_impl import SqlOperationalAlertRepository
from infrastructure.persistence.repositories.product_repo_impl import SqlSKURepository
from infrastructure.persistence.repositories.sales_repo_impl import (
    SqlCustomerPickupNotificationRepository,
    SqlCustomerPriceHistoryRepository,
    SqlSaleLineFulfillmentRepository,
    SqlSaleLineRepository,
    SqlSaleRepository,
)


def build_checkout_service(session: Session) -> CheckoutService:
    return CheckoutService(
        sale_repo=SqlSaleRepository(session),
        movement_repo=SqlStockMovementRepository(session),
        balance_repo=SqlInventoryBalanceRepository(session),
        customer_repo=SqlCustomerRepository(session),
        ar_repo=SqlAccountsReceivableRepository(session),
        price_history_repo=SqlCustomerPriceHistoryRepository(session),
        alert_repo=SqlOperationalAlertRepository(session),
        sku_repo=SqlSKURepository(session),
    )


def build_void_sale_service(session: Session) -> VoidSaleService:
    return VoidSaleService(
        sale_repo=SqlSaleRepository(session),
        movement_repo=SqlStockMovementRepository(session),
        balance_repo=SqlInventoryBalanceRepository(session),
        ar_repo=SqlAccountsReceivableRepository(session),
    )


def build_backorder_service(session: Session) -> BackorderService:
    return BackorderService(
        sale_repo=SqlSaleRepository(session),
        sale_line_repo=SqlSaleLineRepository(session),
        fulfillment_repo=SqlSaleLineFulfillmentRepository(session),
        notification_repo=SqlCustomerPickupNotificationRepository(session),
        movement_repo=SqlStockMovementRepository(session),
        balance_repo=SqlInventoryBalanceRepository(session),
        alert_repo=SqlOperationalAlertRepository(session),
    )


def build_sales_query_service(session: Session):
    from infrastructure.persistence.query_services.sales_query_service import SalesQueryService
    return SalesQueryService(session)


def build_sale_repository(session: Session):
    return SqlSaleRepository(session)
