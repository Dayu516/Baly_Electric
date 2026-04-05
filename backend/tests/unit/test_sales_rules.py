"""Sales rules unit tests — 純邏輯，不碰 DB。"""

import uuid

import pytest

from application.sales.rules import (
    build_sale_lines,
    calculate_line_total,
    calculate_tax,
    derive_backorder_status,
    derive_fulfillment_status,
    derive_has_backorder,
    update_line_statuses,
)
from application.sales.schemas import CartItem
from domain.sales.models import SaleLine


# ── calculate_line_total ─────────────────────────────────


class TestCalculateLineTotal:
    def test_basic(self):
        assert calculate_line_total(100, 3, 0) == 300

    def test_with_discount(self):
        assert calculate_line_total(100, 3, 50) == 250

    def test_zero_quantity(self):
        assert calculate_line_total(100, 0, 0) == 0


# ── calculate_tax ────────────────────────────────────────


class TestCalculateTax:
    def test_none_mode(self):
        subtotal, tax, total, included = calculate_tax(1000, "none")
        assert subtotal == 1000
        assert tax == 0
        assert total == 1000
        assert included is False

    def test_included_mode(self):
        subtotal, tax, total, included = calculate_tax(1050, "included")
        assert subtotal == 1000
        assert tax == 50
        assert total == 1050
        assert included is True

    def test_extra_mode(self):
        subtotal, tax, total, included = calculate_tax(1000, "extra")
        assert subtotal == 1000
        assert tax == 50
        assert total == 1050
        assert included is True

    def test_included_rounding(self):
        subtotal, tax, total, included = calculate_tax(105, "included")
        assert subtotal == 100
        assert tax == 5
        assert total == 105

    def test_extra_rounding(self):
        subtotal, tax, total, included = calculate_tax(99, "extra")
        assert subtotal == 99
        assert tax == round(99 * 0.05, 2)
        assert total == 99 + round(99 * 0.05, 2)


# ── build_sale_lines ─────────────────────────────────────


class TestBuildSaleLines:
    def test_converts_cart_items(self):
        sale_id = uuid.uuid4()
        items = [
            CartItem(sku_id=uuid.uuid4(), quantity=2, unit_price=100, product_name="A", spec="2P"),
            CartItem(sku_id=uuid.uuid4(), quantity=1, unit_price=50, product_name="B", spec=None),
        ]
        lines = build_sale_lines(sale_id, items)
        assert len(lines) == 2
        assert lines[0].sale_id == sale_id
        assert lines[0].line_total == 200
        assert lines[1].line_total == 50

    def test_with_discount(self):
        sale_id = uuid.uuid4()
        items = [
            CartItem(sku_id=uuid.uuid4(), quantity=3, unit_price=100, discount_amount=30, product_name="X", spec=None),
        ]
        lines = build_sale_lines(sale_id, items)
        assert lines[0].line_total == 270


# ── derive_fulfillment_status ────────────────────────────


