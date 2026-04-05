from abc import ABC, abstractmethod
from typing import Optional
from uuid import UUID

from domain.sales.models import (
    CustomerPickupNotification,
    Sale,
    SaleLine,
    SaleLineFulfillment,
)


class SaleRepository(ABC):
    @abstractmethod
    def get_by_id(self, sale_id: UUID) -> Optional[Sale]: ...

    @abstractmethod
    def save(self, sale: Sale) -> Sale: ...

    @abstractmethod
    def save_lines(self, lines: list[SaleLine]) -> None: ...

    @abstractmethod
    def get_by_client_tx_id(self, client_tx_id: str) -> Optional[Sale]: ...

    @abstractmethod
    def delete_with_children(self, sale_id: UUID) -> None:
        """刪除 sale 及其所有子表資料（fulfillments, notifications, lines）。"""
        ...


class SaleLineRepository(ABC):
    @abstractmethod
    def get_by_id(self, sale_line_id: UUID) -> Optional[SaleLine]: ...

    @abstractmethod
    def save(self, line: SaleLine) -> SaleLine: ...

    @abstractmethod
    def list_by_sale_id(self, sale_id: UUID) -> list[SaleLine]: ...


class SaleLineFulfillmentRepository(ABC):
    @abstractmethod
    def save(self, fulfillment: SaleLineFulfillment) -> SaleLineFulfillment: ...

    @abstractmethod
    def list_by_sale_line_id(self, sale_line_id: UUID) -> list[SaleLineFulfillment]: ...

    @abstractmethod
    def list_by_sale_line_and_source(
        self, sale_line_id: UUID, source_doc_id: UUID,
    ) -> list[SaleLineFulfillment]: ...


class CustomerPickupNotificationRepository(ABC):
    @abstractmethod
    def save(self, notification: CustomerPickupNotification) -> CustomerPickupNotification: ...


class CustomerPriceHistoryRepository(ABC):
    @abstractmethod
    def upsert(
        self, customer_id: UUID, sku_id: UUID,
        price: float, cost: float | None,
        sold_at, sale_id: UUID,
    ) -> None:
        """INSERT ... ON CONFLICT UPDATE 客戶歷史售價。"""
        ...
