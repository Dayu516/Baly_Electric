"""SupplierPriceService unit tests — mock repos, no DB."""

import uuid
from unittest.mock import MagicMock

import pytest

from application.product.supplier_price_service import SupplierPriceService


FAKE_PRODUCT = uuid.uuid4()
FAKE_SKU = uuid.uuid4()
FAKE_SUPPLIER = uuid.uuid4()
FAKE_USER = uuid.uuid4()


def _make_service(**overrides):
    defaults = {
        "quote_repo": MagicMock(),
        "product_query": MagicMock(),
        "procurement_query": MagicMock(),
    }
    defaults.update(overrides)
    return SupplierPriceService(**defaults), defaults


class TestCreateQuote:
    def test_successful_quote(self):
        svc, mocks = _make_service()
        mocks["product_query"].verify_sku_belongs_to_product.return_value = True
        mocks["product_query"].get_active_supplier_name.return_value = "台灣士林"

        result = svc.create_quote(
            FAKE_PRODUCT, str(FAKE_SUPPLIER), str(FAKE_SKU), 150.0, FAKE_USER,
        )

        assert result.success
        assert result.data["supplier_name"] == "台灣士林"
        assert result.data["unit_price"] == 150.0
        mocks["quote_repo"].save.assert_called_once()
        mocks["procurement_query"].update_supplier_product_cost.assert_called_once()

    def test_sku_not_belongs_rejected(self):
        svc, mocks = _make_service()
        mocks["product_query"].verify_sku_belongs_to_product.return_value = False

        result = svc.create_quote(
            FAKE_PRODUCT, str(FAKE_SUPPLIER), str(FAKE_SKU), 150.0, FAKE_USER,
        )

        assert not result.success
        assert "不屬於" in result.message
        mocks["quote_repo"].save.assert_not_called()

    def test_supplier_not_found_rejected(self):
        svc, mocks = _make_service()
        mocks["product_query"].verify_sku_belongs_to_product.return_value = True
        mocks["product_query"].get_active_supplier_name.return_value = None

        result = svc.create_quote(
            FAKE_PRODUCT, str(FAKE_SUPPLIER), str(FAKE_SKU), 150.0, FAKE_USER,
        )

        assert not result.success
        assert "供應商" in result.message

    def test_custom_quoted_at(self):
        svc, mocks = _make_service()
        mocks["product_query"].verify_sku_belongs_to_product.return_value = True
        mocks["product_query"].get_active_supplier_name.return_value = "供應商A"

        result = svc.create_quote(
            FAKE_PRODUCT, str(FAKE_SUPPLIER), str(FAKE_SKU), 100.0, FAKE_USER,
            quoted_at="2026-01-15T10:00:00",
        )

        assert result.success
        assert "2026-01-15" in result.data["quoted_at"]
