"""StockCountService unit tests — mock repos, no DB."""

import uuid
from unittest.mock import MagicMock

import pytest

from application.inventory.stock_count_service import CountLineInput, StockCountService
from domain.inventory.models import InventoryBalance


FAKE_USER = uuid.uuid4()
FAKE_SKU_1 = uuid.uuid4()
FAKE_SKU_2 = uuid.uuid4()


def _make_service(**overrides):
    defaults = {
        "balance_repo": MagicMock(),
        "movement_repo": MagicMock(),
        "review_repo": MagicMock(),
    }
    defaults.update(overrides)
    return StockCountService(**defaults), defaults


# ── submit_count ─────────────────────────────────────


class TestSubmitCountNoDiscrepancy:
    def test_no_discrepancy(self):
        svc, mocks = _make_service()
        mocks["balance_repo"].get_by_sku.return_value = InventoryBalance(sku_id=FAKE_SKU_1, current_stock=10)

        result = svc.submit_count([CountLineInput(sku_id=FAKE_SKU_1, actual_quantity=10)], FAKE_USER)

        assert result.success
        assert "帳實相符" in result.message
        mocks["review_repo"].save.assert_not_called()

    def test_no_balance_and_zero_actual(self):
        svc, mocks = _make_service()
        mocks["balance_repo"].get_by_sku.return_value = None

        result = svc.submit_count([CountLineInput(sku_id=FAKE_SKU_1, actual_quantity=0)], FAKE_USER)

        assert result.success
        assert "帳實相符" in result.message


class TestSubmitCountWithDiscrepancy:
    def test_positive_discrepancy(self):
        svc, mocks = _make_service()
        mocks["balance_repo"].get_by_sku.return_value = InventoryBalance(sku_id=FAKE_SKU_1, current_stock=5)

        result = svc.submit_count([CountLineInput(sku_id=FAKE_SKU_1, actual_quantity=8)], FAKE_USER)

        assert result.success
        assert result.data["discrepancies"][0]["difference"] == 3
        mocks["review_repo"].save.assert_called_once()

    def test_negative_discrepancy(self):
        svc, mocks = _make_service()
        mocks["balance_repo"].get_by_sku.return_value = InventoryBalance(sku_id=FAKE_SKU_1, current_stock=10)

        result = svc.submit_count([CountLineInput(sku_id=FAKE_SKU_1, actual_quantity=7)], FAKE_USER)

        assert result.success
        assert result.data["discrepancies"][0]["difference"] == -3

    def test_review_task_created(self):
        svc, mocks = _make_service()
        mocks["balance_repo"].get_by_sku.return_value = InventoryBalance(sku_id=FAKE_SKU_1, current_stock=10)

        svc.submit_count([CountLineInput(sku_id=FAKE_SKU_1, actual_quantity=8)], FAKE_USER)

        task = mocks["review_repo"].save.call_args[0][0]
        assert task.review_type == "stock_discrepancy"

    def test_multi_sku_mixed(self):
        svc, mocks = _make_service()
        mocks["balance_repo"].get_by_sku.side_effect = [
            InventoryBalance(sku_id=FAKE_SKU_1, current_stock=10),
            InventoryBalance(sku_id=FAKE_SKU_2, current_stock=5),
        ]

        result = svc.submit_count([
            CountLineInput(sku_id=FAKE_SKU_1, actual_quantity=10),  # 相符
            CountLineInput(sku_id=FAKE_SKU_2, actual_quantity=3),   # 差異
        ], FAKE_USER)

        assert result.success
        assert len(result.data["discrepancies"]) == 1


# ── adjust ───────────────────────────────────────────


class TestAdjust:
    def test_positive_adjustment(self):
        svc, mocks = _make_service()
        mocks["balance_repo"].get_by_sku.return_value = InventoryBalance(sku_id=FAKE_SKU_1, current_stock=5)

        result = svc.adjust(FAKE_SKU_1, actual_quantity=8, adjusted_by=FAKE_USER)

        assert result.success
        mocks["movement_repo"].save.assert_called_once()
        movement = mocks["movement_repo"].save.call_args[0][0]
        assert movement.quantity == 3
        assert movement.movement_type == "adjustment"
        mocks["balance_repo"].atomic_update.assert_called_once_with(FAKE_SKU_1, 3)

    def test_negative_adjustment(self):
        svc, mocks = _make_service()
        mocks["balance_repo"].get_by_sku.return_value = InventoryBalance(sku_id=FAKE_SKU_1, current_stock=10)

        result = svc.adjust(FAKE_SKU_1, actual_quantity=7, adjusted_by=FAKE_USER)

        assert result.success
        movement = mocks["movement_repo"].save.call_args[0][0]
        assert movement.quantity == -3
        mocks["balance_repo"].atomic_update.assert_called_once_with(FAKE_SKU_1, -3)

    def test_zero_diff_no_adjustment(self):
        svc, mocks = _make_service()
        mocks["balance_repo"].get_by_sku.return_value = InventoryBalance(sku_id=FAKE_SKU_1, current_stock=10)

        result = svc.adjust(FAKE_SKU_1, actual_quantity=10, adjusted_by=FAKE_USER)

        assert result.success
        assert "帳實相符" in result.message
        mocks["movement_repo"].save.assert_not_called()

    def test_no_balance_treated_as_zero(self):
        svc, mocks = _make_service()
        mocks["balance_repo"].get_by_sku.return_value = None

        result = svc.adjust(FAKE_SKU_1, actual_quantity=5, adjusted_by=FAKE_USER)

        assert result.success
        movement = mocks["movement_repo"].save.call_args[0][0]
        assert movement.quantity == 5

    def test_note_passed_to_movement(self):
        svc, mocks = _make_service()
        mocks["balance_repo"].get_by_sku.return_value = InventoryBalance(sku_id=FAKE_SKU_1, current_stock=5)

        svc.adjust(FAKE_SKU_1, actual_quantity=8, adjusted_by=FAKE_USER, note="盤點修正")

        movement = mocks["movement_repo"].save.call_args[0][0]
        assert movement.note == "盤點修正"


class TestAdjustReviewTask:
    def test_closes_review_task(self):
        svc, mocks = _make_service()
        mocks["balance_repo"].get_by_sku.return_value = InventoryBalance(sku_id=FAKE_SKU_1, current_stock=5)
        from domain.review.models import ReviewTask
        task = ReviewTask(task_id=uuid.uuid4(), review_type="stock_discrepancy", status="pending")
        mocks["review_repo"].get_by_id.return_value = task

        svc.adjust(FAKE_SKU_1, actual_quantity=8, adjusted_by=FAKE_USER, review_task_id=task.task_id)

        mocks["review_repo"].save.assert_called_once()
        saved_task = mocks["review_repo"].save.call_args[0][0]
        assert saved_task.status == "completed"
        assert saved_task.resolved_at is not None

    def test_no_review_task_id_skips(self):
        svc, mocks = _make_service()
        mocks["balance_repo"].get_by_sku.return_value = InventoryBalance(sku_id=FAKE_SKU_1, current_stock=5)

        svc.adjust(FAKE_SKU_1, actual_quantity=8, adjusted_by=FAKE_USER)

        mocks["review_repo"].get_by_id.assert_not_called()
