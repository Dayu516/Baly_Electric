"""BackorderService integration tests — real DB, rollback after each test."""

import uuid

import pytest
from sqlalchemy import text

from application.sales import build_backorder_service, build_checkout_service
from application.sales.schemas import CartItem, CheckoutRequest


@pytest.fixture
def backorder_seed(db_session):
    """建立基礎資料 + 一筆已完成的交易（含 sale_line）。"""
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
        VALUES (:cid, '客戶', 'cash', true)
    """), {"cid": customer_id})
    db_session.flush()

    # 結帳：建立一筆 10 個的交易
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

    return {
        "sku_id": sku_id,
        "customer_id": customer_id,
        "cashier_id": cashier_id,
        "sale_id": sale_id,
        "sale_line_id": str(row["sale_line_id"]),
    }


class TestBackorderCreateIntegration:
    def test_creates_backorder(self, db_session, backorder_seed):
        svc = build_backorder_service(db_session)
        result = svc.create_backorder(
            uuid.UUID(backorder_seed["sale_line_id"]),
            delivered_qty=6,
        )

        assert result.success
        assert result.data["backorder_qty"] == 4

        # 驗證 DB
        sl = db_session.execute(text(
            "SELECT * FROM sale_lines WHERE sale_line_id = :id"
        ), {"id": backorder_seed["sale_line_id"]}).mappings().first()
        assert sl["delivered_qty"] == 6
        assert sl["backorder_qty"] == 4
        assert sl["fulfillment_status"] == "partially_backordered"

    def test_sale_has_backorder_updated(self, db_session, backorder_seed):
        svc = build_backorder_service(db_session)
        svc.create_backorder(uuid.UUID(backorder_seed["sale_line_id"]), delivered_qty=6)

        sale = db_session.execute(text(
            "SELECT has_backorder FROM sales WHERE sale_id = :sid"
        ), {"sid": backorder_seed["sale_id"]}).mappings().first()
        assert sale["has_backorder"] is True


class TestBackorderLinkPoIntegration:
    def test_link_po(self, db_session, backorder_seed):
        svc = build_backorder_service(db_session)
        svc.create_backorder(uuid.UUID(backorder_seed["sale_line_id"]), delivered_qty=6)

        po_id = uuid.uuid4()
        result = svc.link_to_po(uuid.UUID(backorder_seed["sale_line_id"]), po_id, None, 4)

        assert result.success

        # fulfillment 記錄
        f = db_session.execute(text(
            "SELECT * FROM sale_line_fulfillments WHERE sale_line_id = :id"
        ), {"id": backorder_seed["sale_line_id"]}).mappings().first()
        assert f is not None
        assert f["allocated_qty"] == 4
        assert str(f["source_doc_id"]) == str(po_id)


class TestBackorderDeliverIntegration:
    def test_full_flow_create_deliver(self, db_session, backorder_seed):
        """完整流程：建欠貨 → 補交 → 驗證庫存 + 狀態。"""
        svc = build_backorder_service(db_session)

        # 1. 建欠貨（10 個中交 6 個，欠 4 個）
        svc.create_backorder(uuid.UUID(backorder_seed["sale_line_id"]), delivered_qty=6)

        # 2. 補交 4 個
        result = svc.deliver_backorder(
            uuid.UUID(backorder_seed["sale_line_id"]),
            deliver_qty=4,
            user_id=backorder_seed["cashier_id"],
        )
        assert result.success

        # 3. 驗證庫存（20 初始 - 10 結帳 - 4 補交 = 6）
        balance = db_session.execute(text(
            "SELECT current_stock FROM inventory_balances WHERE sku_id = :sid"
        ), {"sid": backorder_seed["sku_id"]}).scalar()
        assert balance == 6

        # 4. 驗證狀態
        sl = db_session.execute(text(
            "SELECT * FROM sale_lines WHERE sale_line_id = :id"
        ), {"id": backorder_seed["sale_line_id"]}).mappings().first()
        assert sl["backorder_delivered_qty"] == 4
        assert sl["fulfillment_status"] == "completed"
        assert sl["pickup_completed_at"] is not None
        assert sl["closed_at"] is not None

    def test_partial_deliver(self, db_session, backorder_seed):
        svc = build_backorder_service(db_session)
        svc.create_backorder(uuid.UUID(backorder_seed["sale_line_id"]), delivered_qty=6)

        svc.deliver_backorder(uuid.UUID(backorder_seed["sale_line_id"]), 2, backorder_seed["cashier_id"])

        sl = db_session.execute(text(
            "SELECT * FROM sale_lines WHERE sale_line_id = :id"
        ), {"id": backorder_seed["sale_line_id"]}).mappings().first()
        assert sl["backorder_delivered_qty"] == 2
        assert sl["fulfillment_status"] != "completed"

    def test_stock_movement_created(self, db_session, backorder_seed):
        svc = build_backorder_service(db_session)
        svc.create_backorder(uuid.UUID(backorder_seed["sale_line_id"]), delivered_qty=6)
        svc.deliver_backorder(uuid.UUID(backorder_seed["sale_line_id"]), 3, backorder_seed["cashier_id"])

        movements = db_session.execute(text(
            "SELECT * FROM stock_movements WHERE movement_type = 'backorder_delivery' AND reference_id = :sid"
        ), {"sid": backorder_seed["sale_id"]}).mappings().all()
        assert len(movements) == 1
        assert movements[0]["quantity"] == -3


class TestBackorderNotifyIntegration:
    def test_creates_notification(self, db_session, backorder_seed):
        svc = build_backorder_service(db_session)
        svc.create_backorder(uuid.UUID(backorder_seed["sale_line_id"]), delivered_qty=6)

        result = svc.notify_customer(
            uuid.UUID(backorder_seed["sale_id"]),
            uuid.UUID(backorder_seed["sale_line_id"]),
            channel="phone",
            message="貨到了請來取",
        )
        assert result.success

        notif = db_session.execute(text(
            "SELECT * FROM customer_pickup_notifications WHERE sale_id = :sid"
        ), {"sid": backorder_seed["sale_id"]}).mappings().first()
        assert notif is not None
        assert notif["channel"] == "phone"

        sl = db_session.execute(text(
            "SELECT notify_count FROM sale_lines WHERE sale_line_id = :id"
        ), {"id": backorder_seed["sale_line_id"]}).mappings().first()
        assert sl["notify_count"] == 1


class TestBackorderCancelIntegration:
    def test_cancel(self, db_session, backorder_seed):
        svc = build_backorder_service(db_session)
        svc.create_backorder(uuid.UUID(backorder_seed["sale_line_id"]), delivered_qty=6)

        result = svc.cancel_backorder(uuid.UUID(backorder_seed["sale_line_id"]))
        assert result.success

        sl = db_session.execute(text(
            "SELECT * FROM sale_lines WHERE sale_line_id = :id"
        ), {"id": backorder_seed["sale_line_id"]}).mappings().first()
        assert sl["backorder_qty"] == 0
        assert sl["backorder_status"] == "cancelled"
        assert sl["closed_at"] is not None

        sale = db_session.execute(text(
            "SELECT has_backorder FROM sales WHERE sale_id = :sid"
        ), {"sid": backorder_seed["sale_id"]}).mappings().first()
        assert sale["has_backorder"] is False
