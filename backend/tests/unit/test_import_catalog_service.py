"""ImportCatalogService unit tests — mock repos, no DB."""

import uuid
from unittest.mock import MagicMock

import pytest

from application.product.import_catalog_service import ImportCatalogService
from domain.product.models import Product, SKU


def _make_service(**overrides):
    defaults = {
        "product_repo": MagicMock(),
        "sku_repo": MagicMock(),
        "review_repo": MagicMock(),
        "category_repo": None,
        "attribute_writer": None,
    }
    defaults.update(overrides)
    svc = ImportCatalogService(**defaults)
    return svc, defaults


SIMPLE_CSV = """品名,規格,廠牌,售價,單位
無熔絲開關,2P 20A,士林,100,個
"""

MULTI_CSV = """品名,規格,廠牌,售價,單位
無熔絲開關,2P 20A,士林,100,個
無熔絲開關,3P 30A,東元,200,個
"""

DUPLICATE_CSV = """品名,規格,廠牌,售價,單位
無熔絲開關,2P 20A,士林,100,個
無熔絲開關,2P 20A,士林,100,個
"""

BARCODE_CSV = """品名,規格,廠牌,條碼,售價,單位
開關A,2P,士林,BC001,100,個
"""


class TestImportBasic:
    def test_simple_import(self):
        svc, mocks = _make_service()
        saved_product = Product(product_id=uuid.uuid4(), name="無熔絲開關")
        mocks["product_repo"].save.return_value = saved_product
        mocks["sku_repo"].save.return_value = SKU()
        mocks["sku_repo"].get_by_barcode.return_value = None

        result = svc.import_csv(SIMPLE_CSV, uuid.uuid4())

        assert result.success
        assert result.data["imported"] == 1
        mocks["product_repo"].save.assert_called_once()
        mocks["sku_repo"].save.assert_called_once()

    def test_multi_row_same_product(self):
        """同品名+不同規格 → 不同 Product（因為 product_key = name|spec）。"""
        svc, mocks = _make_service()
        mocks["product_repo"].save.side_effect = [
            Product(product_id=uuid.uuid4(), name="無熔絲開關"),
            Product(product_id=uuid.uuid4(), name="無熔絲開關"),
        ]
        mocks["sku_repo"].save.return_value = SKU()
        mocks["sku_repo"].get_by_barcode.return_value = None

        result = svc.import_csv(MULTI_CSV, uuid.uuid4())
        assert result.data["imported"] == 2

    def test_empty_csv(self):
        svc, _ = _make_service()
        result = svc.import_csv("", uuid.uuid4())
        assert not result.success

    def test_review_task_created(self):
        svc, mocks = _make_service()
        mocks["product_repo"].save.return_value = Product(product_id=uuid.uuid4())
        mocks["sku_repo"].save.return_value = SKU()

        svc.import_csv(SIMPLE_CSV, uuid.uuid4())

        mocks["review_repo"].save.assert_called_once()
        task = mocks["review_repo"].save.call_args[0][0]
        assert task.review_type == "product_confirm"


class TestImportDeduplication:
    def test_sku_level_dedup(self):
        svc, mocks = _make_service()
        mocks["product_repo"].save.return_value = Product(product_id=uuid.uuid4())
        mocks["sku_repo"].save.return_value = SKU()

        result = svc.import_csv(DUPLICATE_CSV, uuid.uuid4())

        assert result.data["imported"] == 1
        assert result.data["skipped_duplicate"] == 1

    def test_barcode_dedup(self):
        svc, mocks = _make_service()
        mocks["product_repo"].save.return_value = Product(product_id=uuid.uuid4())
        mocks["sku_repo"].save.return_value = SKU()
        mocks["sku_repo"].get_by_barcode.return_value = SKU()  # already exists

        result = svc.import_csv(BARCODE_CSV, uuid.uuid4())

        assert result.data["skipped_duplicate"] == 1


class TestImportItemType:
    def test_item_type_from_csv(self):
        csv = """品名,規格,品項型態,售價
組合品A,spec,assembly,100
"""
        svc, mocks = _make_service()
        mocks["product_repo"].save.return_value = Product(product_id=uuid.uuid4())
        mocks["sku_repo"].save.return_value = SKU()

        svc.import_csv(csv, uuid.uuid4())

        saved_sku = mocks["sku_repo"].save.call_args[0][0]
        assert saved_sku.item_type == "assembly"

    def test_invalid_item_type_defaults(self):
        csv = """品名,規格,品項型態,售價
品A,spec,invalid_type,100
"""
        svc, mocks = _make_service()
        mocks["product_repo"].save.return_value = Product(product_id=uuid.uuid4())
        mocks["sku_repo"].save.return_value = SKU()

        svc.import_csv(csv, uuid.uuid4())

        saved_sku = mocks["sku_repo"].save.call_args[0][0]
        assert saved_sku.item_type == "finished"


