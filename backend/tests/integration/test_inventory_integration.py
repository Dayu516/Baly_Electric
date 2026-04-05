"""Inventory module integration tests — real DB, rollback after each test."""

import uuid

import pytest
from sqlalchemy import text

from application.inventory import (
    build_receive_stock_service,
    build_stock_count_service,
    build_stock_recalc_service,
)
from application.inventory.receive_stock_service import ReceiveLineInput
from application.inventory.stock_count_service import CountLineInput


@pytest.fixture
def inv_seed(db_session):
    """建立測試用基礎資料：SKU + 庫存。"""
    sku_id = str(uuid.uuid4())
    sku_id_2 = str(uuid.uuid4())
    product_id = str(uuid.uuid4())
    category_id = str(uuid.uuid4())
    supplier_id = str(uuid.uuid4())

    db_session.execute(text(
        "INSERT INTO categories (category_id, name, sort_order) VALUES (:cid, '分類', 0)"
    ), {"cid": category_id})
    db_session.execute(text(
        "INSERT INTO products (product_id, name, category_id, is_active) VALUES (:pid, '品項', :cid, true)"
    ), {"pid": product_id, "cid": category_id})

    for sid, spec in [(sku_id, "2P"), (sku_id_2, "3P")]:
        db_session.execute(text("""
            INSERT INTO skus (sku_id, product_id, brand, spec, unit, sell_price, cost_price, min_stock, is_active)
            VALUES (:sid, :pid, '牌', :spec, '個', 100, 60, 5, true)
        """), {"sid": sid, "pid": product_id, "spec": spec})
        db_session.execute(text(
            "INSERT INTO inventory_balances (sku_id, current_stock) VALUES (:sid, 0)"
        ), {"sid": sid})

    db_session.execute(text(
        "INSERT INTO suppliers (supplier_id, name, is_active) VALUES (:sid, '供應商', true)"
    ), {"sid": supplier_id})
    db_session.flush()

    return {
        "sku_id": sku_id,
        "sku_id_2": sku_id_2,
        "supplier_id": supplier_id,
        "user_id": uuid.uuid4(),
    }


# ── ReceiveStockService ─────────────────────────────────


class TestReceiveIntegration:
    def test_receive_increases_balance(self, db_session, inv_seed):
        svc = build_receive_stock_service(db_session)
        result = svc.receive(
            [ReceiveLineInput(sku_id=uuid.UUID(inv_seed["sku_id"]), quantity=10)],
            supplier_id=uuid.UUID(inv_seed["supplier_id"]),
            received_by=inv_seed["user_id"],
        )

        assert result.success
        balance = db_session.execute(text(
            "SELECT current_stock FROM inventory_balances WHERE sku_id = :sid"
        ), {"sid": inv_seed["sku_id"]}).scalar()
        assert balance == 10

    def test_multiple_receives_accumulate(self, db_session, inv_seed):
        svc = build_receive_stock_service(db_session)
        svc.receive(
            [ReceiveLineInput(sku_id=uuid.UUID(inv_seed["sku_id"]), quantity=5)],
            supplier_id=uuid.UUID(inv_seed["supplier_id"]),
            received_by=inv_seed["user_id"],
        )
        svc.receive(
            [ReceiveLineInput(sku_id=uuid.UUID(inv_seed["sku_id"]), quantity=3)],
            supplier_id=uuid.UUID(inv_seed["supplier_id"]),
            received_by=inv_seed["user_id"],
        )

        balance = db_session.execute(text(
            "SELECT current_stock FROM inventory_balances WHERE sku_id = :sid"
        ), {"sid": inv_seed["sku_id"]}).scalar()
        assert balance == 8

    def test_movements_created(self, db_session, inv_seed):
        svc = build_receive_stock_service(db_session)
        svc.receive(
            [
                ReceiveLineInput(sku_id=uuid.UUID(inv_seed["sku_id"]), quantity=5),
                ReceiveLineInput(sku_id=uuid.UUID(inv_seed["sku_id_2"]), quantity=3),
            ],
            supplier_id=uuid.UUID(inv_seed["supplier_id"]),
            received_by=inv_seed["user_id"],
        )

        count = db_session.execute(text(
            "SELECT COUNT(*) FROM stock_movements WHERE movement_type = 'purchase_receive'"
        )).scalar()
        assert count == 2

    def test_ensure_exists_idempotent(self, db_session, inv_seed):
        """已有 balance 的 SKU，ensure_exists 不應出錯。"""
        svc = build_receive_stock_service(db_session)
        # 第一次入庫
        svc.receive(
            [ReceiveLineInput(sku_id=uuid.UUID(inv_seed["sku_id"]), quantity=1)],
            supplier_id=uuid.UUID(inv_seed["supplier_id"]),
            received_by=inv_seed["user_id"],
        )
        # 第二次入庫（ensure_exists 再次呼叫，不應爆炸）
        result = svc.receive(
            [ReceiveLineInput(sku_id=uuid.UUID(inv_seed["sku_id"]), quantity=2)],
            supplier_id=uuid.UUID(inv_seed["supplier_id"]),
            received_by=inv_seed["user_id"],
        )
        assert result.success


