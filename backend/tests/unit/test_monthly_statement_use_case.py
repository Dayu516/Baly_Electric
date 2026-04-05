"""GenerateStatementUseCase + RecordPaymentUseCase unit tests."""

import uuid
from unittest.mock import MagicMock

import pytest

from application.use_cases.monthly_statement import (
    GenerateStatementUseCase,
    RecordPaymentUseCase,
)
from core.results import Result
from domain.review.models import ReviewTask
from domain.settings.models import SystemParameter


FAKE_USER = uuid.uuid4()
FAKE_CUSTOMER = uuid.uuid4()
FAKE_AR = uuid.uuid4()


# ── GenerateStatementUseCase ─────────────────────────────


class TestGenerateStatementUseCase:
    def _make(self):
        svc = MagicMock()
        audit = MagicMock()
        session = MagicMock()
        uc = GenerateStatementUseCase(svc, audit, session)
        return uc, svc, audit, session

    def test_successful_generate(self):
        uc, svc, audit, session = self._make()
        svc.generate.return_value = Result.ok(data={"ar_id": str(FAKE_AR), "total_amount": 5000})

        result = uc.execute(FAKE_CUSTOMER, "2026-03", FAKE_USER)

        assert result.success
        audit.log.assert_called_once()
        session.commit.assert_called_once()

    def test_no_commit_on_failure(self):
        uc, svc, audit, session = self._make()
        svc.generate.return_value = Result.fail("ERR", "客戶不存在")

        result = uc.execute(FAKE_CUSTOMER, "2026-03", FAKE_USER)

        assert not result.success
        session.commit.assert_not_called()

    def test_duplicate_period_still_rejected(self):
        """自然冪等：service 層的重複月份防護仍然有效。"""
        uc, svc, audit, session = self._make()
        svc.generate.return_value = Result.fail("ERR-BIZ-003", "已存在")

        result = uc.execute(FAKE_CUSTOMER, "2026-03", FAKE_USER)

        assert not result.success
        assert "已存在" in result.message


# ── RecordPaymentUseCase ─────────────────────────────────


class TestRecordPaymentUseCase:
    def _make(self, auto_close=True):
        payment_svc = MagicMock()
        audit = MagicMock()
        review_repo = MagicMock()
        settings_repo = MagicMock()
        session = MagicMock()

        if auto_close:
            settings_repo.get_parameter.return_value = SystemParameter(key="auto_close_review_on_paid", value="true")
        else:
            settings_repo.get_parameter.return_value = SystemParameter(key="auto_close_review_on_paid", value="false")

        uc = RecordPaymentUseCase(payment_svc, audit, review_repo, settings_repo, session)
        return uc, payment_svc, audit, review_repo, session

    def test_successful_payment(self):
        uc, svc, audit, review_repo, session = self._make()
        svc.record_payment.return_value = Result.ok(data={"paid_amount": 1000, "status": "partial_paid"})

        result = uc.execute(FAKE_AR, 1000, FAKE_USER)

        assert result.success
        audit.log.assert_called_once()
        session.commit.assert_called_once()

    def test_no_commit_on_failure(self):
        uc, svc, audit, review_repo, session = self._make()
        svc.record_payment.return_value = Result.fail("ERR", "不存在")

        result = uc.execute(FAKE_AR, 1000, FAKE_USER)

        assert not result.success
        session.commit.assert_not_called()

    def test_auto_close_review_on_paid(self):
        uc, svc, audit, review_repo, session = self._make(auto_close=True)
        svc.record_payment.return_value = Result.ok(data={"paid_amount": 5000, "status": "paid"})
        task = ReviewTask(task_id=uuid.uuid4(), review_type="monthly_reconcile", status="pending")
        review_repo.find_by_reference.return_value = task

        uc.execute(FAKE_AR, 5000, FAKE_USER)

        review_repo.save.assert_called_once()
        saved_task = review_repo.save.call_args[0][0]
        assert saved_task.status == "completed"
        assert saved_task.resolved_at is not None

    def test_no_auto_close_when_disabled(self):
        uc, svc, audit, review_repo, session = self._make(auto_close=False)
        svc.record_payment.return_value = Result.ok(data={"paid_amount": 5000, "status": "paid"})

        uc.execute(FAKE_AR, 5000, FAKE_USER)

        review_repo.find_by_reference.assert_not_called()

    def test_no_auto_close_when_partial_paid(self):
        uc, svc, audit, review_repo, session = self._make(auto_close=True)
        svc.record_payment.return_value = Result.ok(data={"paid_amount": 1000, "status": "partial_paid"})

        uc.execute(FAKE_AR, 1000, FAKE_USER)

        review_repo.find_by_reference.assert_not_called()

    def test_no_review_task_found_ok(self):
        """找不到對應 ReviewTask 不影響主流程。"""
        uc, svc, audit, review_repo, session = self._make(auto_close=True)
        svc.record_payment.return_value = Result.ok(data={"paid_amount": 5000, "status": "paid"})
        review_repo.find_by_reference.return_value = None  # 沒找到

        result = uc.execute(FAKE_AR, 5000, FAKE_USER)

        assert result.success  # 不影響
        review_repo.save.assert_not_called()

    def test_audit_includes_amount(self):
        uc, svc, audit, review_repo, session = self._make()
        svc.record_payment.return_value = Result.ok(data={"paid_amount": 2000, "status": "partial_paid"})

        uc.execute(FAKE_AR, 2000, FAKE_USER)

        detail = audit.log.call_args[1]["detail"]
        assert detail["amount"] == 2000
        assert detail["new_paid"] == 2000
