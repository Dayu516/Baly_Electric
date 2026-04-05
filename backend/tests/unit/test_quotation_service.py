"""QuotationService unit tests — mock repos, no DB."""

import uuid
from unittest.mock import MagicMock

from application.procurement.quotation_service import QuotationService
from application.procurement.rules import (
    build_sale_lines_from_quotation,
    calculate_subtotal,
)
from domain.procurement.models import SalesQuotation


FAKE_USER = uuid.uuid4()
FAKE_SKU = uuid.uuid4()
FAKE_CUSTOMER = uuid.uuid4()


def _make_service(**overrides):
    defaults = {
        "quotation_repo": MagicMock(),
        "quotation_line_repo": MagicMock(),
        "sale_repo": MagicMock(),
        "movement_repo": MagicMock(),
        "balance_repo": MagicMock(),
        "query_service": MagicMock(),
        "alert_repo": MagicMock(),
        "sku_repo": MagicMock(),
    }
    defaults.update(overrides)
    return QuotationService(**defaults), defaults


class TestCreateQuotation:
    def test_creates_quotation_and_lines(self):
        svc, m = _make_service()
        q = SalesQuotation(quotation_id=uuid.uuid4(), title="test", status="draft")
        m["quotation_repo"].save.return_value = q

        result = svc.create_quotation(
            str(FAKE_CUSTOMER), "test", None, None,
            [{"sku_id": str(FAKE_SKU), "quantity": 5, "unit_price": 100}],
            FAKE_USER,
        )
        assert result.success
        m["quotation_repo"].save.assert_called_once()
        m["quotation_line_repo"].save.assert_called_once()


class TestStatusTransitions:
    def test_send(self):
        svc, m = _make_service()
        q = SalesQuotation(quotation_id=uuid.uuid4(), status="draft")
        m["quotation_repo"].get_by_id.return_value = q

        result = svc.send_quotation(q.quotation_id)
        assert result.success
        assert q.status == "sent"

    def test_accept(self):
        svc, m = _make_service()
        q = SalesQuotation(quotation_id=uuid.uuid4(), status="sent")
        m["quotation_repo"].get_by_id.return_value = q

        result = svc.accept_quotation(q.quotation_id)
        assert result.success
        assert q.status == "accepted"

    def test_cancel(self):
        svc, m = _make_service()
        q = SalesQuotation(quotation_id=uuid.uuid4(), status="draft")
        m["quotation_repo"].get_by_id.return_value = q

        result = svc.cancel_quotation(q.quotation_id)
        assert result.success
        assert q.status == "cancelled"

    def test_not_found(self):
        svc, m = _make_service()
        m["quotation_repo"].get_by_id.return_value = None
        result = svc.send_quotation(uuid.uuid4())
        assert not result.success


class TestAddLine:
    def test_add_to_draft(self):
        svc, m = _make_service()
        q = SalesQuotation(quotation_id=uuid.uuid4(), status="draft")
        m["quotation_repo"].get_by_id.return_value = q

        result = svc.add_line(q.quotation_id, str(FAKE_SKU), 3, 80, None)
        assert result.success
        m["quotation_line_repo"].save.assert_called_once()

    def test_reject_converted(self):
        svc, m = _make_service()
        q = SalesQuotation(quotation_id=uuid.uuid4(), status="converted")
        m["quotation_repo"].get_by_id.return_value = q

        result = svc.add_line(q.quotation_id, str(FAKE_SKU), 3, 80, None)
        assert not result.success


