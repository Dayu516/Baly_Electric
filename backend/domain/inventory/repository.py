from abc import ABC, abstractmethod
from typing import Optional
from uuid import UUID

from domain.inventory.models import InventoryBalance, StockMovement


class StockMovementRepository(ABC):
    @abstractmethod
    def save(self, movement: StockMovement) -> StockMovement: ...

    @abstractmethod
    def list_by_sku(self, sku_id: UUID, offset: int = 0, limit: int = 50) -> list[StockMovement]: ...

    @abstractmethod
    def list_by_reference(self, reference_type: str, reference_id: UUID) -> list[StockMovement]: ...


class InventoryBalanceRepository(ABC):
    @abstractmethod
    def get_by_sku(self, sku_id: UUID) -> Optional[InventoryBalance]: ...

    @abstractmethod
    def atomic_update(self, sku_id: UUID, qty_delta: int) -> None:
        """DB 層 atomic update: current_stock = current_stock + qty_delta"""
        ...

    @abstractmethod
    def ensure_exists(self, sku_id: UUID) -> None:
        """確保 sku_id 有 balance 紀錄（初始 0）"""
        ...

    @abstractmethod
    def set_stock(self, sku_id: UUID, stock: int) -> None:
        """絕對值覆寫 current_stock + 更新 last_recalc_at。僅限重算流程使用。"""
        ...