# ── StockCountService ────────────────────────────────────


class TestStockCountIntegration:
    def test_no_discrepancy(self, db_session, inv_seed):
        """帳實相符不產生 adjustment。"""
        svc = build_stock_count_service(db_session)
        result = svc.submit_count(
            [CountLineInput(sku_id=uuid.UUID(inv_seed["sku_id"]), actual_quantity=0)],
            inv_seed["user_id"],
        )

        assert result.success
        assert "帳實相符" in result.message
        adj_count = db_session.execute(text(
            "SELECT COUNT(*) FROM stock_movements WHERE movement_type = 'adjustment'"
        )).scalar()
        assert adj_count == 0

    def test_discrepancy_detected(self, db_session, inv_seed):
        """先入庫再盤點，差異應被偵測。"""
        receive_svc = build_receive_stock_service(db_session)
        receive_svc.receive(
            [ReceiveLineInput(sku_id=uuid.UUID(inv_seed["sku_id"]), quantity=10)],
            supplier_id=uuid.UUID(inv_seed["supplier_id"]),
            received_by=inv_seed["user_id"],
        )

        count_svc = build_stock_count_service(db_session)
        result = count_svc.submit_count(
            [CountLineInput(sku_id=uuid.UUID(inv_seed["sku_id"]), actual_quantity=8)],
            inv_seed["user_id"],
        )

        assert result.success
        assert len(result.data["discrepancies"]) == 1
        assert result.data["discrepancies"][0]["difference"] == -2

    def test_adjust_writes_movement_and_balance(self, db_session, inv_seed):
        """調整後 movement + balance 都正確。"""
        receive_svc = build_receive_stock_service(db_session)
        receive_svc.receive(
            [ReceiveLineInput(sku_id=uuid.UUID(inv_seed["sku_id"]), quantity=10)],
            supplier_id=uuid.UUID(inv_seed["supplier_id"]),
            received_by=inv_seed["user_id"],
        )

        count_svc = build_stock_count_service(db_session)
        count_svc.adjust(uuid.UUID(inv_seed["sku_id"]), actual_quantity=8, adjusted_by=inv_seed["user_id"])

        balance = db_session.execute(text(
            "SELECT current_stock FROM inventory_balances WHERE sku_id = :sid"
        ), {"sid": inv_seed["sku_id"]}).scalar()
        assert balance == 8

        adj = db_session.execute(text(
            "SELECT quantity FROM stock_movements WHERE sku_id = :sid AND movement_type = 'adjustment'"
        ), {"sid": inv_seed["sku_id"]}).scalar()
        assert adj == -2


# ── StockRecalcService ───────────────────────────────────


