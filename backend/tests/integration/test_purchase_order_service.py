"""PurchaseOrderService integration tests — real DB, rollback."""

import uuid

import pytest
from sqlalchemy import text

from infrastructure.persistence.query_services.procurement_query_service import ProcurementQueryService


FAKE_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


class TestCreateOrder:
    def test_create_draft(self, po_service, seed_data):
        result = po_service.create_order(
            supplier_id=seed_data["supplier_id"],
            note="測試建單",
            lines=[{"sku_id": seed_data["sku_id"], "ordered_quantity": 10, "unit_cost": 60}],
        )
        assert result.success
        assert result.data["po_id"]

    def test_create_empty_lines(self, po_service, seed_data):
        result = po_service.create_order(
            supplier_id=seed_data["supplier_id"], note=None, lines=[],
        )
        assert result.success


class TestConfirmAndCancel:
    def _create_po(self, po_service, seed_data):
        result = po_service.create_order(
            supplier_id=seed_data["supplier_id"], note=None,
            lines=[{"sku_id": seed_data["sku_id"], "ordered_quantity": 5, "unit_cost": 60}],
        )
        return uuid.UUID(result.data["po_id"])

    def test_confirm_draft(self, po_service, seed_data):
        po_id = self._create_po(po_service, seed_data)
        result = po_service.confirm_order(po_id)
        assert result.success
        assert "已確認" in result.message

    def test_confirm_non_draft_fails(self, po_service, seed_data):
        po_id = self._create_po(po_service, seed_data)
        po_service.confirm_order(po_id)
        result = po_service.confirm_order(po_id)
        assert not result.success
        assert "草稿" in result.message

    def test_cancel_draft(self, po_service, seed_data):
        po_id = self._create_po(po_service, seed_data)
        result = po_service.cancel_order(po_id)
        assert result.success

    def test_cancel_received_fails(self, db_session, po_service, seed_data):
        po_id = self._create_po(po_service, seed_data)
        po_service.confirm_order(po_id)
        db_session.execute(
            text("UPDATE purchase_orders SET status = 'received' WHERE po_id = :pid"),
            {"pid": str(po_id)},
        )
        db_session.flush()
        result = po_service.cancel_order(po_id)
        assert not result.success

    def test_not_found(self, po_service):
        result = po_service.confirm_order(uuid.uuid4())
        assert not result.success
        assert "不存在" in result.message


