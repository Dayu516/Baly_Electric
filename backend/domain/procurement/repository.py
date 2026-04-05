"""Procurement domain repository interfaces."""

from abc import ABC, abstractmethod
from typing import Optional
from uuid import UUID

from domain.procurement.models import (
    PurchaseInquiry,
    PurchaseInquiryLine,
    PurchaseInquiryQuote,
    PurchaseOrder,
    PurchaseOrderLine,
    PurchaseReceipt,
    PurchaseReceiptLine,
    SalesQuotation,
    SalesQuotationLine,
    Supplier,
    SupplierPriceQuote,
)


class SupplierRepository(ABC):
    @abstractmethod
    def get_by_id(self, supplier_id: UUID) -> Optional[Supplier]: ...

    @abstractmethod
    def save(self, supplier: Supplier) -> Supplier: ...

    @abstractmethod
    def list_all(self) -> list[Supplier]: ...


class PurchaseOrderRepository(ABC):
    @abstractmethod
    def get_by_id(self, po_id: UUID) -> Optional[PurchaseOrder]: ...

    @abstractmethod
    def save(self, po: PurchaseOrder) -> PurchaseOrder: ...

    @abstractmethod
    def delete(self, po_id: UUID) -> None: ...


class PurchaseOrderLineRepository(ABC):
    @abstractmethod
    def get_by_id(self, po_line_id: UUID) -> Optional[PurchaseOrderLine]: ...

    @abstractmethod
    def save(self, line: PurchaseOrderLine) -> PurchaseOrderLine: ...

    @abstractmethod
    def delete_by_po(self, po_id: UUID) -> None: ...


class PurchaseReceiptRepository(ABC):
    @abstractmethod
    def save(self, receipt: PurchaseReceipt) -> PurchaseReceipt: ...


class PurchaseReceiptLineRepository(ABC):
    @abstractmethod
    def save(self, line: PurchaseReceiptLine) -> PurchaseReceiptLine: ...


class InquiryRepository(ABC):
    @abstractmethod
    def get_by_id(self, inquiry_id: UUID) -> Optional[PurchaseInquiry]: ...

    @abstractmethod
    def save(self, inquiry: PurchaseInquiry) -> PurchaseInquiry: ...

    @abstractmethod
    def delete(self, inquiry_id: UUID) -> None: ...


class InquiryLineRepository(ABC):
    @abstractmethod
    def get_by_id(self, line_id: UUID) -> Optional[PurchaseInquiryLine]: ...

    @abstractmethod
    def save(self, line: PurchaseInquiryLine) -> PurchaseInquiryLine: ...


class InquiryQuoteRepository(ABC):
    @abstractmethod
    def save(self, quote: PurchaseInquiryQuote) -> PurchaseInquiryQuote: ...


class SupplierPriceQuoteRepository(ABC):
    @abstractmethod
    def save(self, quote: SupplierPriceQuote) -> SupplierPriceQuote: ...


class QuotationRepository(ABC):
    @abstractmethod
    def get_by_id(self, quotation_id: UUID) -> Optional[SalesQuotation]: ...

    @abstractmethod
    def save(self, quotation: SalesQuotation) -> SalesQuotation: ...

    @abstractmethod
    def delete(self, quotation_id: UUID) -> None: ...


class QuotationLineRepository(ABC):
    @abstractmethod
    def save(self, line: SalesQuotationLine) -> SalesQuotationLine: ...
