"""Use Case 層 end-to-end integration tests — 驗證跨模組流程語意。

測試 4 條核心流程透過 use case 層的完整行為：
  1. Checkout → inventory → low stock alert
  2. PO Receive → inventory → low stock resolve
  3. Statement → payment → review auto close
  4. Import → review task → deactivate batch

每個 test 用真 DB，rollback after each test。
"""

import uuid

import pytest
from sqlalchemy import text

from application.use_cases import (
    build_checkout_use_case,
    build_deactivate_import_batch_use_case,
    build_generate_statement_use_case,
    build_import_catalog_use_case,
    build_receive_po_use_case,
    build_record_payment_use_case,
    build_void_sale_use_case,
)
from application.sales.schemas import CartItem, CheckoutRequest


@pytest.fixture
def flow_seed(db_session):
    """建立 4 條流程共用的基礎資料。"""
    category_id = str(uuid.uuid4())
    product_id = str(uuid.uuid4())
    sku_id = str(uuid.uuid4())
    supplier_id = str(uuid.uuid4())
    customer_id = str(uuid.uuid4())
    po_id = str(uuid.uuid4())
    po_line_id = str(uuid.uuid4())
    cashier_id = uuid.uuid4()

    db_session.execute(text(
        "INSERT INTO categories (category_id, name, sort_order) VALUES (:cid, '分類', 0)"
    ), {"cid": category_id})
    db_session.execute(text(
        "INSERT INTO products (product_id, name, category_id, is_active) VALUES (:pid, '品項', :cid, true)"
    ), {"pid": product_id, "cid": category_id})
    db_session.execute(text("""
        INSERT INTO skus (sku_id, product_id, brand, spec, unit, sell_price, cost_price, min_stock, is_active)
        VALUES (:sid, :pid, '士林', '2P 20A', '個', 100, 60, 5, true)
    """), {"sid": sku_id, "pid": product_id})
    db_session.execute(text(
        "INSERT INTO inventory_balances (sku_id, current_stock) VALUES (:sid, 10)"
    ), {"sid": sku_id})
    db_session.execute(text(
        "INSERT INTO suppliers (supplier_id, name, is_active) VALUES (:sid, '供應商', true)"
    ), {"sid": supplier_id})
    db_session.execute(text("""
        INSERT INTO supplier_products (sp_id, supplier_id, sku_id, unit_cost, is_preferred)
        VALUES (:spid, :sup, :sku, 60, true)
    """), {"spid": str(uuid.uuid4()), "sup": supplier_id, "sku": sku_id})
    db_session.execute(text("""
        INSERT INTO customers (customer_id, name, payment_terms, is_active)
        VALUES (:cid, '月結客戶', 'monthly_credit', true)
    """), {"cid": customer_id})

    # PO + PO line（for receive test）
    db_session.execute(text("""
        INSERT INTO purchase_orders (po_id, supplier_id, status, note)
        VALUES (:pid, :sid, 'ordered', null)
    """), {"pid": po_id, "sid": supplier_id})
    db_session.execute(text("""
        INSERT INTO purchase_order_lines (po_line_id, po_id, sku_id, ordered_quantity, received_quantity, unit_cost)
        VALUES (:plid, :pid, :sid, 10, 0, 60)
    """), {"plid": po_line_id, "pid": po_id, "sid": sku_id})

    db_session.flush()

    return {
        "sku_id": sku_id,
        "product_id": product_id,
        "supplier_id": supplier_id,
        "customer_id": customer_id,
        "cashier_id": cashier_id,
        "po_id": po_id,
        "po_line_id": po_line_id,
    }


# ── Flow 1: Checkout → Inventory → Low Stock Alert ───────


