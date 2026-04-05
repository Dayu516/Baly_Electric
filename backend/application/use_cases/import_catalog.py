"""ImportCatalogUseCase + DeactivateImportBatchUseCase — 資料導入正式流程。

ImportCatalogUseCase：
  1. 生成 import_batch_id
  2. 呼叫 ImportCatalogService（upsert + review 分級）
  3. Audit（帶 batch_id）
  4. Commit

DeactivateImportBatchUseCase：
  一鍵停用整批匯入的 Product/SKU（不刪資料，只標 inactive）。
  NOTE: 只停用本批 batch-created 的資料。
        若是舊資料只是被本批更新過，不停用。
        TODO: Phase B 可擴充 undo update 邏輯（需 change log）。
"""

import uuid
from uuid import UUID

from sqlalchemy import text

from core.logging import get_logger
from core.results import Result
from infrastructure.persistence.repositories.audit_repo_impl import AuditService

logger = get_logger("use_case.import_catalog")


class ImportCatalogUseCase:
    def __init__(self, import_service, audit_service: AuditService, session):
        self._import_service = import_service
        self._audit = audit_service
        self._session = session

    def execute(self, csv_content: str, created_by: UUID) -> Result:
        # 1. 生成 batch_id
        batch_id = uuid.uuid4()

        # 2. 呼叫 service
        result = self._import_service.import_csv(csv_content, created_by, batch_id=batch_id)
        if not result.success:
            return result

        # 3. Audit
        self._audit.log(
            created_by, "import_catalog", "product",
            detail=result.data,
        )

        # 4. Commit
        self._session.commit()

        return result


class DeactivateImportBatchUseCase:
    """一鍵停用整批匯入的 Product/SKU。

    策略：只停用 source_batch_id == batch_id 的資料（batch-created）。
    不會停用舊資料（source_batch_id != batch_id 或 NULL）。
    TODO: Phase B 可擴充：追蹤本批 upsert 過的舊資料 → undo update。
    """

    def __init__(self, audit_service: AuditService, session):
        self._audit = audit_service
        self._session = session

    def execute(self, batch_id: UUID, user_id: UUID) -> Result:
        # 只停用本批建立的（source_batch_id 匹配）
        product_result = self._session.execute(
            text("UPDATE products SET is_active = false WHERE source_batch_id = :bid AND is_active = true"),
            {"bid": str(batch_id)},
        )
        sku_result = self._session.execute(
            text("UPDATE skus SET is_active = false WHERE source_batch_id = :bid AND is_active = true"),
            {"bid": str(batch_id)},
        )

        product_count = product_result.rowcount
        sku_count = sku_result.rowcount

        if product_count == 0 and sku_count == 0:
            return Result.fail("ERR-BIZ-002", "找不到此批次的匯入資料，或已全部停用")

        self._audit.log(
            user_id, "deactivate_import_batch", "product",
            detail={
                "batch_id": str(batch_id),
                "products_deactivated": product_count,
                "skus_deactivated": sku_count,
            },
        )

        self._session.commit()

        return Result.ok(
            data={"batch_id": str(batch_id), "products": product_count, "skus": sku_count},
            message=f"已停用 {product_count} 品項 + {sku_count} SKU",
        )