class TestReceiveOrder:
    def _create_and_confirm(self, db_session, po_service, seed_data, qty=10):
        create_result = po_service.create_order(
            supplier_id=seed_data["supplier_id"], note=None,
            lines=[{"sku_id": seed_data["sku_id"], "ordered_quantity": qty, "unit_cost": 60}],
        )
        po_id = uuid.UUID(create_result.data["po_id"])
        po_service.confirm_order(po_id)

        qs = ProcurementQueryService(db_session)
        lines = qs.get_purchase_order_lines(str(po_id))
        return po_id, lines[0]["po_line_id"]

    def test_full_receive(self, db_session, po_service, seed_data):
        po_id, line_id = self._create_and_confirm(db_session, po_service, seed_data, qty=10)
        result = po_service.receive_order(
            po_id, [{"po_line_id": str(line_id), "received_quantity": 10}],
            note="全收", user_id=FAKE_USER_ID,
        )
        assert result.success
        assert result.data["receipt_id"]
        assert "received" in result.message

    def test_partial_receive(self, db_session, po_service, seed_data):
        po_id, line_id = self._create_and_confirm(db_session, po_service, seed_data, qty=10)
        result = po_service.receive_order(
            po_id, [{"po_line_id": str(line_id), "received_quantity": 3}],
            note="先收一部分", user_id=FAKE_USER_ID,
        )
        assert result.success
        assert "partial_received" in result.message

    def test_receive_updates_inventory(self, db_session, po_service, seed_data):
        po_id, line_id = self._create_and_confirm(db_session, po_service, seed_data, qty=10)
        before = db_session.execute(
            text("SELECT current_stock FROM inventory_balances WHERE sku_id = :sid"),
            {"sid": seed_data["sku_id"]},
        ).scalar()

        po_service.receive_order(
            po_id, [{"po_line_id": str(line_id), "received_quantity": 10}],
            note=None, user_id=FAKE_USER_ID,
        )

        after = db_session.execute(
            text("SELECT current_stock FROM inventory_balances WHERE sku_id = :sid"),
            {"sid": seed_data["sku_id"]},
        ).scalar()
        assert after == before + 10

    def test_receive_creates_stock_movement(self, db_session, po_service, seed_data):
        po_id, line_id = self._create_and_confirm(db_session, po_service, seed_data, qty=5)
        po_service.receive_order(
            po_id, [{"po_line_id": str(line_id), "received_quantity": 5}],
            note=None, user_id=FAKE_USER_ID,
        )

        movement = db_session.execute(
            text("""
                SELECT quantity, movement_type, reference_type
                FROM stock_movements
                WHERE sku_id = :sid AND movement_type = 'purchase_receive'
                ORDER BY created_at DESC LIMIT 1
            """),
            {"sid": seed_data["sku_id"]},
        ).mappings().first()

        assert movement is not None
        assert movement["quantity"] == 5
        assert movement["reference_type"] == "purchase_receipt"

    def test_receive_draft_fails(self, db_session, po_service, seed_data):
        create_result = po_service.create_order(
            supplier_id=seed_data["supplier_id"], note=None,
            lines=[{"sku_id": seed_data["sku_id"], "ordered_quantity": 5, "unit_cost": 60}],
        )
        po_id = uuid.UUID(create_result.data["po_id"])
        qs = ProcurementQueryService(db_session)
        lines = qs.get_purchase_order_lines(str(po_id))

        result = po_service.receive_order(
            po_id, [{"po_line_id": str(lines[0]["po_line_id"]), "received_quantity": 5}],
            note=None, user_id=FAKE_USER_ID,
        )
        assert not result.success
        assert "draft" in result.message

    def test_receive_empty_lines_fails(self, db_session, po_service, seed_data):
        po_id, _ = self._create_and_confirm(db_session, po_service, seed_data)
        result = po_service.receive_order(po_id, [], note=None, user_id=FAKE_USER_ID)
        assert not result.success


class TestAutoCreateFromLowStock:
    def test_auto_create_when_low_stock(self, db_session, po_service, seed_data):
        result = po_service.auto_create_from_low_stock()
        assert result.success
        assert result.data["count"] >= 1
        assert len(result.data["po_ids"]) >= 1

    def test_auto_create_correct_quantity(self, db_session, po_service, seed_data):
        result = po_service.auto_create_from_low_stock()
        assert result.success

        qs = ProcurementQueryService(db_session)
        po_id = result.data["po_ids"][0]
        lines = qs.get_purchase_order_lines(po_id)
        our_line = [l for l in lines if str(l["sku_id"]) == seed_data["sku_id"]]
        if our_line:
            assert our_line[0]["ordered_quantity"] == 5

    def test_auto_create_no_low_stock(self, db_session, po_service, seed_data):
        db_session.execute(
            text("UPDATE inventory_balances SET current_stock = 100 WHERE sku_id = :sid"),
            {"sid": seed_data["sku_id"]},
        )
        db_session.flush()

        result = po_service.auto_create_from_low_stock()
        if result.success:
            qs = ProcurementQueryService(db_session)
            for po_id in result.data["po_ids"]:
                lines = qs.get_purchase_order_lines(po_id)
                our = [l for l in lines if str(l["sku_id"]) == seed_data["sku_id"]]
                assert len(our) == 0


class TestGetOrderWithAmounts:
    def test_order_has_totals(self, po_service, seed_data):
        create_result = po_service.create_order(
            supplier_id=seed_data["supplier_id"], note=None,
            lines=[{"sku_id": seed_data["sku_id"], "ordered_quantity": 10, "unit_cost": 60}],
        )
        po_id = uuid.UUID(create_result.data["po_id"])

        result = po_service.get_order(po_id)
        assert result.success
        assert result.data["ordered_total"] == 600
        assert result.data["received_total"] == 0
        assert result.data["lines"][0]["line_total"] == 600
