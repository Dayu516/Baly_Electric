"""BackorderService unit tests — mock repos, no DB."""

import uuid
from unittest.mock import MagicMock, call

import pytest

from application.sales.backorder_service import BackorderService
from domain.sales.models import Sale, SaleLine, SaleLineFulfillment


FAKE_USER = uuid.uuid4()
FAKE_CUSTOMER = uuid.uuid4()
FAKE_SALE = uuid.uuid4()
FAKE_SKU = uuid.uuid4()


def _make_service(**overrides):
    defaults = {
        "sale_repo": MagicMock(),
        "sale_line_repo": MagicMock(),
        "fulfillment_repo": MagicMock(),
        "notification_repo": MagicMock(),
        "movement_repo": MagicMock(),
        "balance_repo": MagicMock(),
        "alert_repo": MagicMock(),
    }
    defaults.update(overrides)
    return BackorderService(**defaults), defaults


def _make_sale_line(**overrides):
    defaults = {
        "sale_line_id": uuid.uuid4(),
        "sale_id": FAKE_SALE,
        "sku_id": FAKE_SKU,
        "product_name": "測試品",
        "quantity": 10,
        "ordered_qty": 10,
        "delivered_qty": 10,
        "backorder_qty": 0,
        "backorder_ordered_qty": 0,
        "backorder_arrived_qty": 0,
        "backorder_delivered_qty": 0,
        "fulfillment_status": "completed",
    }
    defaults.update(overrides)
    return SaleLine(**defaults)


# ── create_backorder ─────────────────────────────────────


class TestCreateBackorder:
    def test_creates_backorder(self):
        svc, mocks = _make_service()
        sl = _make_sale_line(ordered_qty=10, delivered_qty=10)
        mocks["sale_line_repo"].get_by_id.return_value = sl
        mocks["sale_line_repo"].save.return_value = sl
        mocks["sale_repo"].get_by_id.return_value = Sale(sale_id=FAKE_SALE)
        mocks["sale_line_repo"].list_by_sale_id.return_value = [sl]

        result = svc.create_backorder(sl.sale_line_id, delivered_qty=6)

        assert result.success
        assert result.data["backorder_qty"] == 4
        mocks["sale_line_repo"].save.assert_called()

    def test_delivered_ge_ordered_rejected(self):
        svc, mocks = _make_service()
        sl = _make_sale_line(ordered_qty=10)
        mocks["sale_line_repo"].get_by_id.return_value = sl

        result = svc.create_backorder(sl.sale_line_id, delivered_qty=10)

        assert not result.success
        assert result.code == "ERR-BIZ-002"

    def test_negative_delivered_rejected(self):
        svc, mocks = _make_service()
        sl = _make_sale_line(ordered_qty=10)
        mocks["sale_line_repo"].get_by_id.return_value = sl

        result = svc.create_backorder(sl.sale_line_id, delivered_qty=-1)

        assert not result.success
        assert result.code == "ERR-BIZ-003"

    def test_nonexistent_line(self):
        svc, mocks = _make_service()
        mocks["sale_line_repo"].get_by_id.return_value = None

        result = svc.create_backorder(uuid.uuid4(), delivered_qty=5)

        assert not result.success
        assert result.code == "ERR-BIZ-001"

    def test_note_saved(self):
        svc, mocks = _make_service()
        sl = _make_sale_line(ordered_qty=10)
        mocks["sale_line_repo"].get_by_id.return_value = sl
        mocks["sale_line_repo"].save.return_value = sl
        mocks["sale_repo"].get_by_id.return_value = Sale(sale_id=FAKE_SALE)
        mocks["sale_line_repo"].list_by_sale_id.return_value = [sl]

        svc.create_backorder(sl.sale_line_id, delivered_qty=5, note="客人明天來拿")

        saved_line = mocks["sale_line_repo"].save.call_args_list[0][0][0]
        assert saved_line.reserved_customer_note == "客人明天來拿"


# ── link_to_po ───────────────────────────────────────────


class TestLinkToPo:
    def test_links_po(self):
        svc, mocks = _make_service()
        sl = _make_sale_line(backorder_qty=5, delivered_qty=5)
        mocks["sale_line_repo"].get_by_id.return_value = sl
        mocks["sale_line_repo"].save.return_value = sl
        mocks["fulfillment_repo"].save.return_value = SaleLineFulfillment()

        po_id = uuid.uuid4()
        result = svc.link_to_po(sl.sale_line_id, po_id, None, 5)

        assert result.success
        mocks["fulfillment_repo"].save.assert_called_once()

    def test_no_backorder_rejected(self):
        svc, mocks = _make_service()
        sl = _make_sale_line(backorder_qty=0)
        mocks["sale_line_repo"].get_by_id.return_value = sl

        result = svc.link_to_po(sl.sale_line_id, uuid.uuid4(), None, 5)

        assert not result.success
        assert result.code == "ERR-BIZ-004"


# ── mark_arrived ─────────────────────────────────────────


