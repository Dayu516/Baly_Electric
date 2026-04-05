from abc import ABC, abstractmethod
from typing import Optional
from uuid import UUID

from domain.customer.models import AccountsReceivable, Customer


class CustomerRepository(ABC):
    @abstractmethod
    def get_by_id(self, customer_id: UUID) -> Optional[Customer]: ...

    @abstractmethod
    def save(self, customer: Customer) -> Customer: ...

    @abstractmethod
    def list_all(self, offset: int = 0, limit: int = 20) -> list[Customer]: ...


class AccountsReceivableRepository(ABC):
    @abstractmethod
    def get_by_id(self, ar_id: UUID) -> Optional[AccountsReceivable]: ...

    @abstractmethod
    def save(self, ar: AccountsReceivable) -> AccountsReceivable: ...

    @abstractmethod
    def get_by_customer_period(self, customer_id: UUID, period: str) -> Optional[AccountsReceivable]: ...
