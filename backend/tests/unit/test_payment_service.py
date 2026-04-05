"""PaymentService unit tests — mock repos, no DB."""

import uuid
from unittest.mock import MagicMock

import pytest

from application.customer.payment_service import PaymentService
from domain.customer.models import AccountsReceivable


FAKE_AR = uuid.uuid4()
FAKE_CUSTOMER = uuid.uuid4()


def _make_service(**overrides):
    defaults = {"ar_repo": MagicMock()}
    defaults.update(overrides)
    return PaymentService(**defaults), defaults


def _ar(total=1000, paid=0, status="open"):
    return AccountsReceivable(
        ar_id=FAKE_AR, customer_id=FAKE_CUSTOMER,
        period="2026-03", total_amount=total, paid_amount=paid, status=status,
    )


class TestRecordPayment:
    def test_partial_payment(self):
        svc, mocks = _make_service()
        mocks["ar_repo"].get_by_id.return_value = _ar(total=1000, paid=0)

        result = svc.record_payment(FAKE_AR, 300)

        assert result.success
        assert result.data["paid_amount"] == 300
        assert result.data["status"] == "partial_paid"
        mocks["ar_repo"].save.assert_called_once()

    def test_full_payment(self):
        svc, mocks = _make_service()
        mocks["ar_repo"].get_by_id.return_value = _ar(total=1000, paid=0)

        result = svc.record_payment(FAKE_AR, 1000)

        assert result.success
        assert result.data["status"] == "paid"
        saved_ar = mocks["ar_repo"].save.call_args[0][0]
        assert saved_ar.paid_at is not None

    def test_accumulative_payment(self):
        svc, mocks = _make_service()
        mocks["ar_repo"].get_by_id.return_value = _ar(total=1000, paid=400)

        result = svc.record_payment(FAKE_AR, 600)

        assert result.success
        assert result.data["paid_amount"] == 1000
        assert result.data["status"] == "paid"

    def test_overpayment_allowed(self):
        """原本行為允許超額付款（paid_amount > total_amount 仍 status=paid）。"""
        svc, mocks = _make_service()
        mocks["ar_repo"].get_by_id.return_value = _ar(total=1000, paid=800)

        result = svc.record_payment(FAKE_AR, 500)

        assert result.success
        assert result.data["paid_amount"] == 1300
        assert result.data["status"] == "paid"

    def test_ar_not_found(self):
        svc, mocks = _make_service()
        mocks["ar_repo"].get_by_id.return_value = None

        result = svc.record_payment(uuid.uuid4(), 100)

        assert not result.success
        assert result.code == "ERR-BIZ-002"
        mocks["ar_repo"].save.assert_not_called()

    def test_paid_at_only_set_on_full(self):
        svc, mocks = _make_service()
        mocks["ar_repo"].get_by_id.return_value = _ar(total=1000, paid=0)

        svc.record_payment(FAKE_AR, 500)

        saved_ar = mocks["ar_repo"].save.call_args[0][0]
        assert saved_ar.paid_at is None  # partial, no paid_at
