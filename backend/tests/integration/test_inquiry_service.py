"""InquiryService integration tests — real DB, rollback."""

import uuid

import pytest

FAKE_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


class TestInquiryFlow:
    def _create_inquiry(self, inquiry_service, seed_data):
        result = inquiry_service.create_inquiry(
            title="4月電線詢價", note=None,
            lines=[{"sku_id": seed_data["sku_id"], "quantity": 10}],
            user_id=FAKE_USER_ID,
        )
        return uuid.UUID(result.data["inquiry_id"])

    def test_create_inquiry(self, inquiry_service, seed_data):
        inquiry_id = self._create_inquiry(inquiry_service, seed_data)
        result = inquiry_service.get_inquiry(inquiry_id)
        assert result.success
        assert result.data["title"] == "4月電線詢價"
        assert len(result.data["lines"]) == 1

    def test_add_line(self, inquiry_service, seed_data):
        inquiry_id = self._create_inquiry(inquiry_service, seed_data)
        result = inquiry_service.add_line(inquiry_id, seed_data["sku_id"], 5, "急單")
        assert result.success

    def test_add_quote(self, inquiry_service, seed_data):
        inquiry_id = self._create_inquiry(inquiry_service, seed_data)
        detail = inquiry_service.get_inquiry(inquiry_id)
        line_id = detail.data["lines"][0]["line_id"]

        result = inquiry_service.add_quote(
            inquiry_id, line_id, seed_data["supplier_id"],
            unit_price=55.0, note="電話報價", user_id=FAKE_USER_ID,
        )
        assert result.success
        assert "已記錄" in result.message

    def test_select_and_convert(self, inquiry_service, seed_data):
        inquiry_id = self._create_inquiry(inquiry_service, seed_data)

        detail = inquiry_service.get_inquiry(inquiry_id)
        line_id = detail.data["lines"][0]["line_id"]
        inquiry_service.add_quote(inquiry_id, line_id, seed_data["supplier_id"],
                                   unit_price=55.0, note=None, user_id=FAKE_USER_ID)

        detail = inquiry_service.get_inquiry(inquiry_id)
        quote_id = detail.data["lines"][0]["quotes"][0]["quote_id"]

        result = inquiry_service.select_quotes(inquiry_id, [quote_id])
        assert result.success

        result = inquiry_service.convert_to_po(inquiry_id)
        assert result.success
        assert len(result.data["po_ids"]) == 1

        detail = inquiry_service.get_inquiry(inquiry_id)
        assert detail.data["status"] == "converted"

    def test_convert_draft_fails(self, inquiry_service, seed_data):
        inquiry_id = self._create_inquiry(inquiry_service, seed_data)
        result = inquiry_service.convert_to_po(inquiry_id)
        assert not result.success
        assert "無法轉單" in result.message

    def test_cancel(self, inquiry_service, seed_data):
        inquiry_id = self._create_inquiry(inquiry_service, seed_data)
        result = inquiry_service.cancel_inquiry(inquiry_id)
        assert result.success
        detail = inquiry_service.get_inquiry(inquiry_id)
        assert detail.data["status"] == "cancelled"
