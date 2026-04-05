"""ReceiveStockService unit tests — mock repos, no DB."""

import uuid
from unittest.mock import MagicMock, call

import pytest

from application.inventory.receive_stock_service import ReceiveLineInput, ReceiveStockService


FAKE_USER = uuid.uuid4()
FAKE_SUPPLIER = uuid.uuid4()
FAKE_SKU_1 = uuid.uuid4()
FAKE_SKU_2 = uuid.uuid4()


def _make_service(**overrides):
    defaults = {
        "movement_repo": MagicMock(),
        "balance_repo": MagicMock(),
    }
    defaults.update(overrides)
    return ReceiveStockService(**defaults), defaults


class TestReceiveBasic:
    def test_single_line_receive(self):
        svc, mocks = _make_service()
        lines = [ReceiveLineInput(sku_id=FAKE_SKU_1, quantity=10)]

        result = svc.receive(lines, FAKE_SUPPLIER, FAKE_USER)

        assert result.success
        assert result.data["lines"] == 1
        mocks["movement_repo"].save.assert_called_once()
        mocks["balance_repo"].ensure_exists.assert_called_once_with(FAKE_SKU_1)
        mocks["balance_repo"].atomic_update.assert_called_once_with(FAKE_SKU_1, 10)

    def test_multi_line_receive(self):
        svc, mocks = _make_service()
        lines = [
            ReceiveLineInput(sku_id=FAKE_SKU_1, quantity=5),
            ReceiveLineInput(sku_id=FAKE_SKU_2, quantity=3),
        ]

        result = svc.receive(lines, FAKE_SUPPLIER, FAKE_USER)

        assert result.success
        assert result.data["lines"] == 2
        assert mocks["movement_repo"].save.call_count == 2
        assert mocks["balance_repo"].ensure_exists.call_count == 2
        assert mocks["balance_repo"].atomic_update.call_count == 2

    def test_movement_has_correct_fields(self):
        svc, mocks = _make_service()
        lines = [ReceiveLineInput(sku_id=FAKE_SKU_1, quantity=7)]

        svc.receive(lines, FAKE_SUPPLIER, FAKE_USER)

        movement = mocks["movement_repo"].save.call_args[0][0]
        assert movement.sku_id == FAKE_SKU_1
        assert movement.quantity == 7
        assert movement.movement_type == "purchase_receive"
        assert movement.reference_type == "purchase_receipt"
        assert movement.created_by == FAKE_USER


class TestReceiveValidation:
    def test_empty_lines_rejected(self):
        svc, mocks = _make_service()

        result = svc.receive([], FAKE_SUPPLIER, FAKE_USER)

        assert not result.success
        assert result.code == "ERR-VAL-001"
        mocks["movement_repo"].save.assert_not_called()

    def test_zero_quantity_rejected(self):
        svc, mocks = _make_service()
        lines = [ReceiveLineInput(sku_id=FAKE_SKU_1, quantity=0)]

        result = svc.receive(lines, FAKE_SUPPLIER, FAKE_USER)

        assert not result.success
        mocks["movement_repo"].save.assert_not_called()

    def test_negative_quantity_rejected(self):
        svc, mocks = _make_service()
        lines = [ReceiveLineInput(sku_id=FAKE_SKU_1, quantity=-5)]

        result = svc.receive(lines, FAKE_SUPPLIER, FAKE_USER)

        assert not result.success
        mocks["movement_repo"].save.assert_not_called()


class TestReceiveEnsureExists:
    def test_ensure_exists_called_before_atomic_update(self):
        svc, mocks = _make_service()
        call_order = []
        mocks["balance_repo"].ensure_exists.side_effect = lambda *a: call_order.append("ensure")
        mocks["balance_repo"].atomic_update.side_effect = lambda *a: call_order.append("update")

        lines = [ReceiveLineInput(sku_id=FAKE_SKU_1, quantity=5)]
        svc.receive(lines, FAKE_SUPPLIER, FAKE_USER)

        assert call_order == ["ensure", "update"]
