"""PaymentService — 收款記錄 use case。

職責：
  - 載入 AR
  - 累加付款金額
  - 推導狀態（paid / partial_paid）
  - 全額收款時設定 paid_at
"""

from datetime import datetime, timezone
from uuid import UUID

from core.results import Result
from domain.customer.repository import AccountsReceivableRepository


class PaymentService:
    def __init__(self, ar_repo: AccountsReceivableRepository):
        self._ar_repo = ar_repo

    def record_payment(self, ar_id: UUID, amount: float) -> Result:
        ar = self._ar_repo.get_by_id(ar_id)
        if not ar:
            return Result.fail("ERR-BIZ-002", "應收帳款不存在")

        ar.paid_amount += amount
        if ar.paid_amount >= ar.total_amount:
            ar.status = "paid"
            ar.paid_at = datetime.now(timezone.utc)
        elif ar.paid_amount > 0:
            ar.status = "partial_paid"

        self._ar_repo.save(ar)

        return Result.ok(
            data={"paid_amount": ar.paid_amount, "status": ar.status},
            message=f"收款 ${amount:.0f}，累計已收 ${ar.paid_amount:.0f}",
        )
