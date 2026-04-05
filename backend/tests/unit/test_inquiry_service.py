"""InquiryService unit tests — mock repos, no DB."""

import uuid
from unittest.mock import MagicMock

from application.procurement.inquiry_service import InquiryService
from application.procurement.rules import group_by_supplier
from domain.procurement.models import PurchaseInquiry, PurchaseInquiryLine


FAKE_USER = uuid.uuid4()
FAKE_SKU = uuid.uuid4()
FAKE_SUPPLIER = uuid.uuid4()


def _make_service(**overrides):
    defaults = {
        "inquiry_repo": MagicMock(),
        "inquiry_line_repo": MagicMock(),
        "inquiry_quote_repo": MagicMock(),
        "supplier_quote_repo": MagicMock(),
        "po_repo": MagicMock(),
        "po_line_repo": MagicMock(),
        "query_service": MagicMock(),
    }
    defaults.update(overrides)
    return InquiryService(**defaults), defaults


class TestCreateInquiry:
    def test_creates_inquiry_and_lines(self):
        svc, m = _make_service()
        inq = PurchaseInquiry(inquiry_id=uuid.uuid4(), title="test", status="draft")
        m["inquiry_repo"].save.return_value = inq

        result = svc.create_inquiry("test", None, [{"sku_id": str(FAKE_SKU), "quantity": 10}], FAKE_USER)
        assert result.success
        m["inquiry_repo"].save.assert_called_once()
        m["inquiry_line_repo"].save.assert_called_once()

    def test_empty_lines(self):
        svc, m = _make_service()
        inq = PurchaseInquiry(inquiry_id=uuid.uuid4(), title="test", status="draft")
        m["inquiry_repo"].save.return_value = inq

        result = svc.create_inquiry("test", None, [], FAKE_USER)
        assert result.success
        m["inquiry_line_repo"].save.assert_not_called()


class TestAddLine:
    def test_adds_to_draft(self):
        svc, m = _make_service()
        inq = PurchaseInquiry(inquiry_id=uuid.uuid4(), status="draft")
        m["inquiry_repo"].get_by_id.return_value = inq
        line = PurchaseInquiryLine(line_id=uuid.uuid4())
        m["inquiry_line_repo"].save.return_value = line

        result = svc.add_line(inq.inquiry_id, str(FAKE_SKU), 5, None)
        assert result.success
        assert inq.status == "quoting"  # auto-transition

    def test_rejects_converted(self):
        svc, m = _make_service()
        inq = PurchaseInquiry(inquiry_id=uuid.uuid4(), status="converted")
        m["inquiry_repo"].get_by_id.return_value = inq

        result = svc.add_line(inq.inquiry_id, str(FAKE_SKU), 5, None)
        assert not result.success

    def test_not_found(self):
        svc, m = _make_service()
        m["inquiry_repo"].get_by_id.return_value = None
        result = svc.add_line(uuid.uuid4(), str(FAKE_SKU), 5, None)
        assert not result.success


class TestAddQuote:
    def test_records_quote_and_global_history(self):
        svc, m = _make_service()
        inq = PurchaseInquiry(inquiry_id=uuid.uuid4(), title="test", status="quoting")
        m["inquiry_repo"].get_by_id.return_value = inq
        line = PurchaseInquiryLine(line_id=uuid.uuid4(), sku_id=FAKE_SKU)
        m["inquiry_line_repo"].get_by_id.return_value = line

        result = svc.add_quote(inq.inquiry_id, str(line.line_id), str(FAKE_SUPPLIER), 55.0, None, FAKE_USER)
        assert result.success
        m["inquiry_quote_repo"].save.assert_called_once()
        m["supplier_quote_repo"].save.assert_called_once()  # global history


class TestConvertToPo:
    def test_converts_with_selected_quotes(self):
        svc, m = _make_service()
        inq = PurchaseInquiry(inquiry_id=uuid.uuid4(), title="test", status="decided")
        m["inquiry_repo"].get_by_id.return_value = inq

        from domain.procurement.models import PurchaseOrder
        saved_po = PurchaseOrder(po_id=uuid.uuid4(), supplier_id=FAKE_SUPPLIER, status="draft")
        m["po_repo"].save.return_value = saved_po

        m["query_service"].get_selected_inquiry_quotes.return_value = [
            {"supplier_id": str(FAKE_SUPPLIER), "sku_id": FAKE_SKU, "quantity": 10, "unit_price": 55},
        ]

        result = svc.convert_to_po(inq.inquiry_id)
        assert result.success
        assert len(result.data["po_ids"]) == 1
        assert inq.status == "converted"

    def test_no_selected_fails(self):
        svc, m = _make_service()
        inq = PurchaseInquiry(inquiry_id=uuid.uuid4(), status="decided")
        m["inquiry_repo"].get_by_id.return_value = inq
        m["query_service"].get_selected_inquiry_quotes.return_value = []

        result = svc.convert_to_po(inq.inquiry_id)
        assert not result.success

    def test_draft_fails(self):
        svc, m = _make_service()
        inq = PurchaseInquiry(inquiry_id=uuid.uuid4(), status="draft")
        m["inquiry_repo"].get_by_id.return_value = inq

        result = svc.convert_to_po(inq.inquiry_id)
        assert not result.success


class TestCancelAndDelete:
    def test_cancel(self):
        svc, m = _make_service()
        inq = PurchaseInquiry(inquiry_id=uuid.uuid4(), status="draft")
        m["inquiry_repo"].get_by_id.return_value = inq

        result = svc.cancel_inquiry(inq.inquiry_id)
        assert result.success
        assert inq.status == "cancelled"

    def test_delete_cancelled(self):
        svc, m = _make_service()
        inq = PurchaseInquiry(inquiry_id=uuid.uuid4(), status="cancelled")
        m["inquiry_repo"].get_by_id.return_value = inq

        result = svc.delete_inquiry(inq.inquiry_id)
        assert result.success
        m["inquiry_repo"].delete.assert_called_once()

    def test_delete_non_cancelled_fails(self):
        svc, m = _make_service()
        inq = PurchaseInquiry(inquiry_id=uuid.uuid4(), status="draft")
        m["inquiry_repo"].get_by_id.return_value = inq

        result = svc.delete_inquiry(inq.inquiry_id)
        assert not result.success


class TestGroupQuotesBySupplier:
    def test_groups(self):
        result = group_by_supplier([
            {"supplier_id": "A", "sku_id": "1"},
            {"supplier_id": "B", "sku_id": "2"},
            {"supplier_id": "A", "sku_id": "3"},
        ])
        assert len(result) == 2
        assert len(result["A"]) == 2