class TestConvertToSale:
    def test_converts_accepted_quotation(self):
        svc, m = _make_service()
        q = SalesQuotation(quotation_id=uuid.uuid4(), customer_id=FAKE_CUSTOMER, title="test", status="accepted")
        m["quotation_repo"].get_by_id.return_value = q

        from domain.sales.models import Sale
        sale = Sale(sale_id=uuid.uuid4(), customer_id=FAKE_CUSTOMER, cashier_id=FAKE_USER)
        m["sale_repo"].save.return_value = sale

        m["query_service"].get_quotation_lines_for_convert.return_value = [
            {"sku_id": FAKE_SKU, "quantity": 5, "unit_price": 100, "product_name": "test", "spec": "x"},
        ]

        result = svc.convert_to_sale(q.quotation_id, FAKE_USER)
        assert result.success
        assert result.data["total"] == 500
        assert q.status == "converted"
        m["sale_repo"].save.assert_called_once()
        m["sale_repo"].save_lines.assert_called_once()
        m["movement_repo"].save.assert_called_once()
        m["balance_repo"].atomic_update.assert_called_once_with(FAKE_SKU, -5)

    def test_no_lines_fails(self):
        svc, m = _make_service()
        q = SalesQuotation(quotation_id=uuid.uuid4(), status="accepted")
        m["quotation_repo"].get_by_id.return_value = q
        m["query_service"].get_quotation_lines_for_convert.return_value = []

        result = svc.convert_to_sale(q.quotation_id, FAKE_USER)
        assert not result.success

    def test_cancelled_fails(self):
        svc, m = _make_service()
        q = SalesQuotation(quotation_id=uuid.uuid4(), status="cancelled")
        m["quotation_repo"].get_by_id.return_value = q

        result = svc.convert_to_sale(q.quotation_id, FAKE_USER)
        assert not result.success

    def test_payment_method_cash_when_no_customer(self):
        svc, m = _make_service()
        q = SalesQuotation(quotation_id=uuid.uuid4(), customer_id=None, title="test", status="draft")
        m["quotation_repo"].get_by_id.return_value = q

        from domain.sales.models import Sale
        sale = Sale(sale_id=uuid.uuid4())
        m["sale_repo"].save.return_value = sale

        m["query_service"].get_quotation_lines_for_convert.return_value = [
            {"sku_id": FAKE_SKU, "quantity": 1, "unit_price": 100, "product_name": "t", "spec": ""},
        ]

        result = svc.convert_to_sale(q.quotation_id, FAKE_USER)
        assert result.success
        # 確認用 cash（無客戶 = 現金）
        saved_sale = m["sale_repo"].save.call_args[0][0]
        assert saved_sale.payment_method == "cash"


class TestDeleteQuotation:
    def test_delete_cancelled(self):
        svc, m = _make_service()
        q = SalesQuotation(quotation_id=uuid.uuid4(), status="cancelled")
        m["quotation_repo"].get_by_id.return_value = q

        result = svc.delete_quotation(q.quotation_id)
        assert result.success
        m["quotation_repo"].delete.assert_called_once()

    def test_delete_non_cancelled_fails(self):
        svc, m = _make_service()
        q = SalesQuotation(quotation_id=uuid.uuid4(), status="draft")
        m["quotation_repo"].get_by_id.return_value = q

        result = svc.delete_quotation(q.quotation_id)
        assert not result.success


class TestPureFunctions:
    def test_calculate_subtotal(self):
        lines = [
            {"quantity": 5, "unit_price": 100},
            {"quantity": 3, "unit_price": 80},
        ]
        assert calculate_subtotal(lines) == 740  # 500 + 240

    def test_calculate_subtotal_empty(self):
        assert calculate_subtotal([]) == 0

    def test_build_sale_lines_from_quotation(self):
        sale_id = uuid.uuid4()
        lines = [
            {"sku_id": FAKE_SKU, "quantity": 5, "unit_price": 100, "product_name": "test", "spec": "x"},
        ]
        result = build_sale_lines_from_quotation(sale_id, lines)
        assert len(result) == 1
        assert result[0].sale_id == sale_id
        assert result[0].line_total == 500
        assert result[0].ordered_qty == 5
        assert result[0].delivered_qty == 5


# ── Low Stock Check ──────────────────────────────────────

class TestQuotationLowStock:
    def test_creates_alert_when_low(self):
        svc, mocks = _make_service()
        from domain.inventory.models import InventoryBalance
        from domain.product.models import SKU
        mocks["balance_repo"].get_by_sku.return_value = InventoryBalance(sku_id=FAKE_SKU, current_stock=2)
        mocks["sku_repo"].get_by_id.return_value = SKU(sku_id=FAKE_SKU, min_stock=5, brand="士林", spec="2P")

        svc.check_low_stock([str(FAKE_SKU)])

        mocks["alert_repo"].save.assert_called_once()
        alert = mocks["alert_repo"].save.call_args[0][0]
        assert alert.alert_type == "low_stock"

    def test_no_alert_when_sufficient(self):
        svc, mocks = _make_service()
        from domain.inventory.models import InventoryBalance
        from domain.product.models import SKU
        mocks["balance_repo"].get_by_sku.return_value = InventoryBalance(sku_id=FAKE_SKU, current_stock=10)
        mocks["sku_repo"].get_by_id.return_value = SKU(sku_id=FAKE_SKU, min_stock=5)

        svc.check_low_stock([str(FAKE_SKU)])

        mocks["alert_repo"].save.assert_not_called()

    def test_alert_failure_does_not_raise(self):
        svc, mocks = _make_service()
        from domain.inventory.models import InventoryBalance
        from domain.product.models import SKU
        mocks["balance_repo"].get_by_sku.return_value = InventoryBalance(sku_id=FAKE_SKU, current_stock=0)
        mocks["sku_repo"].get_by_id.return_value = SKU(sku_id=FAKE_SKU, min_stock=5)
        mocks["alert_repo"].save.side_effect = RuntimeError("DB error")

        svc.check_low_stock([str(FAKE_SKU)])  # 不拋異常
        assert result[0].fulfillment_status == "completed"
