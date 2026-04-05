"""ReceivePurchaseOrderUseCase unit tests — mock all deps, no DB."""

import uuid
from unittest.mock import MagicMock

import pytest

from application.use_cases.receive_purchase_order import ReceivePurchaseOrderUseCase
from domain.inventory.models import InventoryBalance
from domain.procurement.models import PurchaseOrder, PurchaseOrderLine, PurchaseReceipt, PurchaseReceiptLine
from domain.product.models import SKU


FAKE_USER = uuid.uuid4()
FAKE_PO = uuid.uuid4()
FAKE_SKU = uuid.uuid4()
FAKE_PO_LINE = uuid.uuid4()


def _make_use_case(**overrides):
    po_service = MagicMock()
    po_service._po_line_repo = MagicMock()
    po_service._po_repo = MagicMock()
    po_service._movement_repo = MagicMock()
    po_service._balance_repo = MagicMock()

    defaults = {
        "po_service": po_service,
        "receipt_repo": MagicMock(),
        "receipt_line_repo": MagicMock(),
        "audit_service": MagicMock(),
        "alert_repo": MagicMock(),
        "balance_repo": MagicMock(),
        "sku_repo": MagicMock(),
        "query_service": MagicMock(),
        "session": MagicMock(),
    }
    defaults.update(overrides)
    return ReceivePurchaseOrderUseCase(**defaults), defaults


def _success_result(receipt_id=None):
    from core.results import Result
    return Result.ok(data={"receipt_id": str(receipt_id or uuid.uuid4())})


# ── Normal receive ───────────────────────────────────────


class TestNormalReceive:
    def test_successful_receive(self):
        uc, mocks = _make_use_case()
        mocks["receipt_repo"].find_by_idempotency_key.return_value = None
        mocks["query_service"].get_po_line_quantities_by_line.return_value = [
            {"po_line_id": str(FAKE_PO_LINE), "ordered_quantity": 10, "received_quantity": 0},
        ]
        mocks["po_service"].receive_order.return_value = _success_result()

        result = uc.execute(FAKE_PO, [
            {"po_line_id": str(FAKE_PO_LINE), "received_quantity": 5},
        ], None, FAKE_USER)

        assert result.success
        mocks["po_service"].receive_order.assert_called_once()
        mocks["audit_service"].log.assert_called_once()
        mocks["session"].commit.assert_called_once()


# ── Idempotency ──────────────────────────────────────────


class TestIdempotency:
    def test_same_key_same_qty_returns_existing(self):
        uc, mocks = _make_use_case()
        existing = PurchaseReceipt(receipt_id=uuid.uuid4(), po_id=FAKE_PO, received_by=FAKE_USER)
        mocks["receipt_repo"].find_by_idempotency_key.return_value = existing
        mocks["receipt_line_repo"].list_by_receipt.return_value = [
            PurchaseReceiptLine(sku_id=FAKE_SKU, quantity=5),
        ]

        result = uc.execute(FAKE_PO, [
            {"po_line_id": str(FAKE_PO_LINE), "received_quantity": 5},
        ], None, FAKE_USER, idempotency_key="key-1")

        assert result.success
        assert "冪等" in result.message
        mocks["po_service"].receive_order.assert_not_called()

    def test_same_key_different_qty_overwrites(self):
        uc, mocks = _make_use_case()
        existing = PurchaseReceipt(
            receipt_id=uuid.uuid4(), po_id=FAKE_PO, received_by=FAKE_USER,
        )
        mocks["receipt_repo"].find_by_idempotency_key.return_value = existing
        mocks["receipt_line_repo"].list_by_receipt.return_value = [
            PurchaseReceiptLine(sku_id=FAKE_SKU, quantity=5),
        ]
        # PO line for correction
        po_line = PurchaseOrderLine(
            po_line_id=FAKE_PO_LINE, po_id=FAKE_PO, sku_id=FAKE_SKU,
            ordered_quantity=10, received_quantity=5,
        )
        mocks["po_service"]._po_line_repo.get_by_id.return_value = po_line
        mocks["po_service"]._po_repo.get_by_id.return_value = PurchaseOrder(po_id=FAKE_PO, status="partial_received")
        mocks["query_service"].get_po_line_quantities.return_value = [
            {"ordered_quantity": 10, "received_quantity": 3},
        ]

        result = uc.execute(FAKE_PO, [
            {"po_line_id": str(FAKE_PO_LINE), "received_quantity": 3},
        ], None, FAKE_USER, idempotency_key="key-1")

        assert result.success
        assert "覆蓋" in result.message

    def test_overwrite_by_different_user_rejected(self):
        uc, mocks = _make_use_case()
        other_user = uuid.uuid4()
        existing = PurchaseReceipt(
            receipt_id=uuid.uuid4(), po_id=FAKE_PO, received_by=other_user,
        )
        mocks["receipt_repo"].find_by_idempotency_key.return_value = existing
        mocks["receipt_line_repo"].list_by_receipt.return_value = [
            PurchaseReceiptLine(sku_id=FAKE_SKU, quantity=5),
        ]

        result = uc.execute(FAKE_PO, [
            {"po_line_id": str(FAKE_PO_LINE), "received_quantity": 3},
        ], None, FAKE_USER, idempotency_key="key-1")

        assert not result.success
        assert "建立者" in result.message


