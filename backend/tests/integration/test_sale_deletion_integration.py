"""Sale deletion integration tests — real DB, rollback after each test.

驗證 SaleRepository.delete_with_children 的 DB 狀態一致性。
"""

import uuid

import pytest
from sqlalchemy import text

from application.sales import build_backorder_service, build_checkout_service, build_void_sale_service
from application.sales.schemas import CartItem, CheckoutRequest
from infrastructure.persistence.repositories.sales_repo_impl import SqlSaleRepository


@pytest.fixture
def deletion_seed(db_session):
    """建立一筆完整交易（含 sale_lines, movements, fulfillments, notifications）然後作廢。"""
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
        "INSERT INTO inventory_balances (sku_id, current_stock) VALUES (:sid, 50)"
    ), {"sid": sku_id})
    db_session.execute(text("""
        INSERT INTO customers (customer_id, name, payment_terms, is_active)
        VALUES (:cid, '客戶', 'cash', true)
    """), {"cid": customer_id})
    db_session.flush()

    # 結帳
    checkout_svc = build_checkout_service(db_session)
    req = CheckoutRequest(
        customer_id=uuid.UUID(customer_id),
        items=[CartItem(sku_id=uuid.UUID(sku_id), quantity=10, unit_price=100, product_name="品", spec="2P")],
    )
    result = checkout_svc.checkout(req, cashier_id)
    sale_id = result.data["sale_id"]

    # 取得 sale_line_id
    row = db_session.execute(text(
        "SELECT sale_line_id FROM sale_lines WHERE sale_id = :sid"
    ), {"sid": sale_id}).mappings().first()
    sale_line_id = str(row["sale_line_id"])

    # 建欠貨 + 通知（製造子表資料）
    bo_svc = build_backorder_service(db_session)
    bo_svc.create_backorder(uuid.UUID(sale_line_id), delivered_qty=6)
    bo_svc.notify_customer(uuid.UUID(sale_id), uuid.UUID(sale_line_id), "phone", "來取貨")

    # 綁 PO（製造 fulfillment 資料）
    bo_svc.link_to_po(uuid.UUID(sale_line_id), uuid.uuid4(), None, 4)

    # 作廢
    void_svc = build_void_sale_service(db_session)
    void_svc.void(uuid.UUID(sale_id), cashier_id)

    return {
        "sale_id": sale_id,
        "sale_line_id": sale_line_id,
        "sku_id": sku_id,
    }


class TestDeleteWithChildren:
    def test_deletes_all_children(self, db_session, deletion_seed):
        """刪除後，所有子表資料都應該清空。"""
        sale_id = deletion_seed["sale_id"]
        repo = SqlSaleRepository(db_session)

        # 先確認子表資料存在
        assert db_session.execute(text(
            "SELECT COUNT(*) FROM sale_lines WHERE sale_id = :sid"
        ), {"sid": sale_id}).scalar() > 0
        assert db_session.execute(text(
            "SELECT COUNT(*) FROM sale_line_fulfillments WHERE sale_id = :sid"
        ), {"sid": sale_id}).scalar() > 0
        assert db_session.execute(text(
            "SELECT COUNT(*) FROM customer_pickup_notifications WHERE sale_id = :sid"
        ), {"sid": sale_id}).scalar() > 0

        # 執行刪除
        repo.delete_with_children(uuid.UUID(sale_id))

        # 驗證全部清空
        assert db_session.execute(text(
            "SELECT COUNT(*) FROM sales WHERE sale_id = :sid"
        ), {"sid": sale_id}).scalar() == 0
        assert db_session.execute(text(
            "SELECT COUNT(*) FROM sale_lines WHERE sale_id = :sid"
        ), {"sid": sale_id}).scalar() == 0
        assert db_session.execute(text(
            "SELECT COUNT(*) FROM sale_line_fulfillments WHERE sale_id = :sid"
        ), {"sid": sale_id}).scalar() == 0
        assert db_session.execute(text(
            "SELECT COUNT(*) FROM customer_pickup_notifications WHERE sale_id = :sid"
        ), {"sid": sale_id}).scalar() == 0

    def test_does_not_affect_other_sales(self, db_session, deletion_seed):
        """刪除一筆交易不應影響其他交易。"""
        sale_id = deletion_seed["sale_id"]

        # 再建一筆交易
        sku_id = deletion_seed["sku_id"]
        cashier_id = uuid.uuid4()
        checkout_svc = build_checkout_service(db_session)
        req = CheckoutRequest(
            items=[CartItem(sku_id=uuid.UUID(sku_id), quantity=1, unit_price=100, product_name="品", spec="2P")],
        )
        other_result = checkout_svc.checkout(req, cashier_id)
        other_sale_id = other_result.data["sale_id"]

        # 刪除第一筆
        repo = SqlSaleRepository(db_session)
        repo.delete_with_children(uuid.UUID(sale_id))

        # 第二筆應仍存在
        assert db_session.execute(text(
            "SELECT COUNT(*) FROM sales WHERE sale_id = :sid"
        ), {"sid": other_sale_id}).scalar() == 1
        assert db_session.execute(text(
            "SELECT COUNT(*) FROM sale_lines WHERE sale_id = :sid"
        ), {"sid": other_sale_id}).scalar() == 1

    def test_stock_movements_not_deleted(self, db_session, deletion_seed):
        """刪除交易不應刪除 stock_movements（它們是 append-only 真相）。"""
        sale_id = deletion_seed["sale_id"]

        movements_before = db_session.execute(text(
            "SELECT COUNT(*) FROM stock_movements WHERE reference_id = :sid"
        ), {"sid": sale_id}).scalar()
        assert movements_before > 0

        repo = SqlSaleRepository(db_session)
        repo.delete_with_children(uuid.UUID(sale_id))

        movements_after = db_session.execute(text(
            "SELECT COUNT(*) FROM stock_movements WHERE reference_id = :sid"
        ), {"sid": sale_id}).scalar()
        assert movements_after == movements_before  # 不刪 movements