class TestDeriveFulfillmentStatus:
    def test_cancelled_when_qty_zero(self):
        line = SaleLine(ordered_qty=0, quantity=0)
        assert derive_fulfillment_status(line) == "cancelled"

    def test_completed_when_all_delivered(self):
        line = SaleLine(ordered_qty=10, delivered_qty=10, backorder_delivered_qty=0)
        assert derive_fulfillment_status(line) == "completed"

    def test_completed_with_backorder_delivery(self):
        line = SaleLine(ordered_qty=10, delivered_qty=5, backorder_qty=5, backorder_delivered_qty=5)
        assert derive_fulfillment_status(line) == "completed"

    def test_pending_no_delivery(self):
        line = SaleLine(ordered_qty=10, delivered_qty=0, backorder_qty=0)
        assert derive_fulfillment_status(line) == "pending"

    def test_fully_delivered(self):
        line = SaleLine(ordered_qty=10, delivered_qty=10, backorder_qty=0)
        assert derive_fulfillment_status(line) == "fully_delivered"

    def test_partially_delivered(self):
        line = SaleLine(ordered_qty=10, delivered_qty=3, backorder_qty=0)
        assert derive_fulfillment_status(line) == "partially_delivered"

    def test_backordered(self):
        line = SaleLine(ordered_qty=10, delivered_qty=0, backorder_qty=10)
        assert derive_fulfillment_status(line) == "backordered"

    def test_partially_backordered(self):
        line = SaleLine(ordered_qty=10, delivered_qty=5, backorder_qty=5)
        assert derive_fulfillment_status(line) == "partially_backordered"

    def test_waiting_arrival_ordered(self):
        line = SaleLine(ordered_qty=10, delivered_qty=5, backorder_qty=5, backorder_ordered_qty=5)
        assert derive_fulfillment_status(line) == "waiting_arrival"

    def test_waiting_arrival_partial(self):
        line = SaleLine(ordered_qty=10, delivered_qty=5, backorder_qty=5, backorder_ordered_qty=5, backorder_arrived_qty=2)
        assert derive_fulfillment_status(line) == "waiting_arrival"

    def test_ready_for_pickup(self):
        line = SaleLine(ordered_qty=10, delivered_qty=5, backorder_qty=5, backorder_ordered_qty=5, backorder_arrived_qty=5)
        assert derive_fulfillment_status(line) == "ready_for_pickup"

    def test_partially_picked_up(self):
        line = SaleLine(ordered_qty=10, delivered_qty=5, backorder_qty=5, backorder_delivered_qty=3, backorder_arrived_qty=5)
        assert derive_fulfillment_status(line) == "partially_picked_up"


# ── derive_backorder_status ──────────────────────────────


class TestDeriveBackorderStatus:
    def test_no_backorder(self):
        line = SaleLine(backorder_qty=0)
        assert derive_backorder_status(line) is None

    def test_pending(self):
        line = SaleLine(backorder_qty=5)
        assert derive_backorder_status(line) == "pending"

    def test_ordered(self):
        line = SaleLine(backorder_qty=5, backorder_ordered_qty=5)
        assert derive_backorder_status(line) == "ordered"

    def test_partial_arrived(self):
        line = SaleLine(backorder_qty=5, backorder_ordered_qty=5, backorder_arrived_qty=2)
        assert derive_backorder_status(line) == "partial_arrived"

    def test_arrived(self):
        line = SaleLine(backorder_qty=5, backorder_ordered_qty=5, backorder_arrived_qty=5)
        assert derive_backorder_status(line) == "arrived"

    def test_partial_delivered(self):
        line = SaleLine(backorder_qty=5, backorder_delivered_qty=3)
        assert derive_backorder_status(line) == "partial_delivered"

    def test_delivered(self):
        line = SaleLine(backorder_qty=5, backorder_delivered_qty=5)
        assert derive_backorder_status(line) == "delivered"


# ── update_line_statuses ─────────────────────────────────


class TestUpdateLineStatuses:
    def test_updates_both(self):
        line = SaleLine(ordered_qty=10, delivered_qty=5, backorder_qty=5, backorder_ordered_qty=5)
        result = update_line_statuses(line)
        assert result is line  # in-place
        assert line.fulfillment_status == "waiting_arrival"
        assert line.backorder_status == "ordered"


# ── derive_has_backorder ─────────────────────────────────


class TestDeriveHasBackorder:
    def test_no_backorder(self):
        lines = [SaleLine(backorder_qty=0), SaleLine(backorder_qty=0)]
        assert derive_has_backorder(lines) is False

    def test_has_backorder(self):
        lines = [SaleLine(backorder_qty=5, backorder_delivered_qty=0)]
        assert derive_has_backorder(lines) is True

    def test_backorder_fully_delivered(self):
        lines = [SaleLine(backorder_qty=5, backorder_delivered_qty=5)]
        assert derive_has_backorder(lines) is False
