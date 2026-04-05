"""Procurement 模組組裝入口。

所有 Procurement service 的建立都透過這裡，API 層不可自行組裝 repo。

Usage（API 層）：
    from application.procurement import build_po_service, build_inquiry_service, build_quotation_service
    svc = build_po_service(session)
"""

from sqlalchemy.orm import Session

from application.procurement.inquiry_service import InquiryService
from application.procurement.purchase_order_service import PurchaseOrderService
from application.procurement.quotation_service import QuotationService
from infrastructure.persistence.query_services.procurement_query_service import ProcurementQueryService
from infrastructure.persistence.repositories.inventory_repo_impl import (
    SqlInventoryBalanceRepository,
    SqlStockMovementRepository,
)
from infrastructure.persistence.repositories.procurement_repo_impl import (
    SqlInquiryLineRepository,
    SqlInquiryQuoteRepository,
    SqlInquiryRepository,
    SqlPurchaseOrderLineRepository,
    SqlPurchaseOrderRepository,
    SqlPurchaseReceiptLineRepository,
    SqlPurchaseReceiptRepository,
    SqlQuotationLineRepository,
    SqlQuotationRepository,
    SqlSupplierPriceQuoteRepository,
)
from infrastructure.persistence.repositories.alert_repo_impl import SqlOperationalAlertRepository
from infrastructure.persistence.repositories.sales_repo_impl import SqlSaleRepository


def build_po_service(session: Session) -> PurchaseOrderService:
    from application.sales import build_backorder_service
    return PurchaseOrderService(
        po_repo=SqlPurchaseOrderRepository(session),
        po_line_repo=SqlPurchaseOrderLineRepository(session),
        receipt_repo=SqlPurchaseReceiptRepository(session),
        receipt_line_repo=SqlPurchaseReceiptLineRepository(session),
        movement_repo=SqlStockMovementRepository(session),
        balance_repo=SqlInventoryBalanceRepository(session),
        query_service=ProcurementQueryService(session),
        backorder_service=build_backorder_service(session),
        alert_repo=SqlOperationalAlertRepository(session),
    )


def build_inquiry_service(session: Session) -> InquiryService:
    return InquiryService(
        inquiry_repo=SqlInquiryRepository(session),
        inquiry_line_repo=SqlInquiryLineRepository(session),
        inquiry_quote_repo=SqlInquiryQuoteRepository(session),
        supplier_quote_repo=SqlSupplierPriceQuoteRepository(session),
        po_repo=SqlPurchaseOrderRepository(session),
        po_line_repo=SqlPurchaseOrderLineRepository(session),
        query_service=ProcurementQueryService(session),
    )


def build_quotation_service(session: Session) -> QuotationService:
    from infrastructure.persistence.repositories.product_repo_impl import SqlSKURepository
    return QuotationService(
        quotation_repo=SqlQuotationRepository(session),
        quotation_line_repo=SqlQuotationLineRepository(session),
        sale_repo=SqlSaleRepository(session),
        movement_repo=SqlStockMovementRepository(session),
        balance_repo=SqlInventoryBalanceRepository(session),
        query_service=ProcurementQueryService(session),
        alert_repo=SqlOperationalAlertRepository(session),
        sku_repo=SqlSKURepository(session),
    )


def build_procurement_query_service(session: Session):
    return ProcurementQueryService(session)


def build_supplier_repository(session: Session):
    from infrastructure.persistence.repositories.procurement_repo_impl import SqlSupplierRepository
    return SqlSupplierRepository(session)
