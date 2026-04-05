"""CheckoutService integration tests — real DB, rollback after each test."""

import uuid

import pytest
from sqlalchemy import text

from application.sales import build_checkout_service
from application.sales.schemas import CartItem, CheckoutRequest


@pytest.fixture
def sales_seed(db_session):
    """建立測試用基礎資料：SKU + 庫存 + 客戶。"""
    sku_id = str(uuid.uuid4())
    sku_id_2 = str(uuid.uuid4())
    product_id = str(uuid.uuid4())
    category_id = str(uuid.uuid4())
    customer_id = str(uuid.uuid4())
    cashier_id = uuid.uuid4()

    db_session.execute(text(
        "INSERT INTO categories (category_id, name, sort_order) VALUES (:cid, '測試分類', 0)"
    ), {"cid": category_id})

    db_session.execute(text(
        "INSERT INTO products (product_id, name, category_id, is_active) VALUES (:pid, '測試品項', :cid, true)"
    ), {"pid": product_id, "cid": category_id})

    for sid, spec, price in [(sku_id, "2P 20A", 100), (sku_id_2, "3P 30A", 200)]:
        db_session.execute(text("""
            INSERT INTO skus (sku_id, product_id, brand, spec, unit, sell_price, cost_price, min_stock, is_active)
            VALUES (:sid, :pid, '牌', :spec, '個', :price, 60, 5, true)
        """), {"sid": sid, "pid": product_id, "spec": spec, "price": price})

        db_session.execute(text(
            "INSERT INTO inventory_balances (sku_id, current_stock) VALUES (:sid, 20)"
        ), {"sid": sid})

    db_session.execute(text("""
        INSERT INTO customers (customer_id, name, payment_terms, is_active)
        VALUES (:cid, '測試客戶', 'monthly_credit', true)
    """), {"cid": customer_id})

    db_session.flush()

    return {
        "sku_id": sku_id,
        "sku_id_2": sku_id_2,
        "customer_id": customer_id,
        "cashier_id": cashier_id,
    }


class TestCheckoutIntegration:
    def test_creates_sale_and_lines(self, db_session, sales_seed):
        svc = build_checkout_service(db_session)
        req = CheckoutRequest(
            items=[CartItem(
                sku_id=uuid.UUID(sales_seed["sku_id"]),
                quantity=3, unit_price=100, product_name="A", spec="2P 20A",
            )],
        )
        result = svc.checkout(req, sales_seed["cashier_id"])

        assert result.success
        sale_id = result.data["sale_id"]

        # 驗證 sale 寫入
        row = db_session.execute(text("SELECT * FROM sales WHERE sale_id = :sid"), {"sid": sale_id}).mappings().first()
        assert row is not None
        assert row["status"] == "completed"
        assert float(row["total"]) == 300

        # 驗證 sale_lines 寫入
        lines = db_session.execute(text("SELECT * FROM sale_lines WHERE sale_id = :sid"), {"sid": sale_id}).mappings().all()
        assert len(lines) == 1
        assert lines[0]["quantity"] == 3

    def test_stock_deducted(self, db_session, sales_seed):
        svc = build_checkout_service(db_session)
        req = CheckoutRequest(
            items=[CartItem(
                sku_id=uuid.UUID(sales_seed["sku_id"]),
                quantity=5, unit_price=100, product_name="A", spec="2P",
            )],
        )
        svc.checkout(req, sales_seed["cashier_id"])

        balance = db_session.execute(text(
            "SELECT current_stock FROM inventory_balances WHERE sku_id = :sid"
        ), {"sid": sales_seed["sku_id"]}).scalar()
        assert balance == 15  # 20 - 5

    def test_stock_movements_created(self, db_session, sales_seed):
        svc = build_checkout_service(db_session)
        req = CheckoutRequest(
            items=[
                CartItem(sku_id=uuid.UUID(sales_seed["sku_id"]), quantity=2, unit_price=100, product_name="A", spec="2P"),
                CartItem(sku_id=uuid.UUID(sales_seed["sku_id_2"]), quantity=1, unit_price=200, product_name="B", spec="3P"),
            ],
        )
        result = svc.checkout(req, sales_seed["cashier_id"])
        sale_id = result.data["sale_id"]

        movements = db_session.execute(text(
            "SELECT * FROM stock_movements WHERE reference_id = :sid"
        ), {"sid": sale_id}).mappings().all()
        assert len(movements) == 2
        qtys = sorted([m["quantity"] for m in movements])
        assert qtys == [-2, -1]

    def test_idempotent_checkout(self, db_session, sales_seed):
        svc = build_checkout_service(db_session)
        req = CheckoutRequest(
            client_tx_id="unique-tx-001",
            items=[CartItem(
                sku_id=uuid.UUID(sales_seed["sku_id"]),
                quantity=1, unit_price=100, product_name="A", spec="2P",
            )],
        )

        result1 = svc.checkout(req, sales_seed["cashier_id"])
        assert result1.success

        result2 = svc.checkout(req, sales_seed["cashier_id"])
        assert result2.success
        assert result2.data["status"] == "already_exists"
        assert result2.data["sale_id"] == result1.data["sale_id"]

    def test_monthly_credit_ar(self, db_session, sales_seed):
        svc = build_checkout_service(db_session)
        req = CheckoutRequest(
            customer_id=uuid.UUID(sales_seed["customer_id"]),
            payment_method="monthly_credit",
            items=[CartItem(
                sku_id=uuid.UUID(sales_seed["sku_id"]),
                quantity=2, unit_price=100, product_name="A", spec="2P",
            )],
        )
        svc.checkout(req, sales_seed["cashier_id"])

        ar = db_session.execute(text(
            "SELECT * FROM accounts_receivables WHERE customer_id = :cid"
        ), {"cid": sales_seed["customer_id"]}).mappings().first()
        assert ar is not None
        assert float(ar["total_amount"]) == 200

    def test_tax_included(self, db_session, sales_seed):
        svc = build_checkout_service(db_session)
        req = CheckoutRequest(
            tax_mode="included",
            items=[CartItem(
                sku_id=uuid.UUID(sales_seed["sku_id"]),
                quantity=1, unit_price=1050, product_name="A", spec="2P",
            )],
        )
        result = svc.checkout(req, sales_seed["cashier_id"])
        sale_id = result.data["sale_id"]

        row = db_session.execute(text("SELECT * FROM sales WHERE sale_id = :sid"), {"sid": sale_id}).mappings().first()
        assert float(row["total"]) == 1050
        assert float(row["tax_amount"]) == 50
        assert float(row["subtotal"]) == 1000

    def test_customer_price_history(self, db_session, sales_seed):
        svc = build_checkout_service(db_session)
        req = CheckoutRequest(
            customer_id=uuid.UUID(sales_seed["customer_id"]),
            items=[CartItem(
                sku_id=uuid.UUID(sales_seed["sku_id"]),
                quantity=1, unit_price=150, product_name="A", spec="2P",
            )],
        )
        svc.checkout(req, sales_seed["cashier_id"])

        row = db_session.execute(text(
            "SELECT * FROM customer_price_history WHERE customer_id = :cid AND sku_id = :sid"
        ), {"cid": sales_seed["customer_id"], "sid": sales_seed["sku_id"]}).mappings().first()
        assert row is not None
        assert float(row["last_price"]) == 150