class TestCheckoutFlow:
    def test_checkout_creates_audit(self, db_session, flow_seed):
        uc = build_checkout_use_case(db_session)
        req = CheckoutRequest(
            items=[CartItem(sku_id=uuid.UUID(flow_seed["sku_id"]), quantity=2, unit_price=100, product_name="A", spec="2P")],
        )
        result = uc.execute(req, flow_seed["cashier_id"])
        assert result.success

        audit = db_session.execute(text(
            "SELECT * FROM audit_events WHERE action = 'checkout'"
        )).mappings().first()
        assert audit is not None

    def test_checkout_low_stock_alert_created(self, db_session, flow_seed):
        """結帳後庫存低於 min_stock → 建 alert。"""
        # 先把庫存壓低
        db_session.execute(text(
            "UPDATE inventory_balances SET current_stock = 3 WHERE sku_id = :sid"
        ), {"sid": flow_seed["sku_id"]})
        db_session.flush()

        uc = build_checkout_use_case(db_session)
        req = CheckoutRequest(
            items=[CartItem(sku_id=uuid.UUID(flow_seed["sku_id"]), quantity=1, unit_price=100, product_name="A", spec="2P")],
        )
        uc.execute(req, flow_seed["cashier_id"])

        alert = db_session.execute(text(
            "SELECT * FROM operational_alerts WHERE alert_type = 'low_stock' AND reference_id = :sid"
        ), {"sid": flow_seed["sku_id"]}).mappings().first()
        assert alert is not None

    def test_void_creates_audit(self, db_session, flow_seed):
        checkout_uc = build_checkout_use_case(db_session)
        req = CheckoutRequest(
            items=[CartItem(sku_id=uuid.UUID(flow_seed["sku_id"]), quantity=1, unit_price=100, product_name="A", spec="2P")],
        )
        result = checkout_uc.execute(req, flow_seed["cashier_id"])
        sale_id = result.data["sale_id"]

        void_uc = build_void_sale_use_case(db_session)
        void_uc.execute(uuid.UUID(sale_id), flow_seed["cashier_id"], reason="退貨")

        audit = db_session.execute(text(
            "SELECT * FROM audit_events WHERE action = 'void_sale'"
        )).mappings().first()
        assert audit is not None


# ── Flow 2: PO Receive → Inventory → Low Stock Resolve ──


class TestReceiveFlow:
    def test_receive_creates_audit(self, db_session, flow_seed):
        uc = build_receive_po_use_case(db_session)
        result = uc.execute(
            uuid.UUID(flow_seed["po_id"]),
            [{"po_line_id": flow_seed["po_line_id"], "received_quantity": 5}],
            None, flow_seed["cashier_id"],
        )
        assert result.success

        audit = db_session.execute(text(
            "SELECT * FROM audit_events WHERE action = 'receive_po'"
        )).mappings().first()
        assert audit is not None

    def test_receive_resolves_low_stock_alert(self, db_session, flow_seed):
        """先建 low stock alert → 進貨恢復庫存 → alert 被 resolve。"""
        sku_id = flow_seed["sku_id"]

        # 壓低庫存 + 建 alert
        db_session.execute(text(
            "UPDATE inventory_balances SET current_stock = 2 WHERE sku_id = :sid"
        ), {"sid": sku_id})
        db_session.execute(text("""
            INSERT INTO operational_alerts (alert_id, alert_type, severity, title, reference_type, reference_id, is_read)
            VALUES (:aid, 'low_stock', 'warning', '低庫存', 'sku', :sid, false)
        """), {"aid": str(uuid.uuid4()), "sid": sku_id})
        db_session.flush()

        # 進貨 10 個 → current_stock = 12 > min_stock(5)
        uc = build_receive_po_use_case(db_session)
        uc.execute(
            uuid.UUID(flow_seed["po_id"]),
            [{"po_line_id": flow_seed["po_line_id"], "received_quantity": 10}],
            None, flow_seed["cashier_id"],
        )

        # alert 應被 resolve（is_read = true）
        alert = db_session.execute(text(
            "SELECT is_read FROM operational_alerts WHERE alert_type = 'low_stock' AND reference_id = :sid"
        ), {"sid": sku_id}).mappings().first()
        assert alert["is_read"] is True


# ── Flow 3: Statement → Payment → Review Auto Close ─────


