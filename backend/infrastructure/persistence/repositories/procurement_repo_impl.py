"""Procurement repository implementations."""

from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

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
from domain.procurement.repository import (
    InquiryLineRepository,
    InquiryQuoteRepository,
    InquiryRepository,
    PurchaseOrderLineRepository,
    PurchaseOrderRepository,
    PurchaseReceiptLineRepository,
    PurchaseReceiptRepository,
    QuotationLineRepository,
    QuotationRepository,
    SupplierPriceQuoteRepository,
    SupplierRepository,
)
from infrastructure.persistence.orm_models import (
    PurchaseInquiryLineORM,
    PurchaseInquiryORM,
    PurchaseInquiryQuoteORM,
    PurchaseOrderLineORM,
    PurchaseOrderORM,
    PurchaseReceiptLineORM,
    PurchaseReceiptORM,
    SalesQuotationLineORM,
    SalesQuotationORM,
    SupplierORM,
    SupplierPriceQuoteORM,
)


class SqlPurchaseOrderRepository(PurchaseOrderRepository):
    def __init__(self, session: Session):
        self._session = session

    def get_by_id(self, po_id: UUID) -> Optional[PurchaseOrder]:
        orm = self._session.get(PurchaseOrderORM, po_id)
        return self._to_domain(orm) if orm else None

    def save(self, po: PurchaseOrder) -> PurchaseOrder:
        existing = self._session.get(PurchaseOrderORM, po.po_id)
        if existing:
            existing.supplier_id = po.supplier_id
            existing.status = po.status
            existing.note = po.note
            existing.ordered_at = po.ordered_at
            self._session.flush()
            return self._to_domain(existing)

        orm = PurchaseOrderORM(
            po_id=po.po_id,
            supplier_id=po.supplier_id,
            status=po.status,
            note=po.note,
            ordered_at=po.ordered_at,
        )
        self._session.add(orm)
        self._session.flush()
        return self._to_domain(orm)

    def delete(self, po_id: UUID) -> None:
        orm = self._session.get(PurchaseOrderORM, po_id)
        if orm:
            self._session.delete(orm)
            self._session.flush()

    @staticmethod
    def _to_domain(orm: PurchaseOrderORM) -> PurchaseOrder:
        return PurchaseOrder(
            po_id=orm.po_id,
            supplier_id=orm.supplier_id,
            status=orm.status,
            note=orm.note,
            ordered_at=orm.ordered_at,
        )


class SqlPurchaseOrderLineRepository(PurchaseOrderLineRepository):
    def __init__(self, session: Session):
        self._session = session

    def get_by_id(self, po_line_id: UUID) -> Optional[PurchaseOrderLine]:
        orm = self._session.get(PurchaseOrderLineORM, po_line_id)
        return self._to_domain(orm) if orm else None

    def save(self, line: PurchaseOrderLine) -> PurchaseOrderLine:
        existing = self._session.get(PurchaseOrderLineORM, line.po_line_id)
        if existing:
            existing.po_id = line.po_id
            existing.sku_id = line.sku_id
            existing.ordered_quantity = line.ordered_quantity
            existing.received_quantity = line.received_quantity
            existing.unit_cost = line.unit_cost
            self._session.flush()
            return self._to_domain(existing)

        orm = PurchaseOrderLineORM(
            po_line_id=line.po_line_id,
            po_id=line.po_id,
            sku_id=line.sku_id,
            ordered_quantity=line.ordered_quantity,
            received_quantity=line.received_quantity,
            unit_cost=line.unit_cost,
        )
        self._session.add(orm)
        self._session.flush()
        return self._to_domain(orm)

    def delete_by_po(self, po_id: UUID) -> None:
        self._session.query(PurchaseOrderLineORM).filter(
            PurchaseOrderLineORM.po_id == po_id
        ).delete()
        self._session.flush()

    @staticmethod
    def _to_domain(orm: PurchaseOrderLineORM) -> PurchaseOrderLine:
        return PurchaseOrderLine(
            po_line_id=orm.po_line_id,
            po_id=orm.po_id,
            sku_id=orm.sku_id,
            ordered_quantity=orm.ordered_quantity,
            received_quantity=orm.received_quantity,
            unit_cost=float(orm.unit_cost) if orm.unit_cost else None,
        )