class TestMarkArrived:
    def test_marks_arrived(self):
        svc, mocks = _make_service()
        sl = _make_sale_line(backorder_qty=5, delivered_qty=5, backorder_ordered_qty=5)
        mocks["sale_line_repo"].get_by_id.return_value = sl
        mocks["sale_line_repo"].save.return_value = sl
        mocks["sale_repo"].get_by_id.return_value = Sale(sale_id=FAKE_SALE, customer_id=FAKE_CUSTOMER)

        po_id = uuid.uuid4()
        f1 = SaleLineFulfillment(allocated_qty=5, arrived_qty=0, delivered_qty=0, status="pending")
        mocks["fulfillment_repo"].list_by_sale_line_and_source.return_value = [f1]
        mocks["fulfillment_repo"].save.return_value = f1

        result = svc.mark_arrived(sl.sale_line_id, 5, po_id)

        assert result.success
        mocks["fulfillment_repo"].save.assert_called()

    def test_no_backorder_rejected(self):
        svc, mocks = _make_service()
        sl = _make_sale_line(backorder_qty=0)
        mocks["sale_line_repo"].get_by_id.return_value = sl

        result = svc.mark_arrived(sl.sale_line_id, 5)

        assert not result.success

    def test_creates_alert_for_customer(self):
        svc, mocks = _make_service()
        sl = _make_sale_line(backorder_qty=5, delivered_qty=5, backorder_ordered_qty=5)
        mocks["sale_line_repo"].get_by_id.return_value = sl
        mocks["sale_line_repo"].save.return_value = sl
        mocks["sale_repo"].get_by_id.return_value = Sale(sale_id=FAKE_SALE, customer_id=FAKE_CUSTOMER)
        mocks["fulfillment_repo"].list_by_sale_line_and_source.return_value = []

        svc.mark_arrived(sl.sale_line_id, 5)

        mocks["alert_repo"].save.assert_called_once()
        alert = mocks["alert_repo"].save.call_args[0][0]
        assert alert.alert_type == "backorder_arrived"
        assert alert.severity == "info"
        assert alert.reference_type == "sale_line"

    def test_no_alert_without_customer(self):
        svc, mocks = _make_service()
        sl = _make_sale_line(backorder_qty=5, delivered_qty=5)
        mocks["sale_line_repo"].get_by_id.return_value = sl
        mocks["sale_line_repo"].save.return_value = sl
        mocks["sale_repo"].get_by_id.return_value = Sale(sale_id=FAKE_SALE, customer_id=None)

        svc.mark_arrived(sl.sale_line_id, 5)

        mocks["alert_repo"].save.assert_not_called()

    def test_alert_failure_does_not_rollback(self):
        svc, mocks = _make_service()
        sl = _make_sale_line(backorder_qty=5, delivered_qty=5)
        mocks["sale_line_repo"].get_by_id.return_value = sl
        mocks["sale_line_repo"].save.return_value = sl
        mocks["sale_repo"].get_by_id.return_value = Sale(sale_id=FAKE_SALE, customer_id=FAKE_CUSTOMER)
        mocks["fulfillment_repo"].list_by_sale_line_and_source.return_value = []
        mocks["alert_repo"].save.side_effect = RuntimeError("DB error")

        result = svc.mark_arrived(sl.sale_line_id, 5)

        assert result.success  # 主流程不受影響


# ── deliver_backorder ────────────────────────────────────


class TestDeliverBackorder:
    def test_delivers(self):
        svc, mocks = _make_service()
        sl = _make_sale_line(backorder_qty=5, delivered_qty=5, backorder_delivered_qty=0)
        mocks["sale_line_repo"].get_by_id.return_value = sl
        mocks["sale_line_repo"].save.return_value = sl
        mocks["sale_line_repo"].list_by_sale_id.return_value = [sl]
        mocks["sale_repo"].get_by_id.return_value = Sale(sale_id=FAKE_SALE)
        mocks["sale_repo"].save.return_value = Sale(sale_id=FAKE_SALE)
        mocks["fulfillment_repo"].list_by_sale_line_id.return_value = []

        result = svc.deliver_backorder(sl.sale_line_id, 3, FAKE_USER)

        assert result.success
        mocks["movement_repo"].save.assert_called_once()
        mocks["balance_repo"].atomic_update.assert_called_once_with(FAKE_SKU, -3)

    def test_zero_qty_rejected(self):
        svc, mocks = _make_service()
        sl = _make_sale_line(backorder_qty=5, delivered_qty=5)
        mocks["sale_line_repo"].get_by_id.return_value = sl

        result = svc.deliver_backorder(sl.sale_line_id, 0, FAKE_USER)

        assert not result.success
        assert result.code == "ERR-BIZ-005"

    def test_exceeds_remaining_rejected(self):
        svc, mocks = _make_service()
        sl = _make_sale_line(backorder_qty=5, delivered_qty=5, backorder_delivered_qty=3)
        mocks["sale_line_repo"].get_by_id.return_value = sl

        result = svc.deliver_backorder(sl.sale_line_id, 5, FAKE_USER)

        assert not result.success
        assert result.code == "ERR-BIZ-006"

    def test_completes_when_all_delivered(self):
        svc, mocks = _make_service()
        sl = _make_sale_line(backorder_qty=5, delivered_qty=5, backorder_delivered_qty=0)
        mocks["sale_line_repo"].get_by_id.return_value = sl
        mocks["sale_line_repo"].save.return_value = sl
        mocks["sale_line_repo"].list_by_sale_id.return_value = [sl]
        mocks["sale_repo"].get_by_id.return_value = Sale(sale_id=FAKE_SALE)
        mocks["sale_repo"].save.return_value = Sale(sale_id=FAKE_SALE)
        mocks["fulfillment_repo"].list_by_sale_line_id.return_value = []

        svc.deliver_backorder(sl.sale_line_id, 5, FAKE_USER)

        saved_line = mocks["sale_line_repo"].save.call_args_list[0][0][0]
        assert saved_line.pickup_completed_at is not None
        assert saved_line.closed_at is not None

    def test_no_backorder_rejected(self):
        svc, mocks = _make_service()
        sl = _make_sale_line(backorder_qty=0)
        mocks["sale_line_repo"].get_by_id.return_value = sl

        result = svc.deliver_backorder(sl.sale_line_id, 1, FAKE_USER)

        assert not result.success
        assert result.code == "ERR-BIZ-004"


