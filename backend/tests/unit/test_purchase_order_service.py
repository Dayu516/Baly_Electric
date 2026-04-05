"""PurchaseOrderService unit tests — mock repos, no DB."""

import uuid
from unittest.mock import MagicMock, patch

import pytest

from application.procurement.purchase_order_service import PurchaseOrderService
from application.procurement.rules import group_by_supplier
from domain.procurement.models import PurchaseOrder, PurchaseOrderLine


FAKE_USER = uuid.uuid4()
FAKE_SKU = uuid.uuid4()
FAKE_SUPPLIER = uuid.uuid4()


def _make_service(**overrides):
    defaults = {
        "po_repo": MagicMock(),
        "po_line_repo": MagicMock(),
        "receipt_repo": MagicMock(),
        "receipt_line_repo": MagicMock(),
        "movement_repo": MagicMock(),
        "balance_repo": MagicMock(),
        "query_service": MagicMock(),
        "backorder_service": MagicMock(),
    }
    defaults.update(overrides)
    return PurchaseOrderService(**defaults), defaults


class TestCreateOrder:
    def test_creates_po_and_lines(self):
        svc, mocks = _make_service()
        po = PurchaseOrder(po_id=uuid.uuid4(), supplier_id=FAKE_SUPPLIER, status="draft")
        mocks["po_repo"].save.return_value = po

        result = svc.create_order(
            supplier_id=str(FAKE_SUPPLIER),
            note="test",
            lines=[{"sku_id": str(FAKE_SKU), "ordered_quantity": 5, "unit_cost": 60}],
        )

        assert result.success
        assert result.data["po_id"] == str(po.po_id)
        mocks["po_repo"].save.assert_called_once()
        mocks["po_line_repo"].save.assert_called_once()

    def test_empty_lines_still_creates_po(self):
        svc, mocks = _make_service()
        po = PurchaseOrder(po_id=uuid.uuid4(), supplier_id=FAKE_SUPPLIER, status="draft")
        mocks["po_repo"].save.return_value = po

        result = svc.create_order(str(FAKE_SUPPLIER), None, [])
        assert result.success
        mocks["po_line_repo"].save.assert_not_called()


class TestConfirmOrder:
    def test_confirm_draft(self):
        svc, mocks = _make_service()
        po = PurchaseOrder(po_id=uuid.uuid4(), supplier_id=FAKE_SUPPLIER, status="draft")
        mocks["po_repo"].get_by_id.return_value = po
        mocks["po_repo"].save.return_value = po

        result = svc.confirm_order(po.po_id)
        assert result.success
        assert po.status == "ordered"
        assert po.ordered_at is not None

    def test_confirm_non_draft_fails(self):
        svc, mocks = _make_service()
        po = PurchaseOrder(po_id=uuid.uuid4(), supplier_id=FAKE_SUPPLIER, status="ordered")
        mocks["po_repo"].get_by_id.return_value = po

        result = svc.confirm_order(po.po_id)
        assert not result.success
        assert "草稿" in result.message

    def test_confirm_not_found(self):
        svc, mocks = _make_service()
        mocks["po_repo"].get_by_id.return_value = None

        result = svc.confirm_order(uuid.uuid4())
        assert not result.success
        assert "不存在" in result.message


class TestCancelOrder:
    def test_cancel_draft(self):
        svc, mocks = _make_service()
        po = PurchaseOrder(po_id=uuid.uuid4(), supplier_id=FAKE_SUPPLIER, status="draft")
        mocks["po_repo"].get_by_id.return_value = po
        mocks["po_repo"].save.return_value = po

        result = svc.cancel_order(po.po_id)
        assert result.success
        assert po.status == "cancelled"

    def test_cancel_received_fails(self):
        svc, mocks = _make_service()
        po = PurchaseOrder(po_id=uuid.uuid4(), supplier_id=FAKE_SUPPLIER, status="received")
        mocks["po_repo"].get_by_id.return_value = po

        result = svc.cancel_order(po.po_id)
        assert not result.success


class TestDeleteOrder:
    def test_delete_cancelled(self):
        svc, mocks = _make_service()
        po = PurchaseOrder(po_id=uuid.uuid4(), supplier_id=FAKE_SUPPLIER, status="cancelled")
        mocks["po_repo"].get_by_id.return_value = po

        result = svc.delete_order(po.po_id)
        assert result.success
        mocks["po_line_repo"].delete_by_po.assert_called_once_with(po.po_id)
        mocks["po_repo"].delete.assert_called_once_with(po.po_id)

    def test_delete_non_cancelled_fails(self):
        svc, mocks = _make_service()
        po = PurchaseOrder(po_id=uuid.uuid4(), supplier_id=FAKE_SUPPLIER, status="draft")
        mocks["po_repo"].get_by_id.return_value = po

        result = svc.delete_order(po.po_id)
        assert not result.success