class TestUpsertExisting:
    def test_barcode_hit_updates_safe_fields(self):
        """既有 SKU（barcode 命中） → 安全欄位自動更新。"""
        svc, mocks = _make_service()
        existing_sku = SKU(
            sku_id=uuid.uuid4(), product_id=uuid.uuid4(),
            brand="士林", spec="2P", sell_price=100, cost_price=60,
            supplier_code="OLD", item_type="finished",
        )
        mocks["sku_repo"].get_by_barcode.return_value = existing_sku
        mocks["sku_repo"].save.return_value = existing_sku

        csv = """品名,規格,廠牌,條碼,售價,成本,供應商料號
開關,2P,士林,BC001,150,70,NEW_CODE
"""
        result = svc.import_csv(csv, uuid.uuid4())

        assert result.data["updated"] == 1
        # 安全欄位已更新
        saved = mocks["sku_repo"].save.call_args[0][0]
        assert saved.cost_price == 70
        assert saved.supplier_code == "NEW_CODE"

    def test_sell_price_change_goes_to_review(self):
        """售價變更不直接寫，記到 review_changes。"""
        svc, mocks = _make_service()
        existing_sku = SKU(
            sku_id=uuid.uuid4(), product_id=uuid.uuid4(),
            sell_price=100, cost_price=60, item_type="finished",
        )
        mocks["sku_repo"].get_by_barcode.return_value = existing_sku
        mocks["sku_repo"].save.return_value = existing_sku

        csv = """品名,規格,廠牌,條碼,售價,成本
開關,2P,士林,BC001,200,70
"""
        result = svc.import_csv(csv, uuid.uuid4())

        assert len(result.data["review_changes"]) >= 1
        change = result.data["review_changes"][0]
        assert change["field"] == "sell_price"
        assert change["old"] == 100
        assert change["new"] == 200

    def test_item_type_change_goes_to_review(self):
        svc, mocks = _make_service()
        existing_sku = SKU(
            sku_id=uuid.uuid4(), product_id=uuid.uuid4(),
            sell_price=100, item_type="finished",
        )
        mocks["sku_repo"].get_by_barcode.return_value = existing_sku
        mocks["sku_repo"].save.return_value = existing_sku

        csv = """品名,規格,廠牌,條碼,售價,品項型態
開關,2P,士林,BC001,100,assembly
"""
        result = svc.import_csv(csv, uuid.uuid4())

        changes = [c for c in result.data["review_changes"] if c["field"] == "item_type"]
        assert len(changes) == 1
        assert changes[0]["new"] == "assembly"


class TestBatchId:
    def test_batch_id_written_to_product_and_sku(self):
        svc, mocks = _make_service()
        mocks["product_repo"].save.side_effect = lambda p: p
        mocks["sku_repo"].save.return_value = SKU()
        mocks["sku_repo"].get_by_barcode.return_value = None

        batch_id = uuid.uuid4()
        svc.import_csv(SIMPLE_CSV, uuid.uuid4(), batch_id=batch_id)

        saved_product = mocks["product_repo"].save.call_args[0][0]
        assert saved_product.source_batch_id == batch_id

        saved_sku = mocks["sku_repo"].save.call_args[0][0]
        assert saved_sku.source_batch_id == batch_id


class TestCrossBatchDedup:
    def test_db_level_dedup(self):
        """跨批次：name+spec+brand 命中 DB → upsert，不建新 SKU。"""
        product_query = MagicMock()
        product_query.find_existing_sku.return_value = {
            "sku_id": uuid.uuid4(), "product_id": uuid.uuid4(),
            "sell_price": 100, "item_type": "finished", "name": "無熔絲開關",
        }

        svc, mocks = _make_service(product_query=product_query)
        existing_sku = SKU(
            sku_id=uuid.uuid4(), product_id=uuid.uuid4(),
            sell_price=100, cost_price=60, item_type="finished",
        )
        mocks["sku_repo"].get_by_id.return_value = existing_sku
        mocks["sku_repo"].get_by_barcode.return_value = None
        mocks["sku_repo"].save.return_value = existing_sku

        result = svc.import_csv(SIMPLE_CSV, uuid.uuid4())

        # 不應該建新 Product
        mocks["product_repo"].save.assert_not_called()
        # 應該 upsert 既有 SKU
        assert result.data["updated"] == 1 or result.data["skipped_duplicate"] == 1
