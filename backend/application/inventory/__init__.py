"""Inventory 模組組裝入口。

所有 Inventory service 的建立都透過這裡，API 層不可自行組裝 repo。

Usage（API 層）：
    from application.inventory import build_receive_stock_service, build_stock_count_service, build_stock_recalc_service
    svc = build_receive_stock_service(session)
"""

from sqlalchemy.orm import Session

from application.inventory.receive_stock_service import ReceiveStockService
from application.inventory.stock_count_service import StockCountService
from application.inventory.stock_recalc_service import StockRecalcService
from infrastructure.persistence.query_services.inventory_query_service import InventoryQueryService
from infrastructure.persistence.repositories.alert_repo_impl import SqlOperationalAlertRepository
from infrastructure.persistence.repositories.inventory_repo_impl import (
    SqlInventoryBalanceRepository,
    SqlStockMovementRepository,
)
from infrastructure.persistence.repositories.review_repo_impl import SqlReviewTaskRepository


def build_receive_stock_service(session: Session) -> ReceiveStockService:
    return ReceiveStockService(
        movement_repo=SqlStockMovementRepository(session),
        balance_repo=SqlInventoryBalanceRepository(session),
    )


def build_stock_count_service(session: Session) -> StockCountService:
    return StockCountService(
        balance_repo=SqlInventoryBalanceRepository(session),
        movement_repo=SqlStockMovementRepository(session),
        review_repo=SqlReviewTaskRepository(session),
    )


def build_stock_recalc_service(session: Session) -> StockRecalcService:
    return StockRecalcService(
        query_service=InventoryQueryService(session),
        balance_repo=SqlInventoryBalanceRepository(session),
        alert_repo=SqlOperationalAlertRepository(session),
    )


def build_inventory_query_service(session: Session):
    return InventoryQueryService(session)


def build_stock_movement_repository(session: Session):
    return SqlStockMovementRepository(session)


def build_inventory_balance_repository(session: Session):
    return SqlInventoryBalanceRepository(session)