class TestReceiveOrder:
    def test_receive_creates_receipt_and_movement(self):
        svc, mocks = _make_service()
        po_id = uuid.uuid4()
        po = PurchaseOrder(po_id=po_id, supplier_id=FAKE_SUPPLIER, status="ordered")
        mocks["po_repo"].get_by_id.return_value = po
        mocks["po_repo"].save.return_value = po

        po_line_id = uuid.uuid4()
        po_line = PurchaseOrderLine(
            po_line_id=po_line_id, po_id=po_id, sku_id=FAKE_SKU,
            ordered_quantity=10, received_quantity=0, unit_cost=60,
        )
        mocks["po_line_repo"].get_by_id.return_value = po_line
        mocks["po_line_repo"].save.return_value = po_line

        from domain.procurement.models import PurchaseReceipt
        receipt = PurchaseReceipt(receipt_id=uuid.uuid4(), po_id=po_id, supplier_id=FAKE_SUPPLIER, received_by=FAKE_USER)
        mocks["receipt_repo"].save.return_value = receipt

        # get_po_line_quantities — 模擬全收
        mocks["query_service"].get_po_line_quantities.return_value = [
            {"ordered_quantity": 10, "received_quantity": 10}
        ]
        mocks["query_service"].get_purchase_order_lines.return_value = []

        result = svc.receive_order(
            po_id,
            [{"po_line_id": str(po_line_id), "received_quantity": 10}],
            note="全收",
            user_id=FAKE_USER,
        )

        assert result.success
        mocks["receipt_repo"].save.assert_called_once()
        mocks["receipt_line_repo"].save.assert_called_once()
        mocks["movement_repo"].save.assert_called_once()
        mocks["balance_repo"].ensure_exists.assert_called_once_with(FAKE_SKU)
        mocks["balance_repo"].atomic_update.assert_called_once_with(FAKE_SKU, 10)
        assert po.status == "received"

    def test_receive_draft_fails(self):
        svc, mocks = _make_service()
        po = PurchaseOrder(po_id=uuid.uuid4(), supplier_id=FAKE_SUPPLIER, status="draft")
        mocks["po_repo"].get_by_id.return_value = po

        result = svc.receive_order(po.po_id, [{"po_line_id": str(uuid.uuid4()), "received_quantity": 5}],
                                    note=None, user_id=FAKE_USER)
        assert not result.success

    def test_receive_empty_lines_fails(self):
        svc, mocks = _make_service()
        po = PurchaseOrder(po_id=uuid.uuid4(), supplier_id=FAKE_SUPPLIER, status="ordered")
        mocks["po_repo"].get_by_id.return_value = po

        result = svc.receive_order(po.po_id, [], note=None, user_id=FAKE_USER)
        assert not result.success


class TestGroupBySupplier:
    def test_groups_correctly(self):
        items = [
            {"supplier_id": "A", "sku_id": "1"},
            {"supplier_id": "B", "sku_id": "2"},
            {"supplier_id": "A", "sku_id": "3"},
        ]
        result = group_by_supplier(items)
        assert len(result) == 2
        assert len(result["A"]) == 2
        assert len(result["B"]) == 1

    def test_empty(self):
        assert group_by_supplier([]) == {}


class TestBackorderOnReceive:
    def test_mark_arrived_called(self):
        svc, mocks = _make_service()
        po = PurchaseOrder(po_id=uuid.uuid4(), supplier_id=FAKE_SUPPLIER, status="ordered")
        mocks["po_repo"].get_by_id.return_value = po

        sale_line_id = str(uuid.uuid4())
        po_line = PurchaseOrderLine(
            po_line_id=uuid.uuid4(), po_id=po.po_id,
            sku_id=FAKE_SKU, ordered_quantity=10, unit_cost=60,
        )
        mocks["po_line_repo"].get_by_id.return_value = po_line
        mocks["receipt_repo"].save.side_effect = lambda r: r
        mocks["receipt_line_repo"].save.side_effect = lambda r: r
        mocks["movement_repo"].save.side_effect = lambda m: m
        mocks["po_line_repo"].save.side_effect = lambda l: l
        mocks["query_service"].get_po_line_quantities.return_value = [
            {"ordered_quantity": 10, "received_quantity": 5},
        ]
        mocks["query_service"].get_purchase_order_lines.return_value = [
            {"source_sale_line_id": sale_line_id, "received_quantity": 5},
        ]
        mocks["po_repo"].save.side_effect = lambda p: p

        svc.receive_order(po.po_id, [
            {"po_line_id": str(po_line.po_line_id), "received_quantity": 5},
        ], None, FAKE_USER)

        mocks["backorder_service"].mark_arrived.assert_called_once()

    def test_backorder_failure_does_not_break_receive(self):
        svc, mocks = _make_service()
        po = PurchaseOrder(po_id=uuid.uuid4(), supplier_id=FAKE_SUPPLIER, status="ordered")
        mocks["po_repo"].get_by_id.return_value = po

        po_line = PurchaseOrderLine(
            po_line_id=uuid.uuid4(), po_id=po.po_id,
            sku_id=FAKE_SKU, ordered_quantity=10, unit_cost=60,
        )
        mocks["po_line_repo"].get_by_id.return_value = po_line
        mocks["receipt_repo"].save.side_effect = lambda r: r
        mocks["receipt_line_repo"].save.side_effect = lambda r: r
        mocks["movement_repo"].save.side_effect = lambda m: m
        mocks["po_line_repo"].save.side_effect = lambda l: l
        mocks["query_service"].get_po_line_quantities.return_value = [
            {"ordered_quantity": 10, "received_quantity": 5},
        ]
        mocks["query_service"].get_purchase_order_lines.return_value = [
            {"source_sale_line_id": str(uuid.uuid4()), "received_quantity": 5},
        ]
        mocks["po_repo"].save.side_effect = lambda p: p
        mocks["backorder_service"].mark_arrived.side_effect = RuntimeError("DB error")

        result = svc.receive_order(po.po_id, [
            {"po_line_id": str(po_line.po_line_id), "received_quantity": 5},
        ], None, FAKE_USER)

        assert result.success  # 主流程不受影響


