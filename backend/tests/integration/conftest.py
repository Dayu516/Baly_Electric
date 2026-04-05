"""Integration test fixtures — real DB, rollback after each test."""

import pytest
from sqlalchemy import text

from database import SessionLocal


@pytest.fixture
def db_session():
    """提供一個 DB session，測試結束後 rollback。"""
    session = SessionLocal()
    # 開始一個 savepoint，測試結束後回滾
    session.begin_nested()
    yield session
    session.rollback()
    session.close()


@pytest.fixture
def seed_data(db_session):
    """建立測試用基礎資料（供應商、品項、SKU、庫存）。回傳 dict 包含所有 ID。"""
    import uuid

    supplier_id = str(uuid.uuid4())
    product_id = str(uuid.uuid4())
    sku_id = str(uuid.uuid4())
    category_id = str(uuid.uuid4())

    # 供應商
    db_session.execute(text("""
        INSERT INTO suppliers (supplier_id, name, is_active)
        VALUES (:sid, '測試供應商', true)
    """), {"sid": supplier_id})

    # 分類
    db_session.execute(text("""
        INSERT INTO categories (category_id, name, sort_order)
        VALUES (:cid, '測試分類', 0)
    """), {"cid": category_id})

    # 品項
    db_session.execute(text("""
        INSERT INTO products (product_id, name, category_id, is_active)
        VALUES (:pid, '測試品項', :cid, true)
    """), {"pid": product_id, "cid": category_id})

    # SKU
    db_session.execute(text("""
        INSERT INTO skus (sku_id, product_id, brand, spec, unit, sell_price, cost_price, min_stock, is_active)
        VALUES (:sid, :pid, '測試牌', '2P 20A', '個', 100, 60, 10, true)
    """), {"sid": sku_id, "pid": product_id})

    # 庫存
    db_session.execute(text("""
        INSERT INTO inventory_balances (sku_id, current_stock) VALUES (:sid, 5)
    """), {"sid": sku_id})

    # supplier_products（首選供應商）
    db_session.execute(text("""
        INSERT INTO supplier_products (sp_id, supplier_id, sku_id, unit_cost, is_preferred)
        VALUES (:spid, :sup_id, :sku_id, 60, true)
    """), {"spid": str(uuid.uuid4()), "sup_id": supplier_id, "sku_id": sku_id})

    db_session.flush()

    return {
        "supplier_id": supplier_id,
        "product_id": product_id,
        "sku_id": sku_id,
        "category_id": category_id,
    }


@pytest.fixture
def po_service(db_session):
    """建立 PurchaseOrderService（注入所有 repo）。"""
    from application.procurement.purchase_order_service import PurchaseOrderService
    from infrastructure.persistence.query_services.procurement_query_service import ProcurementQueryService
    from infrastructure.persistence.repositories.inventory_repo_impl import (
        SqlInventoryBalanceRepository, SqlStockMovementRepository,
    )
    from infrastructure.persistence.repositories.procurement_repo_impl import (
        SqlPurchaseOrderLineRepository, SqlPurchaseOrderRepository,
        SqlPurchaseReceiptLineRepository, SqlPurchaseReceiptRepository,
    )

    return PurchaseOrderService(
        po_repo=SqlPurchaseOrderRepository(db_session),
        po_line_repo=SqlPurchaseOrderLineRepository(db_session),
        receipt_repo=SqlPurchaseReceiptRepository(db_session),
        receipt_line_repo=SqlPurchaseReceiptLineRepository(db_session),
        movement_repo=SqlStockMovementRepository(db_session),
        balance_repo=SqlInventoryBalanceRepository(db_session),
        query_service=ProcurementQueryService(db_session),
    )


@pytest.fixture
def inquiry_service(db_session):
    """建立 InquiryService（注入所有 repo）。"""
    from application.procurement.inquiry_service import InquiryService
    from infrastructure.persistence.query_services.procurement_query_service import ProcurementQueryService as _PQS
    from infrastructure.persistence.repositories.procurement_repo_impl import (
        SqlInquiryLineRepository, SqlInquiryQuoteRepository, SqlInquiryRepository,
        SqlPurchaseOrderLineRepository as _SqlPOLineRepo,
        SqlPurchaseOrderRepository as _SqlPORepo,
        SqlSupplierPriceQuoteRepository,
    )

    return InquiryService(
        inquiry_repo=SqlInquiryRepository(db_session),
        inquiry_line_repo=SqlInquiryLineRepository(db_session),
        inquiry_quote_repo=SqlInquiryQuoteRepository(db_session),
        supplier_quote_repo=SqlSupplierPriceQuoteRepository(db_session),
        po_repo=_SqlPORepo(db_session),
        po_line_repo=_SqlPOLineRepo(db_session),
        query_service=_PQS(db_session),
    )


@pytest.fixture
def quotation_service(db_session):
    """建立 QuotationService（注入所有 repo）。"""
    from application.procurement.quotation_service import QuotationService
    from infrastructure.persistence.query_services.procurement_query_service import ProcurementQueryService
    from infrastructure.persistence.repositories.inventory_repo_impl import (
        SqlInventoryBalanceRepository as _BalRepo,
        SqlStockMovementRepository as _MvtRepo,
    )
    from infrastructure.persistence.repositories.procurement_repo_impl import (
        SqlQuotationLineRepository, SqlQuotationRepository,
    )
    from infrastructure.persistence.repositories.sales_repo_impl import SqlSaleRepository

    return QuotationService(
        quotation_repo=SqlQuotationRepository(db_session),
        quotation_line_repo=SqlQuotationLineRepository(db_session),
        sale_repo=SqlSaleRepository(db_session),
        movement_repo=_MvtRepo(db_session),
        balance_repo=_BalRepo(db_session),
        query_service=ProcurementQueryService(db_session),
    )
