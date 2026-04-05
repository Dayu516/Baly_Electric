"""QuotationService integration tests — real DB, rollback."""

import uuid

import pytest
from sqlalchemy import text

FAKE_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


class TestQuotationFlow:
    def _create_customer(self, db_session):
        cid = str(uuid.uuid4())
        db_session.execute(text("""
            INSERT INTO customers (customer_id, name, payment_terms) VALUES (:cid, '測試客戶', 'cash')
        """), {"cid": cid})
        db_session.flush()
        return cid

    def _create_quotation(self, quotation_service, seed_data, customer_id=None):
        result = quotation_service.create_quotation(
            customer_id=customer_id,
            title="4月報價",
            valid_until=None,
            note=None,
            lines=[{"sku_id": seed_data["sku_id"], "quantity": 5, "unit_price": 100}],
            user_id=FAKE_USER_ID,
        )
        return uuid.UUID(result.data["quotation_id"])

    def test_create_quotation(self, quotation_service, seed_data):
        qid = self._create_quotation(quotation_service, seed_data)
        result = quotation_service.get_quotation(qid)
        assert result.success
        assert result.data["title"] == "4月報價"
        assert len(result.data["lines"]) == 1
        assert result.data["lines"][0]["unit_price"] == 100

    def test_add_line(self, quotation_service, seed_data):
        qid = self._create_quotation(quotation_service, seed_data)
        result = quotation_service.add_line(qid, seed_data["sku_id"], 3, 80, "特價")
        assert result.success

    def test_send_and_accept(self, quotation_service, seed_data):
        qid = self._create_quotation(quotation_service, seed_data)
        result = quotation_service.send_quotation(qid)
        assert result.success
        result = quotation_service.accept_quotation(qid)
        assert result.success

    def test_convert_to_sale(self, quotation_service, seed_data):
        qid = self._create_quotation(quotation_service, seed_data)
        quotation_service.accept_quotation(qid)
        result = quotation_service.convert_to_sale(qid, FAKE_USER_ID)
        assert result.success
        assert result.data["sale_id"]
        assert result.data["total"] == 500

    def test_convert_creates_stock_movement(self, db_session, quotation_service, seed_data):
        qid = self._create_quotation(quotation_service, seed_data)
        quotation_service.accept_quotation(qid)

        before = db_session.execute(
            text("SELECT current_stock FROM inventory_balances WHERE sku_id = :sid"),
            {"sid": seed_data["sku_id"]},
        ).scalar()

        quotation_service.convert_to_sale(qid, FAKE_USER_ID)

        after = db_session.execute(
            text("SELECT current_stock FROM inventory_balances WHERE sku_id = :sid"),
            {"sid": seed_data["sku_id"]},
        ).scalar()
        assert after == before - 5

    def test_convert_empty_quotation_fails(self, quotation_service, seed_data):
        result = quotation_service.create_quotation(
            customer_id=None, title="空報價", valid_until=None, note=None,
            lines=[], user_id=FAKE_USER_ID,
        )
        qid = uuid.UUID(result.data["quotation_id"])
        result = quotation_service.convert_to_sale(qid, FAKE_USER_ID)
        assert not result.success
        assert "沒有明細" in result.message

    def test_cancel(self, quotation_service, seed_data):
        qid = self._create_quotation(quotation_service, seed_data)
        result = quotation_service.cancel_quotation(qid)
        assert result.success
