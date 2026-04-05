"""Customer + AccountsReceivable repository 實作。"""

from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from domain.customer.models import AccountsReceivable, Customer
from domain.customer.repository import AccountsReceivableRepository, CustomerRepository
from infrastructure.persistence.orm_models import AccountsReceivableORM, CustomerORM


class SqlCustomerRepository(CustomerRepository):
    def __init__(self, session: Session):
        self._session = session

    def get_by_id(self, customer_id: UUID) -> Optional[Customer]:
        orm = self._session.get(CustomerORM, customer_id)
        return self._to_domain(orm) if orm else None

    # 所有可寫入欄位（domain → ORM 映射）
    _FIELDS = [
        "name", "short_name", "tax_id", "customer_type", "customer_code",
        "phone", "contact_person", "mobile", "email", "line_id",
        "address", "shipping_address",
        "payment_terms", "payment_days", "price_level", "credit_limit", "discount_rate",
        "allow_debt", "invoice_type", "invoice_title", "invoice_address", "invoice_delivery",
        "sales_rep", "source", "customer_level", "cooperation_status", "tags",
        "note", "is_active", "version",
    ]

    def save(self, customer: Customer) -> Customer:
        existing = self._session.get(CustomerORM, customer.customer_id)
        if existing:
            for f in self._FIELDS:
                setattr(existing, f, getattr(customer, f))
            self._session.flush()
            return self._to_domain(existing)

        data = {f: getattr(customer, f) for f in self._FIELDS}
        data["customer_id"] = customer.customer_id
        orm = CustomerORM(**data)
        self._session.add(orm)
        self._session.flush()
        return self._to_domain(orm)

    def list_all(self, offset: int = 0, limit: int = 20) -> list[Customer]:
        orms = (
            self._session.query(CustomerORM)
            .filter(CustomerORM.is_active == True)  # noqa: E712
            .order_by(CustomerORM.name)
            .offset(offset)
            .limit(limit)
            .all()
        )
        return [self._to_domain(o) for o in orms]

    @staticmethod
    def _to_domain(orm: CustomerORM) -> Customer:
        return Customer(
            customer_id=orm.customer_id,
            name=orm.name,
            short_name=orm.short_name,
            tax_id=orm.tax_id,
            customer_type=orm.customer_type,
            customer_code=orm.customer_code,
            phone=orm.phone,
            contact_person=orm.contact_person,
            mobile=orm.mobile,
            email=orm.email,
            line_id=orm.line_id,
            address=orm.address,
            shipping_address=orm.shipping_address,
            payment_terms=orm.payment_terms,
            payment_days=orm.payment_days,
            price_level=orm.price_level,
            credit_limit=float(orm.credit_limit) if orm.credit_limit else None,
            discount_rate=float(orm.discount_rate) if orm.discount_rate else None,
            allow_debt=orm.allow_debt,
            invoice_type=orm.invoice_type,
            invoice_title=orm.invoice_title,
            invoice_address=orm.invoice_address,
            invoice_delivery=orm.invoice_delivery,
            sales_rep=orm.sales_rep,
            source=orm.source,
            customer_level=orm.customer_level,
            cooperation_status=orm.cooperation_status,
            tags=orm.tags,
            note=orm.note,
            is_active=orm.is_active,
            version=orm.version,
        )


class SqlAccountsReceivableRepository(AccountsReceivableRepository):
    def __init__(self, session: Session):
        self._session = session

    def get_by_id(self, ar_id: UUID) -> Optional[AccountsReceivable]:
        orm = self._session.get(AccountsReceivableORM, ar_id)
        return self._to_domain(orm) if orm else None

    def save(self, ar: AccountsReceivable) -> AccountsReceivable:
        existing = self._session.get(AccountsReceivableORM, ar.ar_id)
        if existing:
            existing.total_amount = ar.total_amount
            existing.paid_amount = ar.paid_amount
            existing.status = ar.status
            existing.paid_at = ar.paid_at
            existing.note = ar.note
            self._session.flush()
            return self._to_domain(existing)

        orm = AccountsReceivableORM(
            ar_id=ar.ar_id,
            customer_id=ar.customer_id,
            period=ar.period,
            total_amount=ar.total_amount,
            paid_amount=ar.paid_amount,
            status=ar.status,
            due_date=ar.due_date,
            note=ar.note,
        )
        self._session.add(orm)
        self._session.flush()
        return self._to_domain(orm)

    def get_by_customer_period(self, customer_id: UUID, period: str) -> Optional[AccountsReceivable]:
        orm = (
            self._session.query(AccountsReceivableORM)
            .filter(
                AccountsReceivableORM.customer_id == customer_id,
                AccountsReceivableORM.period == period,
            )
            .first()
        )
        return self._to_domain(orm) if orm else None

    @staticmethod
    def _to_domain(orm: AccountsReceivableORM) -> AccountsReceivable:
        return AccountsReceivable(
            ar_id=orm.ar_id,
            customer_id=orm.customer_id,
            period=orm.period,
            total_amount=float(orm.total_amount),
            paid_amount=float(orm.paid_amount),
            status=orm.status,
            due_date=orm.due_date,
            paid_at=orm.paid_at,
            note=orm.note,
        )