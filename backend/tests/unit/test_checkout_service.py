"""CheckoutService unit tests — mock repos, no DB."""

import uuid
from unittest.mock import MagicMock

import pytest

from application.sales.checkout_service import CheckoutService
from application.sales.schemas import CartItem, CheckoutRequest
from domain.inventory.models import InventoryBalance
from domain.product.models import SKU
from domain.sales.models import Sale


FAKE_CASHIER = uuid.uuid4()
FAKE_CUSTOMER = uuid.uuid4()
FAKE_SKU_1 = uuid.uuid4()
FAKE_SKU_2 = uuid.uuid4()


def _make_service(**overrides):
    defaults = {
        "sale_repo": MagicMock(),
        "movement_repo": MagicMock(),
        "balance_repo": MagicMock(),
        "customer_repo": MagicMock(),
        "ar_repo": MagicMock(),
        "price_history_repo": MagicMock(),
        "alert_repo": MagicMock(),
        "sku_repo": MagicMock(),
    }
    defaults.update(overrides)
    svc = CheckoutService(**defaults)
    return svc, defaults


def _make_request(**overrides):
    defaults = {
        "customer_id": None,
        "payment_method": "cash",
        "tax_mode": "none",
        "items": [
            CartItem(sku_id=FAKE_SKU_1, quantity=2, unit_price=100, product_name="A", spec="2P"),
        ],
        "discount_amount": 0,
        "note": None,
        "client_tx_id": None,
    }
    defaults.update(overrides)
    return CheckoutRequest(**defaults)


class TestCheckoutBasic:
    def test_successful_checkout(self):
        svc, mocks = _make_service()
        saved_sale = Sale(sale_id=uuid.uuid4(), cashier_id=FAKE_CASHIER, total=200)
        mocks["sale_repo"].save.return_value = saved_sale
        mocks["sale_repo"].get_by_client_tx_id.return_value = None

        result = svc.checkout(_make_request(), FAKE_CASHIER)

        assert result.success
        assert result.data["total"] == 200
        assert result.data["status"] == "completed"
        mocks["sale_repo"].save.assert_called_once()
        mocks["sale_repo"].save_lines.assert_called_once()

    def test_stock_movement_created_per_item(self):
        svc, mocks = _make_service()
        saved_sale = Sale(sale_id=uuid.uuid4(), cashier_id=FAKE_CASHIER, total=300)
        mocks["sale_repo"].save.return_value = saved_sale

        req = _make_request(items=[
            CartItem(sku_id=FAKE_SKU_1, quantity=2, unit_price=100, product_name="A", spec=None),
            CartItem(sku_id=FAKE_SKU_2, quantity=1, unit_price=100, product_name="B", spec=None),
        ])
        svc.checkout(req, FAKE_CASHIER)

        assert mocks["movement_repo"].save.call_count == 2
        assert mocks["balance_repo"].atomic_update.call_count == 2

    def test_balance_atomic_update_negative(self):
        svc, mocks = _make_service()
        saved_sale = Sale(sale_id=uuid.uuid4(), cashier_id=FAKE_CASHIER, total=200)
        mocks["sale_repo"].save.return_value = saved_sale

        svc.checkout(_make_request(), FAKE_CASHIER)

        mocks["balance_repo"].atomic_update.assert_called_once_with(FAKE_SKU_1, -2)


class TestCheckoutIdempotency:
    def test_duplicate_client_tx_id(self):
        svc, mocks = _make_service()
        existing_sale = Sale(sale_id=uuid.uuid4(), total=200)
        mocks["sale_repo"].get_by_client_tx_id.return_value = existing_sale

        req = _make_request(client_tx_id="tx-123")
        result = svc.checkout(req, FAKE_CASHIER)

        assert result.success
        assert result.data["status"] == "already_exists"
        mocks["sale_repo"].save.assert_not_called()

    def test_no_client_tx_id_no_check(self):
        svc, mocks = _make_service()
        saved_sale = Sale(sale_id=uuid.uuid4(), cashier_id=FAKE_CASHIER, total=200)
        mocks["sale_repo"].save.return_value = saved_sale

        result = svc.checkout(_make_request(client_tx_id=None), FAKE_CASHIER)

        assert result.success
        mocks["sale_repo"].get_by_client_tx_id.assert_not_called()


class TestCheckoutMonthlyCredit:
    def test_accumulates_ar(self):
        svc, mocks = _make_service()
        saved_sale = Sale(sale_id=uuid.uuid4(), cashier_id=FAKE_CASHIER, total=200)
        mocks["sale_repo"].save.return_value = saved_sale
        mocks["ar_repo"].get_by_customer_period.return_value = None

        req = _make_request(customer_id=FAKE_CUSTOMER, payment_method="monthly_credit")
        svc.checkout(req, FAKE_CASHIER)

        mocks["ar_repo"].save.assert_called_once()

    def test_no_ar_for_cash(self):
        svc, mocks = _make_service()
        saved_sale = Sale(sale_id=uuid.uuid4(), cashier_id=FAKE_CASHIER, total=200)
        mocks["sale_repo"].save.return_value = saved_sale

        req = _make_request(payment_method="cash")
        svc.checkout(req, FAKE_CASHIER)

        mocks["ar_repo"].get_by_customer_period.assert_not_called()


