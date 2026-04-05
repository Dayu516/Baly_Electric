"""GenerateStatementService unit tests — mock repos, no DB."""

import uuid
from unittest.mock import MagicMock

import pytest

from application.customer.generate_statement_service import GenerateStatementService
from domain.customer.models import AccountsReceivable, Customer


FAKE_CUSTOMER = uuid.uuid4()
FAKE_USER = uuid.uuid4()


def _make_service(**overrides):
    defaults = {
        "customer_repo": MagicMock(),
        "ar_repo": MagicMock(),
        "review_repo": MagicMock(),
        "query_service": MagicMock(),
    }
    defaults.update(overrides)
    return GenerateStatementService(**defaults), defaults


def _monthly_customer(customer_id=FAKE_CUSTOMER):
    return Customer(customer_id=customer_id, name="測試客戶", payment_terms="monthly_credit")


class TestGenerateStatement:
    def test_successful_generation(self):
        svc, mocks = _make_service()
        mocks["customer_repo"].get_by_id.return_value = _monthly_customer()
        mocks["ar_repo"].get_by_customer_period.return_value = None
        mocks["query_service"].sum_customer_sales.return_value = 5000.0
        mocks["ar_repo"].save.side_effect = lambda ar: ar

        result = svc.generate(FAKE_CUSTOMER, "2026-03", FAKE_USER)

        assert result.success
        assert result.data["total_amount"] == 5000.0
        assert result.data["period"] == "2026-03"
        mocks["ar_repo"].save.assert_called_once()
        mocks["review_repo"].save.assert_called_once()

    def test_customer_not_found(self):
        svc, mocks = _make_service()
        mocks["customer_repo"].get_by_id.return_value = None

        result = svc.generate(FAKE_CUSTOMER, "2026-03", FAKE_USER)

        assert not result.success
        assert result.code == "ERR-BIZ-002"

    def test_non_monthly_credit_rejected(self):
        svc, mocks = _make_service()
        customer = Customer(customer_id=FAKE_CUSTOMER, name="現金客", payment_terms="cash")
        mocks["customer_repo"].get_by_id.return_value = customer

        result = svc.generate(FAKE_CUSTOMER, "2026-03", FAKE_USER)

        assert not result.success
        assert "非月結" in result.message

    def test_duplicate_period_rejected(self):
        svc, mocks = _make_service()
        mocks["customer_repo"].get_by_id.return_value = _monthly_customer()
        mocks["ar_repo"].get_by_customer_period.return_value = AccountsReceivable(
            customer_id=FAKE_CUSTOMER, period="2026-03", total_amount=1000,
        )

        result = svc.generate(FAKE_CUSTOMER, "2026-03", FAKE_USER)

        assert not result.success
        assert "已存在" in result.message

    def test_zero_sales_no_ar(self):
        svc, mocks = _make_service()
        mocks["customer_repo"].get_by_id.return_value = _monthly_customer()
        mocks["ar_repo"].get_by_customer_period.return_value = None
        mocks["query_service"].sum_customer_sales.return_value = 0

        result = svc.generate(FAKE_CUSTOMER, "2026-03", FAKE_USER)

        assert result.success
        assert "無月結金額" in result.message
        mocks["ar_repo"].save.assert_not_called()

    def test_review_task_created(self):
        svc, mocks = _make_service()
        mocks["customer_repo"].get_by_id.return_value = _monthly_customer()
        mocks["ar_repo"].get_by_customer_period.return_value = None
        mocks["query_service"].sum_customer_sales.return_value = 3000.0
        mocks["ar_repo"].save.side_effect = lambda ar: ar

        svc.generate(FAKE_CUSTOMER, "2026-03", FAKE_USER)

        task = mocks["review_repo"].save.call_args[0][0]
        assert task.review_type == "monthly_reconcile"
        assert "測試客戶" in task.title

    def test_ar_fields_correct(self):
        svc, mocks = _make_service()
        mocks["customer_repo"].get_by_id.return_value = _monthly_customer()
        mocks["ar_repo"].get_by_customer_period.return_value = None
        mocks["query_service"].sum_customer_sales.return_value = 2500.0
        mocks["ar_repo"].save.side_effect = lambda ar: ar

        svc.generate(FAKE_CUSTOMER, "2026-03", FAKE_USER)

        ar = mocks["ar_repo"].save.call_args[0][0]
        assert ar.customer_id == FAKE_CUSTOMER
        assert ar.period == "2026-03"
        assert ar.total_amount == 2500.0
        assert ar.status == "open"
