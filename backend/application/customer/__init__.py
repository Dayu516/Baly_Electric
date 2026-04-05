"""Customer 模組組裝入口。

所有 Customer service 的建立都透過這裡，API 層不可自行組裝 repo。

Usage（API 層）：
    from application.customer import build_generate_statement_service, build_payment_service
    svc = build_payment_service(session)
"""

from sqlalchemy.orm import Session

from application.customer.generate_statement_service import GenerateStatementService
from application.customer.payment_service import PaymentService
from infrastructure.persistence.query_services.sales_query_service import SalesQueryService
from infrastructure.persistence.repositories.customer_repo_impl import (
    SqlAccountsReceivableRepository,
    SqlCustomerRepository,
)
from infrastructure.persistence.repositories.review_repo_impl import SqlReviewTaskRepository


def build_generate_statement_service(session: Session) -> GenerateStatementService:
    return GenerateStatementService(
        customer_repo=SqlCustomerRepository(session),
        ar_repo=SqlAccountsReceivableRepository(session),
        review_repo=SqlReviewTaskRepository(session),
        query_service=SalesQueryService(session),
    )


def build_payment_service(session: Session) -> PaymentService:
    return PaymentService(
        ar_repo=SqlAccountsReceivableRepository(session),
    )


def build_customer_repository(session: Session):
    return SqlCustomerRepository(session)
