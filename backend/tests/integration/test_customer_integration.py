"""Customer module integration tests — real DB, rollback after each test."""

import uuid

import pytest
from sqlalchemy import text

from application.customer import build_generate_statement_service, build_payment_service
from infrastructure.persistence.repositories.customer_repo_impl import SqlCustomerRepository
from domain.customer.models import Customer


@pytest.fixture
def customer_seed(db_session):
    """建立測試用基礎資料：月結客戶 + 已完成交易。"""
    customer_id = str(uuid.uuid4())
    cashier_id = str(uuid.uuid4())

    db_session.execute(text("""
        INSERT INTO customers (customer_id, name, payment_terms, is_active)
        VALUES (:cid, '月結客戶', 'monthly_credit', true)
    """), {"cid": customer_id})

    # 建一筆已完成交易（月結彙總用）
    sale_id = str(uuid.uuid4())
    db_session.execute(text("""
        INSERT INTO sales (sale_id, customer_id, cashier_id, status, payment_method, total, subtotal, tax_amount, discount_amount)
        VALUES (:sid, :cid, :uid, 'completed', 'monthly_credit', 3000, 3000, 0, 0)
    """), {"sid": sale_id, "cid": customer_id, "uid": cashier_id})

    db_session.flush()

    return {
        "customer_id": customer_id,
        "cashier_id": cashier_id,
        "sale_id": sale_id,
    }


# ── Customer CRUD ────────────────────────────────────────


class TestCustomerCrudIntegration:
    def test_create_and_get(self, db_session):
        repo = SqlCustomerRepository(db_session)
        c = Customer(name="新客戶", payment_terms="cash", phone="0912345678")
        saved = repo.save(c)
        db_session.flush()

        fetched = repo.get_by_id(saved.customer_id)
        assert fetched is not None
        assert fetched.name == "新客戶"
        assert fetched.phone == "0912345678"

    def test_update_with_version(self, db_session):
        repo = SqlCustomerRepository(db_session)
        c = Customer(name="舊名", payment_terms="cash")
        saved = repo.save(c)
        db_session.flush()

        saved.name = "新名"
        saved.version += 1
        updated = repo.save(saved)
        assert updated.name == "新名"
        assert updated.version == 2

    def test_list_active_only(self, db_session):
        repo = SqlCustomerRepository(db_session)
        repo.save(Customer(name="A", is_active=True))
        repo.save(Customer(name="B", is_active=False))
        db_session.flush()

        active = repo.list_all(offset=0, limit=100)
        names = [c.name for c in active]
        assert "A" in names
        assert "B" not in names


# ── GenerateStatementService ─────────────────────────────


