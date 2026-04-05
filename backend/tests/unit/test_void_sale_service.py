"""VoidSaleService unit tests — mock repos, no DB."""

import uuid
from unittest.mock import MagicMock

import pytest

from application.sales.void_sale_service import VoidSaleService
from domain.inventory.models import StockMovement
from domain.sales.models import Sale


FAKE_USER = uuid.uuid4()
FAKE_CUSTOMER = uuid.uuid4()


def _make_service(**overrides):
    defaults = {
        "sale_repo": MagicMock(),
        "movement_repo": MagicMock(),
        "balance_repo": MagicMock(),
        "ar_repo": MagicMock(),
    }
    defaults.update(overrides)
    return VoidSaleService(**defaults), defaults


class TestVoidBasic:
    def test_void_completed_sale(self):
        svc, mocks = _make_service()
        sale = Sale(sale_id=uuid.uuid4(), status="completed", total=500, payment_method="cash")
        mocks["sale_repo"].get_by_id.return_value = sale
        mocks["movement_repo"].list_by_reference.return_value = [
            StockMovement(sku_id=uuid.uuid4(), quantity=-3, movement_type="sale", reference_type="sale"),
        ]

        result = svc.void(sale.sale_id, FAKE_USER, reason="客人退貨")

        assert result.success
        mocks["sale_repo"].save.assert_called_once()
        saved_sale = mocks["sale_repo"].save.call_args[0][0]
        assert saved_sale.status == "voided"
        assert "客人退貨" in saved_sale.note

    def test_void_nonexistent_sale(self):
        svc, mocks = _make_service()
        mocks["sale_repo"].get_by_id.return_value = None

        result = svc.void(uuid.uuid4(), FAKE_USER)

        assert not result.success
        assert result.code == "ERR-BIZ-002"

    def test_void_already_voided(self):
        svc, mocks = _make_service()
        sale = Sale(sale_id=uuid.uuid4(), status="voided")
        mocks["sale_repo"].get_by_id.return_value = sale

        result = svc.void(sale.sale_id, FAKE_USER)

        assert not result.success
        assert result.code == "ERR-BIZ-001"


class TestVoidInventoryReturn:
    def test_creates_return_movements(self):
        svc, mocks = _make_service()
        sku1 = uuid.uuid4()
        sku2 = uuid.uuid4()
        sale = Sale(sale_id=uuid.uuid4(), status="completed", total=500, payment_method="cash")
        mocks["sale_repo"].get_by_id.return_value = sale
        mocks["movement_repo"].list_by_reference.return_value = [
            StockMovement(sku_id=sku1, quantity=-3, movement_type="sale", reference_type="sale"),
            StockMovement(sku_id=sku2, quantity=-2, movement_type="sale", reference_type="sale"),
        ]

        svc.void(sale.sale_id, FAKE_USER)

        assert mocks["movement_repo"].save.call_count == 2
        assert mocks["balance_repo"].atomic_update.call_count == 2
        # First call: sku1, +3
        mocks["balance_repo"].atomic_update.assert_any_call(sku1, 3)
        mocks["balance_repo"].atomic_update.assert_any_call(sku2, 2)


class TestVoidMonthlyCredit:
    def test_deducts_ar(self):
        svc, mocks = _make_service()
        sale = Sale(
            sale_id=uuid.uuid4(), status="completed", total=500,
            payment_method="monthly_credit", customer_id=FAKE_CUSTOMER,
        )
        mocks["sale_repo"].get_by_id.return_value = sale
        mocks["movement_repo"].list_by_reference.return_value = []

        from domain.customer.models import AccountsReceivable
        ar = AccountsReceivable(customer_id=FAKE_CUSTOMER, period="2026-04", total_amount=1000, status="open")
        mocks["ar_repo"].get_by_customer_period.return_value = ar

        svc.void(sale.sale_id, FAKE_USER)

        mocks["ar_repo"].save.assert_called_once()
        saved_ar = mocks["ar_repo"].save.call_args[0][0]
        assert saved_ar.total_amount == 500  # 1000 - 500

    def test_no_ar_deduction_for_cash(self):
        svc, mocks = _make_service()
        sale = Sale(sale_id=uuid.uuid4(), status="completed", total=500, payment_method="cash")
        mocks["sale_repo"].get_by_id.return_value = sale
        mocks["movement_repo"].list_by_reference.return_value = []

        svc.void(sale.sale_id, FAKE_USER)

        mocks["ar_repo"].get_by_customer_period.assert_not_called()

    def test_void_without_reason(self):
        svc, mocks = _make_service()
        sale = Sale(sale_id=uuid.uuid4(), status="completed", total=100, payment_method="cash")
        mocks["sale_repo"].get_by_id.return_value = sale
        mocks["movement_repo"].list_by_reference.return_value = []

        result = svc.void(sale.sale_id, FAKE_USER, reason=None)

        assert result.success
        saved_sale = mocks["sale_repo"].save.call_args[0][0]
        assert saved_sale.note == "[作廢]"