class TestRecalcIntegration:
    def test_recalc_corrects_inconsistency(self, db_session, inv_seed):
        """模擬不一致場景：手動改 balance → 重算修正。"""
        sku_id = inv_seed["sku_id"]

        # 入庫 10 個
        receive_svc = build_receive_stock_service(db_session)
        receive_svc.receive(
            [ReceiveLineInput(sku_id=uuid.UUID(sku_id), quantity=10)],
            supplier_id=uuid.UUID(inv_seed["supplier_id"]),
            received_by=inv_seed["user_id"],
        )

        # 手動把 balance 改壞（模擬不一致）
        db_session.execute(text(
            "UPDATE inventory_balances SET current_stock = 999 WHERE sku_id = :sid"
        ), {"sid": sku_id})

        # 重算
        recalc_svc = build_stock_recalc_service(db_session)
        result = recalc_svc.recalc(uuid.UUID(sku_id))

        assert result.success
        assert result.data["current_stock"] == 10

        balance = db_session.execute(text(
            "SELECT current_stock FROM inventory_balances WHERE sku_id = :sid"
        ), {"sid": sku_id}).scalar()
        assert balance == 10

    def test_recalc_idempotent(self, db_session, inv_seed):
        """重算兩次結果相同。"""
        sku_id = inv_seed["sku_id"]

        receive_svc = build_receive_stock_service(db_session)
        receive_svc.receive(
            [ReceiveLineInput(sku_id=uuid.UUID(sku_id), quantity=7)],
            supplier_id=uuid.UUID(inv_seed["supplier_id"]),
            received_by=inv_seed["user_id"],
        )

        recalc_svc = build_stock_recalc_service(db_session)
        result1 = recalc_svc.recalc(uuid.UUID(sku_id))
        result2 = recalc_svc.recalc(uuid.UUID(sku_id))

        assert result1.data["current_stock"] == result2.data["current_stock"] == 7

    def test_recalc_sets_last_recalc_at(self, db_session, inv_seed):
        sku_id = inv_seed["sku_id"]
        recalc_svc = build_stock_recalc_service(db_session)
        recalc_svc.recalc(uuid.UUID(sku_id))

        row = db_session.execute(text(
            "SELECT last_recalc_at FROM inventory_balances WHERE sku_id = :sid"
        ), {"sid": sku_id}).mappings().first()
        assert row["last_recalc_at"] is not None


# ── 完整流程 ─────────────────────────────────────────────


class TestFullFlow:
    def test_receive_count_recalc_flow(self, db_session, inv_seed):
        """入庫 → 盤點 → 調整 → 重算：完整流程一致性。"""
        sku_id = uuid.UUID(inv_seed["sku_id"])
        supplier_id = uuid.UUID(inv_seed["supplier_id"])
        user_id = inv_seed["user_id"]

        # 1. 入庫 20 個
        receive_svc = build_receive_stock_service(db_session)
        receive_svc.receive(
            [ReceiveLineInput(sku_id=sku_id, quantity=20)],
            supplier_id=supplier_id, received_by=user_id,
        )

        # 2. 盤點：實際只有 18 個
        count_svc = build_stock_count_service(db_session)
        result = count_svc.submit_count(
            [CountLineInput(sku_id=sku_id, actual_quantity=18)],
            user_id,
        )
        assert len(result.data["discrepancies"]) == 1

        # 3. 執行調整
        count_svc.adjust(sku_id, actual_quantity=18, adjusted_by=user_id)

        # 4. 此時 balance 應為 18
        balance = db_session.execute(text(
            "SELECT current_stock FROM inventory_balances WHERE sku_id = :sid"
        ), {"sid": str(sku_id)}).scalar()
        assert balance == 18

        # 5. 重算：movement sum = 20 + (-2) = 18，應該一致
        recalc_svc = build_stock_recalc_service(db_session)
        result = recalc_svc.recalc(sku_id)
        assert result.data["current_stock"] == 18

    def test_consecutive_atomic_updates_correct(self, db_session, inv_seed):
        """連續兩次 atomic_update 的結果正確。"""
        sku_id = uuid.UUID(inv_seed["sku_id"])
        supplier_id = uuid.UUID(inv_seed["supplier_id"])
        user_id = inv_seed["user_id"]

        svc = build_receive_stock_service(db_session)
        svc.receive([ReceiveLineInput(sku_id=sku_id, quantity=10)], supplier_id, user_id)
        svc.receive([ReceiveLineInput(sku_id=sku_id, quantity=5)], supplier_id, user_id)
        svc.receive([ReceiveLineInput(sku_id=sku_id, quantity=3)], supplier_id, user_id)

        balance = db_session.execute(text(
            "SELECT current_stock FROM inventory_balances WHERE sku_id = :sid"
        ), {"sid": str(sku_id)}).scalar()
        assert balance == 18

        movements = db_session.execute(text(
            "SELECT COUNT(*) FROM stock_movements WHERE sku_id = :sid"
        ), {"sid": str(sku_id)}).scalar()
        assert movements == 3
