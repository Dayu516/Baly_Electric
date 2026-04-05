"""GenerateStatementService — 月結單生成 use case。

Transaction 邊界：
  Transaction 內：
    INSERT accounts_receivable
    INSERT review_task（monthly_reconcile，待人工確認）
    INSERT audit_event
"""

import uuid
from datetime import datetime, timezone

from core.logging import get_logger
from core.results import Result
from domain.customer.models import AccountsReceivable
from domain.customer.repository import AccountsReceivableRepository, CustomerRepository
from domain.review.models import ReviewTask
from domain.review.repository import ReviewTaskRepository
from infrastructure.persistence.query_services.sales_query_service import SalesQueryService

logger = get_logger("generate_statement")


class GenerateStatementService:
    def __init__(
        self,
        customer_repo: CustomerRepository,
        ar_repo: AccountsReceivableRepository,
        review_repo: ReviewTaskRepository,
        query_service: SalesQueryService,
    ):
        self._customer_repo = customer_repo
        self._ar_repo = ar_repo
        self._review_repo = review_repo
        self._query = query_service

    def generate(self, customer_id: uuid.UUID, period: str, generated_by: uuid.UUID) -> Result:
        """生成月結單。period 格式：YYYY-MM。"""

        # 檢查客戶
        customer = self._customer_repo.get_by_id(customer_id)
        if not customer:
            return Result.fail("ERR-BIZ-002", "客戶不存在")

        if customer.payment_terms != "monthly_credit":
            return Result.fail("ERR-BIZ-001", "此客戶非月結客戶")

        # 檢查是否已有此期月結單
        existing = self._ar_repo.get_by_customer_period(customer_id, period)
        if existing:
            return Result.fail("ERR-BIZ-003", f"{period} 月結單已存在")

        # 彙總銷售金額
        total = self._query.sum_customer_sales(str(customer_id), period)
        if total <= 0:
            return Result.ok(message=f"{period} 無月結金額")

        # 建立應收帳款
        ar = AccountsReceivable(
            customer_id=customer_id,
            period=period,
            total_amount=total,
            status="open",
        )
        saved_ar = self._ar_repo.save(ar)

        # 建立 ReviewTask
        review = ReviewTask(
            review_type="monthly_reconcile",
            title=f"{customer.name} {period} 月結單 ${total:.0f}",
            detail=f"客戶：{customer.name}\n期間：{period}\n金額：${total:.2f}",
            reference_type="accounts_receivable",
            reference_id=saved_ar.ar_id,
        )
        self._review_repo.save(review)

        logger.info(
            "statement_generated",
            customer_id=str(customer_id),
            period=period,
            total=total,
        )

        return Result.ok(
            data={
                "ar_id": str(saved_ar.ar_id),
                "customer_name": customer.name,
                "period": period,
                "total_amount": total,
            },
            message=f"月結單已生成：{customer.name} {period} ${total:.0f}",
        )