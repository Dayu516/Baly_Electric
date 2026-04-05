"""GenerateStatementUseCase + RecordPaymentUseCase — 月結與收款正式流程。

GenerateStatementUseCase：
  1. 呼叫 GenerateStatementService.generate()
  2. Audit
  3. Commit

RecordPaymentUseCase：
  1. 呼叫 PaymentService.record_payment()
  2. Audit
  3. 若全額付清 + auto_close_review_on_paid → 自動結案 ReviewTask
  4. Commit
"""

from datetime import datetime, timezone
from uuid import UUID

from core.logging import get_logger
from core.results import Result
from domain.review.repository import ReviewTaskRepository
from infrastructure.persistence.repositories.audit_repo_impl import AuditService

logger = get_logger("use_case.monthly_statement")


class GenerateStatementUseCase:
    def __init__(self, statement_service, audit_service: AuditService, session):
        self._service = statement_service
        self._audit = audit_service
        self._session = session

    def execute(self, customer_id: UUID, period: str, generated_by: UUID) -> Result:
        result = self._service.generate(customer_id, period, generated_by)
        if not result.success:
            return result

        self._audit.log(
            generated_by, "generate_statement", "accounts_receivable",
            detail=result.data,
        )

        self._session.commit()
        return result


class RecordPaymentUseCase:
    def __init__(
        self,
        payment_service,
        audit_service: AuditService,
        review_repo: ReviewTaskRepository,
        settings_repo,
        session,
    ):
        self._payment = payment_service
        self._audit = audit_service
        self._review_repo = review_repo
        self._settings_repo = settings_repo
        self._session = session

    def execute(self, ar_id: UUID, amount: float, user_id: UUID) -> Result:
        result = self._payment.record_payment(ar_id, amount)
        if not result.success:
            return result

        # 全額付清 → 嘗試自動結案 ReviewTask
        if result.data and result.data.get("status") == "paid":
            self._try_auto_close_review(ar_id, user_id)

        self._audit.log(
            user_id, "record_payment", "accounts_receivable",
            entity_id=ar_id,
            detail={"amount": amount, "new_paid": result.data["paid_amount"]},
        )

        self._session.commit()
        return result

    def _try_auto_close_review(self, ar_id: UUID, user_id: UUID) -> None:
        """依設定決定是否自動關閉 monthly_reconcile ReviewTask。"""
        try:
            auto_close = True  # 預設
            if self._settings_repo:
                param = self._settings_repo.get_parameter("auto_close_review_on_paid")
                if param and param.value == "false":
                    auto_close = False

            if not auto_close:
                return

            task = self._review_repo.find_by_reference("accounts_receivable", ar_id)
            if task and task.status in ("pending", "claimed"):
                task.status = "completed"
                task.resolved_at = datetime.now(timezone.utc)
                task.resolved_by = user_id
                self._review_repo.save(task)
                logger.info("review_auto_closed", task_id=str(task.task_id), ar_id=str(ar_id))
        except Exception:
            logger.warning("auto_close_review_failed", ar_id=str(ar_id), exc_info=True)