class SqlPurchaseReceiptRepository(PurchaseReceiptRepository):
    def __init__(self, session: Session):
        self._session = session

    def save(self, receipt: PurchaseReceipt) -> PurchaseReceipt:
        orm = PurchaseReceiptORM(
            receipt_id=receipt.receipt_id,
            po_id=receipt.po_id,
            supplier_id=receipt.supplier_id,
            received_by=receipt.received_by,
            note=receipt.note,
        )
        self._session.add(orm)
        self._session.flush()
        return PurchaseReceipt(
            receipt_id=orm.receipt_id,
            po_id=orm.po_id,
            supplier_id=orm.supplier_id,
            received_by=orm.received_by,
            note=orm.note,
        )


class SqlPurchaseReceiptLineRepository(PurchaseReceiptLineRepository):
    def __init__(self, session: Session):
        self._session = session

    def save(self, line: PurchaseReceiptLine) -> PurchaseReceiptLine:
        orm = PurchaseReceiptLineORM(
            receipt_line_id=line.receipt_line_id,
            receipt_id=line.receipt_id,
            sku_id=line.sku_id,
            quantity=line.quantity,
            unit_cost=line.unit_cost,
        )
        self._session.add(orm)
        self._session.flush()
        return line


# ═══════════════════════════════════════════════════════════
# Inquiry
# ═══════════════════════════════════════════════════════════

class SqlInquiryRepository(InquiryRepository):
    def __init__(self, session: Session):
        self._session = session

    def get_by_id(self, inquiry_id: UUID) -> Optional[PurchaseInquiry]:
        orm = self._session.get(PurchaseInquiryORM, inquiry_id)
        if not orm:
            return None
        return PurchaseInquiry(
            inquiry_id=orm.inquiry_id, title=orm.title, status=orm.status,
            note=orm.note, created_by=orm.created_by,
            created_at=orm.created_at, updated_at=orm.updated_at,
        )

    def save(self, inquiry: PurchaseInquiry) -> PurchaseInquiry:
        existing = self._session.get(PurchaseInquiryORM, inquiry.inquiry_id)
        if existing:
            existing.title = inquiry.title
            existing.status = inquiry.status
            existing.note = inquiry.note
            existing.updated_at = inquiry.updated_at
            self._session.flush()
            return inquiry

        orm = PurchaseInquiryORM(
            inquiry_id=inquiry.inquiry_id, title=inquiry.title,
            status=inquiry.status, note=inquiry.note,
            created_by=inquiry.created_by,
            created_at=inquiry.created_at, updated_at=inquiry.updated_at,
        )
        self._session.add(orm)
        self._session.flush()
        return PurchaseInquiry(
            inquiry_id=orm.inquiry_id, title=orm.title, status=orm.status,
            note=orm.note, created_by=orm.created_by,
            created_at=orm.created_at, updated_at=orm.updated_at,
        )

    def delete(self, inquiry_id: UUID) -> None:
        # 刪除關聯（quotes → lines → inquiry）
        self._session.query(PurchaseInquiryQuoteORM).filter(
            PurchaseInquiryQuoteORM.inquiry_id == inquiry_id).delete()
        self._session.query(PurchaseInquiryLineORM).filter(
            PurchaseInquiryLineORM.inquiry_id == inquiry_id).delete()
        orm = self._session.get(PurchaseInquiryORM, inquiry_id)
        if orm:
            self._session.delete(orm)
        self._session.flush()


class SqlInquiryLineRepository(InquiryLineRepository):
    def __init__(self, session: Session):
        self._session = session

    def get_by_id(self, line_id: UUID) -> Optional[PurchaseInquiryLine]:
        orm = self._session.get(PurchaseInquiryLineORM, line_id)
        if not orm:
            return None
        return PurchaseInquiryLine(
            line_id=orm.line_id, inquiry_id=orm.inquiry_id,
            sku_id=orm.sku_id, quantity=orm.quantity, note=orm.note,
        )

    def save(self, line: PurchaseInquiryLine) -> PurchaseInquiryLine:
        orm = PurchaseInquiryLineORM(
            line_id=line.line_id, inquiry_id=line.inquiry_id,
            sku_id=line.sku_id, quantity=line.quantity, note=line.note,
        )
        self._session.add(orm)
        self._session.flush()
        return line


class SqlInquiryQuoteRepository(InquiryQuoteRepository):
    def __init__(self, session: Session):
        self._session = session

    def save(self, quote: PurchaseInquiryQuote) -> PurchaseInquiryQuote:
        orm = PurchaseInquiryQuoteORM(
            quote_id=quote.quote_id, inquiry_id=quote.inquiry_id,
            line_id=quote.line_id, supplier_id=quote.supplier_id,
            unit_price=quote.unit_price, note=quote.note,
            is_selected=quote.is_selected, created_at=quote.created_at,
        )
        self._session.add(orm)
        self._session.flush()
        return quote