class TestPriceAnomaly:
    def _setup_receive(self, mocks, unit_cost=100):
        po = PurchaseOrder(po_id=uuid.uuid4(), supplier_id=FAKE_SUPPLIER, status="ordered")
        mocks["po_repo"].get_by_id.return_value = po
        po_line = PurchaseOrderLine(
            po_line_id=uuid.uuid4(), po_id=po.po_id,
            sku_id=FAKE_SKU, ordered_quantity=5, unit_cost=60,
        )
        mocks["po_line_repo"].get_by_id.return_value = po_line
        mocks["receipt_repo"].save.side_effect = lambda r: r
        mocks["receipt_line_repo"].save.side_effect = lambda r: r
        mocks["movement_repo"].save.side_effect = lambda m: m
        mocks["po_line_repo"].save.side_effect = lambda l: l
        mocks["po_repo"].save.side_effect = lambda p: p
        mocks["query_service"].get_po_line_quantities.return_value = [
            {"ordered_quantity": 5, "received_quantity": 5},
        ]
        mocks["query_service"].get_purchase_order_lines.return_value = []
        return po, po_line

    def test_triggers_alert_on_price_spike(self):
        svc, mocks = _make_service()
        po, po_line = self._setup_receive(mocks)
        mocks["query_service"].get_supplier_product_cost.return_value = 50.0  # baseline

        svc.receive_order(po.po_id, [
            {"po_line_id": str(po_line.po_line_id), "received_quantity": 5, "unit_cost": 70, "sku_id": str(FAKE_SKU)},
        ], None, FAKE_USER)

        mocks["alert_repo"].save.assert_called_once()
        alert = mocks["alert_repo"].save.call_args[0][0]
        assert alert.alert_type == "price_anomaly"
        assert alert.severity == "warning"

    def test_no_alert_within_threshold(self):
        svc, mocks = _make_service()
        po, po_line = self._setup_receive(mocks)
        mocks["query_service"].get_supplier_product_cost.return_value = 50.0

        svc.receive_order(po.po_id, [
            {"po_line_id": str(po_line.po_line_id), "received_quantity": 5, "unit_cost": 55, "sku_id": str(FAKE_SKU)},
        ], None, FAKE_USER)

        mocks["alert_repo"].save.assert_not_called()

    def test_no_alert_first_purchase(self):
        svc, mocks = _make_service()
        po, po_line = self._setup_receive(mocks)
        mocks["query_service"].get_supplier_product_cost.return_value = None  # 首次

        svc.receive_order(po.po_id, [
            {"po_line_id": str(po_line.po_line_id), "received_quantity": 5, "unit_cost": 100, "sku_id": str(FAKE_SKU)},
        ], None, FAKE_USER)

        mocks["alert_repo"].save.assert_not_called()

    def test_alert_failure_does_not_break_receive(self):
        svc, mocks = _make_service()
        po, po_line = self._setup_receive(mocks)
        mocks["query_service"].get_supplier_product_cost.return_value = 50.0
        mocks["alert_repo"].save.side_effect = RuntimeError("DB error")

        result = svc.receive_order(po.po_id, [
            {"po_line_id": str(po_line.po_line_id), "received_quantity": 5, "unit_cost": 100, "sku_id": str(FAKE_SKU)},
        ], None, FAKE_USER)

        assert result.success