# ── Over-receive 防護 ────────────────────────────────────


class TestOverReceive:
    def test_over_receive_rejected(self):
        uc, mocks = _make_use_case()
        mocks["receipt_repo"].find_by_idempotency_key.return_value = None
        mocks["query_service"].get_po_line_quantities_by_line.return_value = [
            {"po_line_id": str(FAKE_PO_LINE), "ordered_quantity": 10, "received_quantity": 8},
        ]

        result = uc.execute(FAKE_PO, [
            {"po_line_id": str(FAKE_PO_LINE), "received_quantity": 5},
        ], None, FAKE_USER)

        assert not result.success
        assert "超收" in result.message

    def test_exact_quantity_allowed(self):
        uc, mocks = _make_use_case()
        mocks["receipt_repo"].find_by_idempotency_key.return_value = None
        mocks["query_service"].get_po_line_quantities_by_line.return_value = [
            {"po_line_id": str(FAKE_PO_LINE), "ordered_quantity": 10, "received_quantity": 5},
        ]
        mocks["po_service"].receive_order.return_value = _success_result()

        result = uc.execute(FAKE_PO, [
            {"po_line_id": str(FAKE_PO_LINE), "received_quantity": 5},
        ], None, FAKE_USER)

        assert result.success


# ── Low stock alert resolve ──────────────────────────────


class TestLowStockResolve:
    def test_resolves_alert_when_stock_recovered(self):
        uc, mocks = _make_use_case()
        mocks["receipt_repo"].find_by_idempotency_key.return_value = None
        mocks["query_service"].get_po_line_quantities_by_line.return_value = [
            {"po_line_id": str(FAKE_PO_LINE), "ordered_quantity": 10, "received_quantity": 0},
        ]
        mocks["po_service"].receive_order.return_value = _success_result()

        # Post-commit: stock recovered
        po_line = PurchaseOrderLine(po_line_id=FAKE_PO_LINE, po_id=FAKE_PO, sku_id=FAKE_SKU)
        mocks["po_service"]._po_line_repo.get_by_id.return_value = po_line
        mocks["balance_repo"].get_by_sku.return_value = InventoryBalance(sku_id=FAKE_SKU, current_stock=15)
        mocks["sku_repo"].get_by_id.return_value = SKU(sku_id=FAKE_SKU, min_stock=10)

        from domain.alert.models import OperationalAlert
        active_alert = OperationalAlert(alert_id=uuid.uuid4(), alert_type="low_stock")
        mocks["alert_repo"].list_active_by_reference.return_value = [active_alert]

        uc.execute(FAKE_PO, [
            {"po_line_id": str(FAKE_PO_LINE), "received_quantity": 5},
        ], None, FAKE_USER)

        mocks["alert_repo"].mark_read.assert_called_once_with(active_alert.alert_id)

    def test_no_resolve_when_still_low(self):
        uc, mocks = _make_use_case()
        mocks["receipt_repo"].find_by_idempotency_key.return_value = None
        mocks["query_service"].get_po_line_quantities_by_line.return_value = [
            {"po_line_id": str(FAKE_PO_LINE), "ordered_quantity": 10, "received_quantity": 0},
        ]
        mocks["po_service"].receive_order.return_value = _success_result()

        po_line = PurchaseOrderLine(po_line_id=FAKE_PO_LINE, po_id=FAKE_PO, sku_id=FAKE_SKU)
        mocks["po_service"]._po_line_repo.get_by_id.return_value = po_line
        mocks["balance_repo"].get_by_sku.return_value = InventoryBalance(sku_id=FAKE_SKU, current_stock=3)
        mocks["sku_repo"].get_by_id.return_value = SKU(sku_id=FAKE_SKU, min_stock=10)

        uc.execute(FAKE_PO, [
            {"po_line_id": str(FAKE_PO_LINE), "received_quantity": 5},
        ], None, FAKE_USER)

        mocks["alert_repo"].mark_read.assert_not_called()