class SqlSupplierPriceQuoteRepository(SupplierPriceQuoteRepository):
    def __init__(self, session: Session):
        self._session = session

    def save(self, quote: SupplierPriceQuote) -> SupplierPriceQuote:
        orm = SupplierPriceQuoteORM(
            supplier_id=quote.supplier_id, sku_id=quote.sku_id,
            unit_price=quote.unit_price, quoted_at=quote.quoted_at,
            note=quote.note, created_by=quote.created_by,
            created_at=quote.created_at,
        )
        self._session.add(orm)
        self._session.flush()
        return quote


# ═══════════════════════════════════════════════════════════
# Quotation
# ═══════════════════════════════════════════════════════════

class SqlQuotationRepository(QuotationRepository):
    def __init__(self, session: Session):
        self._session = session

    def get_by_id(self, quotation_id: UUID) -> Optional[SalesQuotation]:
        orm = self._session.get(SalesQuotationORM, quotation_id)
        if not orm:
            return None
        return SalesQuotation(
            quotation_id=orm.quotation_id, customer_id=orm.customer_id,
            title=orm.title, status=orm.status, valid_until=orm.valid_until,
            note=orm.note, created_by=orm.created_by,
            created_at=orm.created_at, updated_at=orm.updated_at,
        )

    def save(self, q: SalesQuotation) -> SalesQuotation:
        existing = self._session.get(SalesQuotationORM, q.quotation_id)
        if existing:
            existing.customer_id = q.customer_id
            existing.title = q.title
            existing.status = q.status
            existing.valid_until = q.valid_until
            existing.note = q.note
            existing.updated_at = q.updated_at
            self._session.flush()
            return q

        orm = SalesQuotationORM(
            quotation_id=q.quotation_id, customer_id=q.customer_id,
            title=q.title, status=q.status, valid_until=q.valid_until,
            note=q.note, created_by=q.created_by,
            created_at=q.created_at, updated_at=q.updated_at,
        )
        self._session.add(orm)
        self._session.flush()
        return SalesQuotation(
            quotation_id=orm.quotation_id, customer_id=orm.customer_id,
            title=orm.title, status=orm.status, valid_until=orm.valid_until,
            note=orm.note, created_by=orm.created_by,
            created_at=orm.created_at, updated_at=orm.updated_at,
        )

    def delete(self, quotation_id: UUID) -> None:
        self._session.query(SalesQuotationLineORM).filter(
            SalesQuotationLineORM.quotation_id == quotation_id).delete()
        orm = self._session.get(SalesQuotationORM, quotation_id)
        if orm:
            self._session.delete(orm)
        self._session.flush()


class SqlQuotationLineRepository(QuotationLineRepository):
    def __init__(self, session: Session):
        self._session = session

    def save(self, line: SalesQuotationLine) -> SalesQuotationLine:
        orm = SalesQuotationLineORM(
            line_id=line.line_id, quotation_id=line.quotation_id,
            sku_id=line.sku_id, quantity=line.quantity,
            unit_price=line.unit_price, note=line.note,
        )
        self._session.add(orm)
        self._session.flush()
        return line


class SqlSupplierRepository(SupplierRepository):
    def __init__(self, session: Session):
        self._session = session

    def get_by_id(self, supplier_id: UUID) -> Optional[Supplier]:
        orm = self._session.get(SupplierORM, supplier_id)
        return self._to_domain(orm) if orm else None

    def save(self, supplier: Supplier) -> Supplier:
        existing = self._session.get(SupplierORM, supplier.supplier_id)
        if existing:
            existing.name = supplier.name
            existing.contact_name = supplier.contact_name
            existing.phone = supplier.phone
            existing.address = supplier.address
            existing.note = supplier.note
            existing.is_active = supplier.is_active
            self._session.flush()
            return self._to_domain(existing)

        orm = SupplierORM(
            supplier_id=supplier.supplier_id,
            name=supplier.name,
            contact_name=supplier.contact_name,
            phone=supplier.phone,
            address=supplier.address,
            note=supplier.note,
            is_active=supplier.is_active,
        )
        self._session.add(orm)
        self._session.flush()
        return self._to_domain(orm)

    @staticmethod
    def _to_domain(orm: SupplierORM) -> Supplier:
        return Supplier(
            supplier_id=orm.supplier_id,
            name=orm.name,
            contact_name=orm.contact_name,
            phone=orm.phone,
            address=orm.address,
            note=orm.note,
            is_active=orm.is_active,
        )