# ── notify_customer ──────────────────────────────────────


class TestNotifyCustomer:
    def test_single_line_notification(self):
        svc, mocks = _make_service()
        sale = Sale(sale_id=FAKE_SALE, customer_id=FAKE_CUSTOMER)
        mocks["sale_repo"].get_by_id.return_value = sale
        sl = _make_sale_line(backorder_qty=5, delivered_qty=5)
        mocks["sale_line_repo"].get_by_id.return_value = sl
        mocks["sale_line_repo"].save.return_value = sl

        result = svc.notify_customer(FAKE_SALE, sl.sale_line_id, "phone")

        assert result.success
        mocks["notification_repo"].save.assert_called_once()
        mocks["sale_line_repo"].save.assert_called_once()

    def test_whole_sale_notification(self):
        svc, mocks = _make_service()
        sale = Sale(sale_id=FAKE_SALE, customer_id=FAKE_CUSTOMER)
        mocks["sale_repo"].get_by_id.return_value = sale
        lines = [
            _make_sale_line(backorder_qty=5, delivered_qty=5),
            _make_sale_line(backorder_qty=3, delivered_qty=7),
            _make_sale_line(backorder_qty=0, delivered_qty=10),  # no backorder
        ]
        mocks["sale_line_repo"].list_by_sale_id.return_value = lines
        mocks["sale_line_repo"].save.return_value = lines[0]

        result = svc.notify_customer(FAKE_SALE, None, "manual")

        assert result.success
        # Only 2 lines with backorder_qty > 0
        assert mocks["sale_line_repo"].save.call_count == 2

    def test_no_customer_rejected(self):
        svc, mocks = _make_service()
        sale = Sale(sale_id=FAKE_SALE, customer_id=None)
        mocks["sale_repo"].get_by_id.return_value = sale

        result = svc.notify_customer(FAKE_SALE, None)

        assert not result.success
        assert result.code == "ERR-BIZ-007"

    def test_nonexistent_sale_rejected(self):
        svc, mocks = _make_service()
        mocks["sale_repo"].get_by_id.return_value = None

        result = svc.notify_customer(uuid.uuid4(), None)

        assert not result.success


# ── cancel_backorder ─────────────────────────────────────


class TestCancelBackorder:
    def test_cancels(self):
        svc, mocks = _make_service()
        sl = _make_sale_line(backorder_qty=5, delivered_qty=5)
        mocks["sale_line_repo"].get_by_id.return_value = sl
        mocks["sale_line_repo"].save.return_value = sl
        mocks["sale_line_repo"].list_by_sale_id.return_value = [sl]
        mocks["sale_repo"].get_by_id.return_value = Sale(sale_id=FAKE_SALE)
        mocks["sale_repo"].save.return_value = Sale(sale_id=FAKE_SALE)

        result = svc.cancel_backorder(sl.sale_line_id)

        assert result.success
        saved_line = mocks["sale_line_repo"].save.call_args_list[0][0][0]
        assert saved_line.backorder_qty == 0
        assert saved_line.backorder_status == "cancelled"
        assert saved_line.closed_at is not None

    def test_no_backorder_rejected(self):
        svc, mocks = _make_service()
        sl = _make_sale_line(backorder_qty=0)
        mocks["sale_line_repo"].get_by_id.return_value = sl

        result = svc.cancel_backorder(sl.sale_line_id)

        assert not result.success
        assert result.code == "ERR-BIZ-004"
