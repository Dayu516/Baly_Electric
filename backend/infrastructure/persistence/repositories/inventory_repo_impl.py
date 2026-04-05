"""Inventory repository 實作 — 含 InventoryBalance atomic update（架構例外）。"""

from typing import Optional
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from domain.inventory.models import InventoryBalance, StockMovement
from domain.inventory.repository import InventoryBalanceRepository, StockMovementRepository
from infrastructure.persistence.orm_models import InventoryBalanceORM, StockMovementORM


class SqlStockMovementRepository(StockMovementRepository):
    def __init__(self, session: Session):
        self._session = session

    def save(self, movement: StockMovement) -> StockMovement:
        orm = StockMovementORM(
            movement_id=movement.movement_id,
            sku_id=movement.sku_id,
            quantity=movement.quantity,
            movement_type=movement.movement_type,
            reference_type=movement.reference_type,
            reference_id=movement.reference_id,
            note=movement.note,
            created_by=movement.created_by,
        )
        self._session.add(orm)
        self._session.flush()
        return movement

    def list_by_sku(self, sku_id: UUID, offset: int = 0, limit: int = 50) -> list[StockMovement]:
        orms = (
            self._session.query(StockMovementORM)
            .filter(StockMovementORM.sku_id == sku_id)
            .order_by(StockMovementORM.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return [self._to_domain(o) for o in orms]

    def list_by_reference(self, reference_type: str, reference_id: UUID) -> list[StockMovement]:
        orms = (
            self._session.query(StockMovementORM)
            .filter(
                StockMovementORM.reference_type == reference_type,
                StockMovementORM.reference_id == reference_id,
            )
            .all()
        )
        return [self._to_domain(o) for o in orms]

    @staticmethod
    def _to_domain(orm: StockMovementORM) -> StockMovement:
        return StockMovement(
            movement_id=orm.movement_id,
            sku_id=orm.sku_id,
            quantity=orm.quantity,
            movement_type=orm.movement_type,
            reference_type=orm.reference_type,
            reference_id=orm.reference_id,
            note=orm.note,
            created_by=orm.created_by,
            created_at=orm.created_at,
        )


class SqlInventoryBalanceRepository(InventoryBalanceRepository):
    def __init__(self, session: Session):
        self._session = session

    def get_by_sku(self, sku_id: UUID) -> Optional[InventoryBalance]:
        orm = self._session.get(InventoryBalanceORM, sku_id)
        if not orm:
            return None
        return InventoryBalance(
            sku_id=orm.sku_id,
            current_stock=orm.current_stock,
            last_recalc_at=orm.last_recalc_at,
        )

    def atomic_update(self, sku_id: UUID, qty_delta: int) -> None:
        """DB 層 atomic update — 避免 race condition。

        這是 Phase A 唯一允許在 repository 寫原生 SQL 的地方（架構例外）。
        """
        self._session.execute(
            text("""
                UPDATE inventory_balances
                SET current_stock = current_stock + :qty,
                    updated_at = NOW()
                WHERE sku_id = :sku_id
            """),
            {"qty": qty_delta, "sku_id": str(sku_id)},
        )

    def ensure_exists(self, sku_id: UUID) -> None:
        existing = self._session.get(InventoryBalanceORM, sku_id)
        if not existing:
            orm = InventoryBalanceORM(sku_id=sku_id, current_stock=0)
            self._session.add(orm)
            self._session.flush()

    def set_stock(self, sku_id: UUID, stock: int) -> None:
        """絕對值覆寫 current_stock — 僅限重算流程使用。"""
        self._session.execute(
            text("""
                UPDATE inventory_balances
                SET current_stock = :stock, last_recalc_at = NOW(), updated_at = NOW()
                WHERE sku_id = :sku_id
            """),
            {"stock": stock, "sku_id": str(sku_id)},
        )
