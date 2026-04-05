"""Use Case 層 — 跨模組正式業務流程的唯一承載點。

Use case 只做：
  - Idempotency 檢查
  - 呼叫 service 執行業務邏輯
  - 建立 audit_event
  - Commit
  - Post-commit side effects（best-effort）

Use case 不做：
  - 金額計算 / 狀態推導（下沉到 service）
  - 直接呼叫 repository（下沉到 service / rules.py）
  - Business rules（下沉到 service / rules.py）
"""

from sqlalchemy.orm import Session


def build_receive_po_use_case(session: Session):
    from application.use_cases.receive_purchase_order import ReceivePurchaseOrderUseCase
    from application.procurement import build_po_service, build_procurement_query_service
    from infrastructure.persistence.repositories.alert_repo_impl import SqlOperationalAlertRepository
    from infrastructure.persistence.repositories.audit_repo_impl import AuditService
    from infrastructure.persistence.repositories.inventory_repo_impl import SqlInventoryBalanceRepository
    from infrastructure.persistence.repositories.procurement_repo_impl import (
        SqlPurchaseReceiptLineRepository,
        SqlPurchaseReceiptRepository,
    )
    from infrastructure.persistence.repositories.product_repo_impl import SqlSKURepository

    return ReceivePurchaseOrderUseCase(
        po_service=build_po_service(session),
        receipt_repo=SqlPurchaseReceiptRepository(session),
        receipt_line_repo=SqlPurchaseReceiptLineRepository(session),
        audit_service=AuditService(session),
        alert_repo=SqlOperationalAlertRepository(session),
        balance_repo=SqlInventoryBalanceRepository(session),
        sku_repo=SqlSKURepository(session),
        query_service=build_procurement_query_service(session),
        session=session,
    )


def build_import_catalog_use_case(session: Session):
    from application.use_cases.import_catalog import ImportCatalogUseCase
    from application.product import build_import_catalog_service
    from infrastructure.persistence.repositories.audit_repo_impl import AuditService

    return ImportCatalogUseCase(
        import_service=build_import_catalog_service(session),
        audit_service=AuditService(session),
        session=session,
    )


def build_deactivate_import_batch_use_case(session: Session):
    from application.use_cases.import_catalog import DeactivateImportBatchUseCase
    from infrastructure.persistence.repositories.audit_repo_impl import AuditService

    return DeactivateImportBatchUseCase(
        audit_service=AuditService(session),
        session=session,
    )


def build_checkout_use_case(session: Session):
    from application.use_cases.checkout import CheckoutUseCase
    from application.sales import build_checkout_service
    from infrastructure.persistence.repositories.alert_repo_impl import SqlOperationalAlertRepository
    from infrastructure.persistence.repositories.audit_repo_impl import AuditService
    from infrastructure.persistence.repositories.inventory_repo_impl import SqlInventoryBalanceRepository
    from infrastructure.persistence.repositories.product_repo_impl import SqlSKURepository

    return CheckoutUseCase(
        checkout_service=build_checkout_service(session),
        audit_service=AuditService(session),
        alert_repo=SqlOperationalAlertRepository(session),
        balance_repo=SqlInventoryBalanceRepository(session),
        sku_repo=SqlSKURepository(session),
        session=session,
    )


def build_void_sale_use_case(session: Session):
    from application.use_cases.checkout import VoidSaleUseCase
    from application.sales import build_void_sale_service
    from infrastructure.persistence.repositories.audit_repo_impl import AuditService

    return VoidSaleUseCase(
        void_service=build_void_sale_service(session),
        audit_service=AuditService(session),
        session=session,
    )


def build_generate_statement_use_case(session: Session):
    from application.use_cases.monthly_statement import GenerateStatementUseCase
    from application.customer import build_generate_statement_service
    from infrastructure.persistence.repositories.audit_repo_impl import AuditService

    return GenerateStatementUseCase(
        statement_service=build_generate_statement_service(session),
        audit_service=AuditService(session),
        session=session,
    )


def build_record_payment_use_case(session: Session):
    from application.use_cases.monthly_statement import RecordPaymentUseCase
    from application.customer import build_payment_service
    from infrastructure.persistence.repositories.audit_repo_impl import AuditService
    from infrastructure.persistence.repositories.review_repo_impl import SqlReviewTaskRepository
    from infrastructure.persistence.repositories.settings_repo_impl import SqlSettingsRepository

    return RecordPaymentUseCase(
        payment_service=build_payment_service(session),
        audit_service=AuditService(session),
        review_repo=SqlReviewTaskRepository(session),
        settings_repo=SqlSettingsRepository(session),
        session=session,
    )
