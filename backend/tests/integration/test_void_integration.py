"""VoidSaleService integration tests — real DB, rollback after each test."""

import uuid

import pytest
from sqlalchemy import text

from application.sales import build_checkout_service, build_void_sale_service
from application.sales.schemas import CartItem, CheckoutRequest


@pytest.fixture
def void_seed(db_session):
    """建立基礎資料 + 一筆已完成的交易。"""
    sku_id = str(uuid.uuid4())
    product_id = str(uuid.uuid4())
    category_id = str(uuid.uuid4())
    customer_id = str(uuid.uuid4())
    cashier_id = uuid.uuid4()

    db_session.execute(text(
        "INSERT INTO categories (category_id, name, sort_order) VALUES (:cid, '分類', 0)"
    ), {"cid": category_id})
    db_session.execute(text(
        "INSERT INTO products (product_id, name, category_id, is_active) VALUES (:pid, '品項', :cid, true)"
    ), {"pid": product_id, "cid": category_id})
    db_session.execute(text("""
        INSERT INTO skus (sku_id, product_id, brand, spec, unit, sell_price, cost_price, min_stock, is_active)
        VALUES (:sid, :pid, '牌', '2P', '個', 100, 60, 5, true)
    """), {"sid": sku_id, "pid": product_id})
    db_session.execute(text(
        "INSERT INTO inventory_balances (sku_id, current_stock) VALUES (:sid, 20)"
    ), {"sid": sku_id})
    db_session.execute(text("""
        INSERT INTO customers (customer_id, name, payment_terms, is_active)
        VALUES (:cid, '客戶', 'monthly_credit', true)
    """), {"cid": customer_id})
    db_session.flush()

    # 先結帳
    checkout_svc = build_checkout_service(db_session)
    req = CheckoutRequest(
        items=[CartItem(sku_id=uuid.UUID(sku_id), quantity=5, unit_price=100, product_name="A", spec="2P")],
    )
    result = checkout_svc.checkout(req, cashier_id)
    sale_id = result.data["sale_id"]

    return {
        "sku_id": sku_id,
        "customer_id": customer_id,
        "cashier_id": cashier_id,
        "sale_id": sale_id,
    }


class TestVoidIntegration:
    def test_void_restores_inventory(self, db_session, void_seed):
        svc = build_void_sale_service(db_session)
        result = svc.void(uuid.UUID(void_seed["sale_id"]), void_seed["cashier_id"], "退貨")

        assert result.success

        balance = db_session.execute(text(
            "SELECT current_stock FROM inventory_balances WHERE sku_id = :sid"
        ), {"sid": void_seed["sku_id"]}).scalar()
        assert balance == 20  # 20 - 5 + 5 = 20

    def test_void_sets_status(self, db_session, void_seed):
        svc = build_void_sale_service(db_session)
        svc.void(uuid.UUID(void_seed["sale_id"]), void_seed["cashier_id"])

        row = db_session.execute(text(
            "SELECT status FROM sales WHERE sale_id = :sid"
        ), {"sid": void_seed["sale_id"]}).mappings().first()
        assert row["status"] == "voided"

    def test_void_creates_return_movements(self, db_session, void_seed):
        svc = build_void_sale_service(db_session)
        svc.void(uuid.UUID(void_seed["sale_id"]), void_seed["cashier_id"])

        movements = db_session.execute(text(
            "SELECT * FROM stock_movements WHERE reference_id = :sid AND movement_type = 'return'"
        ), {"sid": void_seed["sale_id"]}).mappings().all()
        assert len(movements) == 1
        assert movements[0]["quantity"] == 5

    def test_void_twice_rejected(self, db_session, void_seed):
        svc = build_void_sale_service(db_session)
        svc.void(uuid.UUID(void_seed["sale_id"]), void_seed["cashier_id"])

        result = svc.void(uuid.UUID(void_seed["sale_id"]), void_seed["cashier_id"])
        assert not result.success
        assert result.code == "ERR-BIZ-001"

    def test_void_monthly_credit_deducts_ar(self, db_session, void_seed):
        # 先用月結結帳
        checkout_svc = build_checkout_service(db_session)
        req = CheckoutRequest(
            customer_id=uuid.UUID(void_seed["customer_id"]),
            payment_method="monthly_credit",
            items=[CartItem(sku_id=uuid.UUID(void_seed["sku_id"]), quantity=2, unit_price=100, product_name="A", spec="2P")],
        )
        result = checkout_svc.checkout(req, void_seed["cashier_id"])
        sale_id = result.data["sale_id"]

        ar_before = db_session.execute(text(
            "SELECT total_amount FROM accounts_receivables WHERE customer_id = :cid"
        ), {"cid": void_seed["customer_id"]}).scalar()

        # 作廢
        void_svc = build_void_sale_service(db_session)
        void_svc.void(uuid.UUID(sale_id), void_seed["cashier_id"])

        ar_after = db_session.execute(text(
            "SELECT total_amount FROM accounts_receivables WHERE customer_id = :cid"
        ), {"cid": void_seed["customer_id"]}).scalar()

        assert float(ar_after) == float(ar_before) - 200
