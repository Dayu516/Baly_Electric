"""StockRecalcService unit tests — mock repos, no DB.

重點驗證：Application 層只依賴抽象，不依賴 SQLAlchemy session。
"""

import uuid
from unittest.mock import MagicMock

import pytest

from application.inventory.stock_recalc_service import StockRecalcService


FAKE_SKU = uuid.uuid4()


def _make_service(**overrides):
    defaults = {
        "query_service": MagicMock(),
        "balance_repo": MagicMock(),
        "alert_repo": MagicMock(),
    }
    defaults.update(overrides)
    return StockRecalcService(**defaults), defaults


class TestRecalc:
    def test_calls_set_stock_with_correct_value(self):
        svc, mocks = _make_service()
        mocks["query_service"].recalc_inventory_balance.return_value = 42

        result = svc.recalc(FAKE_SKU)

        assert result.success
        mocks["query_service"].recalc_inventory_balance.assert_called_once_with(str(FAKE_SKU))
        mocks["balance_repo"].set_stock.assert_called_once_with(FAKE_SKU, 42)

    def test_returns_correct_data(self):
        svc, mocks = _make_service()
        mocks["query_service"].recalc_inventory_balance.return_value = 15

        result = svc.recalc(FAKE_SKU)

        assert result.data["sku_id"] == str(FAKE_SKU)
        assert result.data["current_stock"] == 15

    def test_zero_stock(self):
        svc, mocks = _make_service()
        mocks["query_service"].recalc_inventory_balance.return_value = 0

        result = svc.recalc(FAKE_SKU)

        assert result.success
        mocks["balance_repo"].set_stock.assert_called_once_with(FAKE_SKU, 0)

    def test_negative_stock(self):
        """負庫存允許（電控行先賣後補）。"""
        svc, mocks = _make_service()
        mocks["query_service"].recalc_inventory_balance.return_value = -3

        result = svc.recalc(FAKE_SKU)

        assert result.success
        mocks["balance_repo"].set_stock.assert_called_once_with(FAKE_SKU, -3)

    def test_no_session_access(self):
        """確認 service 不碰 _session（架構驗證）。"""
        svc, mocks = _make_service()
        mocks["query_service"].recalc_inventory_balance.return_value = 10

        svc.recalc(FAKE_SKU)

        # query_service._session should never be accessed
        assert not hasattr(mocks["query_service"], '_session') or \
               not mocks["query_service"]._session.execute.called
