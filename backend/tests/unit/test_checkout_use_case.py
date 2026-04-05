"""CheckoutUseCase + VoidSaleUseCase unit tests."""

import uuid
from unittest.mock import MagicMock

import pytest

from application.use_cases.checkout import CheckoutUseCase, VoidSaleUseCase
from core.results import Result
from domain.alert.models import OperationalAlert
from domain.inventory.models import InventoryBalance
from domain.product.models import SKU


FAKE_CASHIER = uuid.uuid4()
FAKE_SKU = uuid.uuid4()


class _FakeItem:
    def __init__(self, sku_id):
        self.sku_id = sku_id


class _FakeRequest:
    def __init__(self, items=None, client_tx_id=None):
        self.items = items or [_FakeItem(FAKE_SKU)]
        self.client_tx_id = client_tx_id


def _make_checkout_uc():
    return CheckoutUseCase(
        checkout_service=MagicMock(),
        audit_service=MagicMock(),
        alert_repo=MagicMock(),
        balance_repo=MagicMock(),
        sku_repo=MagicMock(),
        session=MagicMock(),
    )


def _make_void_uc():
    return VoidSaleUseCase(
        void_service=MagicMock(),
        audit_service=MagicMock(),
        session=MagicMock(),
    )


# ── CheckoutUseCase ──────────────────────────────────────


class TestCheckoutUseCase:
    def test_successful_checkout(self):
        uc = _make_checkout_uc()
        uc._checkout.checkout.return_value = Result.ok(data={
            "sale_id": str(uuid.uuid4()), "total": 200, "status": "completed", "item_count": 1,
        })

        result = uc.execute(_FakeRequest(), FAKE_CASHIER)

        assert result.success
        uc._audit.log.assert_called_once()
        uc._session.commit.assert_called_once()

    def test_idempotent_no_alert(self):
        """冪等回傳（already_exists）不觸發 low stock alert。"""
        uc = _make_checkout_uc()
        uc._checkout.checkout.return_value = Result.ok(data={
            "sale_id": str(uuid.uuid4()), "total": 200, "status": "already_exists",
        })

        uc.execute(_FakeRequest(client_tx_id="tx-1"), FAKE_CASHIER)

        # alert_repo.save 不該被呼叫（冪等回傳不做 post-commit）
        uc._alert_repo.save.assert_not_called()

    def test_no_commit_on_failure(self):
        uc = _make_checkout_uc()
        uc._checkout.checkout.return_value = Result.fail("ERR", "fail")

        result = uc.execute(_FakeRequest(), FAKE_CASHIER)

        assert not result.success
        uc._session.commit.assert_not_called()

    def test_audit_in_use_case(self):
        uc = _make_checkout_uc()
        uc._checkout.checkout.return_value = Result.ok(data={
            "sale_id": str(uuid.uuid4()), "total": 100, "status": "completed", "item_count": 1,
        })

        uc.execute(_FakeRequest(), FAKE_CASHIER)

        uc._audit.log.assert_called_once()
        args = uc._audit.log.call_args[0]
        assert args[0] == FAKE_CASHIER
        assert args[1] == "checkout"


# ── Low Stock Alert Dedup ────────────────────────────────


class TestCheckoutLowStockDedup:
    def test_creates_alert_when_no_active(self):
        uc = _make_checkout_uc()
        uc._checkout.checkout.return_value = Result.ok(data={
            "sale_id": str(uuid.uuid4()), "status": "completed", "total": 100, "item_count": 1,
        })
        uc._balance_repo.get_by_sku.return_value = InventoryBalance(sku_id=FAKE_SKU, current_stock=3)
        uc._sku_repo.get_by_id.return_value = SKU(sku_id=FAKE_SKU, min_stock=5, brand="士林", spec="2P")
        uc._alert_repo.list_active_by_reference.return_value = []  # 無 active alert

        uc.execute(_FakeRequest(), FAKE_CASHIER)

        uc._alert_repo.save.assert_called_once()
        alert = uc._alert_repo.save.call_args[0][0]
        assert alert.alert_type == "low_stock"

    def test_no_duplicate_when_active_exists(self):
        uc = _make_checkout_uc()
        uc._checkout.checkout.return_value = Result.ok(data={
            "sale_id": str(uuid.uuid4()), "status": "completed", "total": 100, "item_count": 1,
        })
        uc._balance_repo.get_by_sku.return_value = InventoryBalance(sku_id=FAKE_SKU, current_stock=3)
        uc._sku_repo.get_by_id.return_value = SKU(sku_id=FAKE_SKU, min_stock=5)
        # 已有 active alert
        uc._alert_repo.list_active_by_reference.return_value = [
            OperationalAlert(alert_type="low_stock"),
        ]

        uc.execute(_FakeRequest(), FAKE_CASHIER)

        uc._alert_repo.save.assert_not_called()  # 不重建

    def test_no_alert_when_stock_sufficient(self):
        uc = _make_checkout_uc()
        uc._checkout.checkout.return_value = Result.ok(data={
            "sale_id": str(uuid.uuid4()), "status": "completed", "total": 100, "item_count": 1,
        })
        uc._balance_repo.get_by_sku.return_value = InventoryBalance(sku_id=FAKE_SKU, current_stock=10)
        uc._sku_repo.get_by_id.return_value = SKU(sku_id=FAKE_SKU, min_stock=5)

        uc.execute(_FakeRequest(), FAKE_CASHIER)

        uc._alert_repo.list_active_by_reference.assert_not_called()
        uc._alert_repo.save.assert_not_called()

    def test_alert_failure_does_not_break(self):
        uc = _make_checkout_uc()
        uc._checkout.checkout.return_value = Result.ok(data={
            "sale_id": str(uuid.uuid4()), "status": "completed", "total": 100, "item_count": 1,
        })
        uc._balance_repo.get_by_sku.return_value = InventoryBalance(sku_id=FAKE_SKU, current_stock=0)
        uc._sku_repo.get_by_id.return_value = SKU(sku_id=FAKE_SKU, min_stock=5)
        uc._alert_repo.list_active_by_reference.return_value = []
        uc._alert_repo.save.side_effect = RuntimeError("DB error")

        result = uc.execute(_FakeRequest(), FAKE_CASHIER)

        assert result.success  # 主流程不受影響


# ── VoidSaleUseCase ──────────────────────────────────────


class TestVoidSaleUseCase:
    def test_successful_void(self):
        uc = _make_void_uc()
        uc._void.void.return_value = Result.ok(message="已作廢")

        result = uc.execute(uuid.uuid4(), uuid.uuid4(), reason="客退")

        assert result.success
        uc._audit.log.assert_called_once()
        uc._session.commit.assert_called_once()

    def test_no_commit_on_failure(self):
        uc = _make_void_uc()
        uc._void.void.return_value = Result.fail("ERR", "不存在")

        result = uc.execute(uuid.uuid4(), uuid.uuid4())

        assert not result.success
        uc._session.commit.assert_not_called()

    def test_audit_includes_reason(self):
        uc = _make_void_uc()
        sale_id = uuid.uuid4()
        uc._void.void.return_value = Result.ok(message="已作廢")

        uc.execute(sale_id, uuid.uuid4(), reason="品質問題")

        detail = uc._audit.log.call_args[1]["detail"]
        assert detail["reason"] == "品質問題"
