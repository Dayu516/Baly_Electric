"""AliasService — 品項別名 CRUD use case。"""

from uuid import UUID

from core.results import Result
from domain.product.models import ProductAlias
from domain.product.repository import ProductAliasRepository


class AliasService:
    def __init__(self, alias_repo: ProductAliasRepository):
        self._alias_repo = alias_repo

    def create_alias(
        self,
        product_id: UUID,
        alias: str,
        alias_type: str = "common",
        created_by: UUID | None = None,
    ) -> Result:
        new_alias = ProductAlias(
            product_id=product_id,
            alias=alias.strip(),
            alias_type=alias_type,
            created_by=created_by,
        )
        saved = self._alias_repo.save(new_alias)
        return Result.ok(
            data={
                "alias_id": str(saved.alias_id),
                "product_id": str(saved.product_id),
                "alias": saved.alias,
                "alias_type": saved.alias_type,
            },
            message="別名已建立",
        )

    def delete_alias(self, product_id: UUID, alias_id: UUID) -> Result:
        existing = self._alias_repo.get_by_id(alias_id)
        if not existing or existing.product_id != product_id:
            return Result.fail("ERR-BIZ-002", "別名不存在")
        self._alias_repo.delete(alias_id)
        return Result.ok(message="別名已刪除")