class TestCheckoutPriceHistory:
    def test_records_price_history_with_customer(self):
        svc, mocks = _make_service()
        saved_sale = Sale(sale_id=uuid.uuid4(), cashier_id=FAKE_CASHIER, total=200)
        mocks["sale_repo"].save.return_value = saved_sale

        req = _make_request(customer_id=FAKE_CUSTOMER)
        svc.checkout(req, FAKE_CASHIER)

        mocks["price_history_repo"].upsert.assert_called_once()

    def test_no_price_history_without_customer(self):
        svc, mocks = _make_service()
        saved_sale = Sale(sale_id=uuid.uuid4(), cashier_id=FAKE_CASHIER, total=200)
        mocks["sale_repo"].save.return_value = saved_sale

        req = _make_request(customer_id=None)
        svc.checkout(req, FAKE_CASHIER)

        mocks["price_history_repo"].upsert.assert_not_called()


class TestCheckoutTax:
    def test_tax_none(self):
        svc, mocks = _make_service()
        saved_sale = Sale(sale_id=uuid.uuid4(), cashier_id=FAKE_CASHIER, total=200)
        mocks["sale_repo"].save.return_value = saved_sale

        req = _make_request(tax_mode="none")
        result = svc.checkout(req, FAKE_CASHIER)
        assert result.success
        # total = 100 * 2 = 200, no tax
        assert result.data["total"] == 200

    def test_tax_extra(self):
        svc, mocks = _make_service()
        saved_sale = Sale(sale_id=uuid.uuid4(), cashier_id=FAKE_CASHIER, total=210)
        mocks["sale_repo"].save.return_value = saved_sale

        req = _make_request(tax_mode="extra")
        result = svc.checkout(req, FAKE_CASHIER)
        assert result.success
        # Sale was saved with calculated amounts; mock returns 210
        assert result.data["total"] == 210


class TestCheckoutLowStockAlert:
    """check_low_stock() 是 public method，由 API 層在 commit 後呼叫。"""

    def _items(self):
        return [CartItem(sku_id=FAKE_SKU_1, quantity=2, unit_price=100, product_name="A", spec="2P")]

    def test_creates_alert_when_low(self):
        svc, mocks = _make_service()
        mocks["balance_repo"].get_by_sku.return_value = InventoryBalance(sku_id=FAKE_SKU_1, current_stock=3)
        mocks["sku_repo"].get_by_id.return_value = SKU(sku_id=FAKE_SKU_1, min_stock=5, brand="士林", spec="2P")

        svc.check_low_stock(self._items())

        mocks["alert_repo"].save.assert_called_once()
        alert = mocks["alert_repo"].save.call_args[0][0]
        assert alert.alert_type == "low_stock"
        assert alert.severity == "warning"
        assert alert.reference_id == FAKE_SKU_1

    def test_no_alert_when_stock_sufficient(self):
        svc, mocks = _make_service()
        mocks["balance_repo"].get_by_sku.return_value = InventoryBalance(sku_id=FAKE_SKU_1, current_stock=10)
        mocks["sku_repo"].get_by_id.return_value = SKU(sku_id=FAKE_SKU_1, min_stock=5)

        svc.check_low_stock(self._items())

        mocks["alert_repo"].save.assert_not_called()

    def test_fallback_zero_when_no_min_stock(self):
        svc, mocks = _make_service()
        mocks["balance_repo"].get_by_sku.return_value = InventoryBalance(sku_id=FAKE_SKU_1, current_stock=0)
        mocks["sku_repo"].get_by_id.return_value = SKU(sku_id=FAKE_SKU_1, min_stock=None)

        svc.check_low_stock(self._items())

        mocks["alert_repo"].save.assert_called_once()

    def test_alert_failure_does_not_break(self):
        svc, mocks = _make_service()
        mocks["balance_repo"].get_by_sku.return_value = InventoryBalance(sku_id=FAKE_SKU_1, current_stock=0)
        mocks["sku_repo"].get_by_id.return_value = SKU(sku_id=FAKE_SKU_1, min_stock=5)
        mocks["alert_repo"].save.side_effect = RuntimeError("DB error")

        # 不拋異常
        svc.check_low_stock(self._items())

    def test_checkout_does_not_trigger_alert(self):
        """checkout() 本身不呼叫 check_low_stock — 由 API commit 後觸發。"""
        svc, mocks = _make_service()
        saved_sale = Sale(sale_id=uuid.uuid4(), cashier_id=FAKE_CASHIER, total=200)
        mocks["sale_repo"].save.return_value = saved_sale
        mocks["balance_repo"].get_by_sku.return_value = InventoryBalance(sku_id=FAKE_SKU_1, current_stock=0)
        mocks["sku_repo"].get_by_id.return_value = SKU(sku_id=FAKE_SKU_1, min_stock=5)

        svc.checkout(_make_request(), FAKE_CASHIER)

        # checkout 本身不觸發 alert，alert_repo.save 不該被呼叫
        mocks["alert_repo"].save.assert_not_called()