class TestGenerateStatementIntegration:
    def test_generates_ar(self, db_session, customer_seed):
        svc = build_generate_statement_service(db_session)

        # 找出交易所在月份
        row = db_session.execute(text(
            "SELECT TO_CHAR(created_at, 'YYYY-MM') as period FROM sales WHERE sale_id = :sid"
        ), {"sid": customer_seed["sale_id"]}).mappings().first()
        period = row["period"]

        result = svc.generate(uuid.UUID(customer_seed["customer_id"]), period, uuid.uuid4())

        assert result.success
        assert result.data["total_amount"] == 3000.0

        ar = db_session.execute(text(
            "SELECT * FROM accounts_receivables WHERE customer_id = :cid AND period = :p"
        ), {"cid": customer_seed["customer_id"], "p": period}).mappings().first()
        assert ar is not None
        assert float(ar["total_amount"]) == 3000.0
        assert ar["status"] == "open"

    def test_duplicate_period_rejected(self, db_session, customer_seed):
        svc = build_generate_statement_service(db_session)
        row = db_session.execute(text(
            "SELECT TO_CHAR(created_at, 'YYYY-MM') as period FROM sales WHERE sale_id = :sid"
        ), {"sid": customer_seed["sale_id"]}).mappings().first()
        period = row["period"]

        svc.generate(uuid.UUID(customer_seed["customer_id"]), period, uuid.uuid4())
        result = svc.generate(uuid.UUID(customer_seed["customer_id"]), period, uuid.uuid4())

        assert not result.success
        assert "已存在" in result.message

    def test_non_monthly_rejected(self, db_session):
        db_session.execute(text("""
            INSERT INTO customers (customer_id, name, payment_terms, is_active)
            VALUES (:cid, '現金客', 'cash', true)
        """), {"cid": str(uuid.uuid4())})
        db_session.flush()

        cash_id = db_session.execute(text(
            "SELECT customer_id FROM customers WHERE name = '現金客'"
        )).scalar()

        svc = build_generate_statement_service(db_session)
        result = svc.generate(cash_id, "2026-03", uuid.uuid4())
        assert not result.success
        assert "非月結" in result.message

    def test_review_task_created(self, db_session, customer_seed):
        svc = build_generate_statement_service(db_session)
        row = db_session.execute(text(
            "SELECT TO_CHAR(created_at, 'YYYY-MM') as period FROM sales WHERE sale_id = :sid"
        ), {"sid": customer_seed["sale_id"]}).mappings().first()

        svc.generate(uuid.UUID(customer_seed["customer_id"]), row["period"], uuid.uuid4())

        task = db_session.execute(text(
            "SELECT * FROM review_tasks WHERE review_type = 'monthly_reconcile'"
        )).mappings().first()
        assert task is not None
        assert "月結客戶" in task["title"]


# ── PaymentService ───────────────────────────────────────


class TestPaymentIntegration:
    def _create_ar(self, db_session, customer_seed, period="2026-03"):
        svc = build_generate_statement_service(db_session)
        row = db_session.execute(text(
            "SELECT TO_CHAR(created_at, 'YYYY-MM') as period FROM sales WHERE sale_id = :sid"
        ), {"sid": customer_seed["sale_id"]}).mappings().first()
        svc.generate(uuid.UUID(customer_seed["customer_id"]), row["period"], uuid.uuid4())

        ar = db_session.execute(text(
            "SELECT ar_id FROM accounts_receivables WHERE customer_id = :cid"
        ), {"cid": customer_seed["customer_id"]}).mappings().first()
        return ar["ar_id"]

    def test_partial_payment(self, db_session, customer_seed):
        ar_id = self._create_ar(db_session, customer_seed)
        svc = build_payment_service(db_session)

        result = svc.record_payment(ar_id, 1000)

        assert result.success
        assert result.data["status"] == "partial_paid"

        ar = db_session.execute(text(
            "SELECT * FROM accounts_receivables WHERE ar_id = :aid"
        ), {"aid": str(ar_id)}).mappings().first()
        assert float(ar["paid_amount"]) == 1000
        assert ar["status"] == "partial_paid"

    def test_full_payment(self, db_session, customer_seed):
        ar_id = self._create_ar(db_session, customer_seed)
        svc = build_payment_service(db_session)

        svc.record_payment(ar_id, 3000)

        ar = db_session.execute(text(
            "SELECT * FROM accounts_receivables WHERE ar_id = :aid"
        ), {"aid": str(ar_id)}).mappings().first()
        assert float(ar["paid_amount"]) == 3000
        assert ar["status"] == "paid"
        assert ar["paid_at"] is not None

    def test_accumulative_payments(self, db_session, customer_seed):
        ar_id = self._create_ar(db_session, customer_seed)
        svc = build_payment_service(db_session)

        svc.record_payment(ar_id, 1000)
        svc.record_payment(ar_id, 2000)

        ar = db_session.execute(text(
            "SELECT * FROM accounts_receivables WHERE ar_id = :aid"
        ), {"aid": str(ar_id)}).mappings().first()
        assert float(ar["paid_amount"]) == 3000
        assert ar["status"] == "paid"