class TestStatementPaymentFlow:
    def test_full_flow(self, db_session, flow_seed):
        """生成月結 → 收款付清 → ReviewTask 自動結案。"""
        customer_id = flow_seed["customer_id"]

        # 先建一筆已完成交易（月結彙總需要）
        sale_id = str(uuid.uuid4())
        db_session.execute(text("""
            INSERT INTO sales (sale_id, customer_id, cashier_id, status, payment_method, total, subtotal, tax_amount, discount_amount)
            VALUES (:sid, :cid, :uid, 'completed', 'monthly_credit', 3000, 3000, 0, 0)
        """), {"sid": sale_id, "cid": customer_id, "uid": str(flow_seed["cashier_id"])})
        db_session.flush()

        # 取得交易月份
        row = db_session.execute(text(
            "SELECT TO_CHAR(created_at, 'YYYY-MM') as period FROM sales WHERE sale_id = :sid"
        ), {"sid": sale_id}).mappings().first()
        period = row["period"]

        # 1. 生成月結
        gen_uc = build_generate_statement_use_case(db_session)
        gen_result = gen_uc.execute(uuid.UUID(customer_id), period, flow_seed["cashier_id"])
        assert gen_result.success

        # 驗證 ReviewTask 建立
        task = db_session.execute(text(
            "SELECT * FROM review_tasks WHERE review_type = 'monthly_reconcile'"
        )).mappings().first()
        assert task is not None
        assert task["status"] == "pending"

        # 2. 全額收款
        ar = db_session.execute(text(
            "SELECT ar_id FROM accounts_receivables WHERE customer_id = :cid"
        ), {"cid": customer_id}).mappings().first()

        pay_uc = build_record_payment_use_case(db_session)
        pay_result = pay_uc.execute(ar["ar_id"], 3000, flow_seed["cashier_id"])
        assert pay_result.success

        # 3. 驗證 AR 結清
        ar_updated = db_session.execute(text(
            "SELECT status, paid_at FROM accounts_receivables WHERE ar_id = :aid"
        ), {"aid": str(ar["ar_id"])}).mappings().first()
        assert ar_updated["status"] == "paid"
        assert ar_updated["paid_at"] is not None

        # 4. 驗證 ReviewTask 自動結案
        task_updated = db_session.execute(text(
            "SELECT status FROM review_tasks WHERE review_type = 'monthly_reconcile'"
        )).mappings().first()
        assert task_updated["status"] == "completed"


# ── Flow 4: Import → Review Task → Deactivate Batch ─────


class TestImportFlow:
    def test_import_creates_review_with_batch_id(self, db_session, flow_seed):
        uc = build_import_catalog_use_case(db_session)

        csv = """品名,規格,廠牌,售價,單位
匯入測試品,4P 40A,東元,200,個
"""
        result = uc.execute(csv, flow_seed["cashier_id"])
        assert result.success

        batch_id = result.data["import_batch_id"]
        assert batch_id is not None

        # ReviewTask 有 batch reference
        task = db_session.execute(text(
            "SELECT * FROM review_tasks WHERE review_type = 'product_confirm'"
        )).mappings().first()
        assert task is not None
        assert str(task["reference_id"]) == batch_id

        # Product 有 source_batch_id
        product = db_session.execute(text(
            "SELECT source_batch_id FROM products WHERE name = '匯入測試品'"
        )).mappings().first()
        assert product is not None
        assert str(product["source_batch_id"]) == batch_id

    def test_deactivate_batch(self, db_session, flow_seed):
        """匯入 → 停用整批。"""
        import_uc = build_import_catalog_use_case(db_session)
        csv = """品名,規格,廠牌,售價,單位
停用測試品A,2P,士林,100,個
停用測試品B,3P,東元,200,個
"""
        result = import_uc.execute(csv, flow_seed["cashier_id"])
        batch_id = result.data["import_batch_id"]

        # 停用
        deact_uc = build_deactivate_import_batch_use_case(db_session)
        deact_result = deact_uc.execute(uuid.UUID(batch_id), flow_seed["cashier_id"])
        assert deact_result.success

        # 驗證 Product/SKU 被停用
        active_products = db_session.execute(text(
            "SELECT COUNT(*) FROM products WHERE source_batch_id = :bid AND is_active = true"
        ), {"bid": batch_id}).scalar()
        assert active_products == 0

        active_skus = db_session.execute(text(
            "SELECT COUNT(*) FROM skus WHERE source_batch_id = :bid AND is_active = true"
        ), {"bid": batch_id}).scalar()
        assert active_skus == 0

    def test_import_audit_created(self, db_session, flow_seed):
        uc = build_import_catalog_use_case(db_session)
        csv = """品名,規格,廠牌,售價
審計測試品,2P,士林,100
"""
        uc.execute(csv, flow_seed["cashier_id"])

        audit = db_session.execute(text(
            "SELECT * FROM audit_events WHERE action = 'import_catalog'"
        )).mappings().first()
        assert audit is not None
