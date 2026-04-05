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
