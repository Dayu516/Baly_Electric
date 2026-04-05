"""BomService — BOM 組成關係管理 use case。

規則：
- BOM 的 parent 必須是 item_type=assembly
- BOM 的 child 必須存在
- 全量覆蓋（delete + insert）
- item_type 變更時驗證 BOM 一致性
"""

from uuid import UUID

from core.errors import ERR_BIZ_001, ERR_BIZ_002
from core.logging import get_logger
from core.results import Result
from domain.product.models import BomChild
from domain.product.repository import BomRepository, SKURepository

logger = get_logger("bom")


class BomService:
    def __init__(self, sku_repo: SKURepository, bom_repo: BomRepository):
        self._sku_repo = sku_repo
        self._bom_repo = bom_repo

    def save_bom(self, parent_sku_id: UUID, children: list[dict]) -> Result:
        """全量覆蓋 BOM。children: [{child_sku_id, quantity, component_role, sort_order, note}]"""
        parent = self._sku_repo.get_by_id(parent_sku_id)
        if not parent:
            return Result.fail(ERR_BIZ_002, "成品 SKU 不存在")
        if parent.item_type != "assembly":
            return Result.fail(ERR_BIZ_001, f"只有組合品才能設定 BOM，目前型態為 {parent.item_type}")

        # 驗證所有 child 都存在
        bom_children = []
        for child in children:
            child_sku = self._sku_repo.get_by_id(UUID(child["child_sku_id"]))
            if not child_sku:
                return Result.fail(ERR_BIZ_002, f"零件 SKU {child['child_sku_id']} 不存在")
            bom_children.append(BomChild(
                child_sku_id=UUID(child["child_sku_id"]),
                quantity=child.get("quantity", 1),
                component_role=child.get("component_role"),
                sort_order=child.get("sort_order", 0),
                note=child.get("note"),
            ))

        self._bom_repo.replace_children(parent_sku_id, bom_children)

        logger.info("bom_saved", parent_sku_id=str(parent_sku_id), children=len(children))
        return Result.ok(message=f"BOM 已儲存，{len(children)} 個組成件")

    def validate_item_type_change(self, sku_id: UUID, new_type: str) -> Result:
        """驗證 item_type 變更是否合法（業務規則，放在 Application Service）。"""
        if new_type not in ("finished", "assembly", "accessory", "component"):
            return Result.fail(ERR_BIZ_001, f"無效的品項型態：{new_type}")

        current = self._sku_repo.get_by_id(sku_id)
        if not current:
            return Result.fail(ERR_BIZ_002, "SKU 不存在")

        old_type = current.item_type

        # 從 assembly 改走 → 不能有 BOM children
        if old_type == "assembly" and new_type != "assembly":
            if self._bom_repo.has_children(sku_id):
                return Result.fail(ERR_BIZ_001, "此組合品已有組成件，請先移除 BOM 關係再更改型態")

        # 從 component 改走 → 不能被別人的 BOM 引用
        if old_type == "component" and new_type != "component":
            if self._bom_repo.is_child(sku_id):
                return Result.fail(ERR_BIZ_001, "此零件已被其他組合品使用，請先移除 BOM 關係再更改型態")

        return Result.ok()
