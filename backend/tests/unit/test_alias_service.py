"""AliasService unit tests — mock repos, no DB."""

import uuid
from unittest.mock import MagicMock

import pytest

from application.product.alias_service import AliasService
from domain.product.models import ProductAlias


FAKE_PRODUCT = uuid.uuid4()
FAKE_USER = uuid.uuid4()


def _make_service(**overrides):
    defaults = {"alias_repo": MagicMock()}
    defaults.update(overrides)
    return AliasService(**defaults), defaults


class TestCreateAlias:
    def test_creates(self):
        svc, mocks = _make_service()
        mocks["alias_repo"].save.side_effect = lambda a: a

        result = svc.create_alias(FAKE_PRODUCT, "斷路器", "common", FAKE_USER)

        assert result.success
        assert result.data["alias"] == "斷路器"
        mocks["alias_repo"].save.assert_called_once()

    def test_strips_whitespace(self):
        svc, mocks = _make_service()
        mocks["alias_repo"].save.side_effect = lambda a: a

        svc.create_alias(FAKE_PRODUCT, "  開關  ", "common")

        saved = mocks["alias_repo"].save.call_args[0][0]
        assert saved.alias == "開關"


class TestDeleteAlias:
    def test_deletes(self):
        svc, mocks = _make_service()
        alias_id = uuid.uuid4()
        mocks["alias_repo"].get_by_id.return_value = ProductAlias(
            alias_id=alias_id, product_id=FAKE_PRODUCT, alias="test",
        )

        result = svc.delete_alias(FAKE_PRODUCT, alias_id)

        assert result.success
        mocks["alias_repo"].delete.assert_called_once_with(alias_id)

    def test_not_found(self):
        svc, mocks = _make_service()
        mocks["alias_repo"].get_by_id.return_value = None

        result = svc.delete_alias(FAKE_PRODUCT, uuid.uuid4())

        assert not result.success

    def test_wrong_product_rejected(self):
        svc, mocks = _make_service()
        alias_id = uuid.uuid4()
        mocks["alias_repo"].get_by_id.return_value = ProductAlias(
            alias_id=alias_id, product_id=uuid.uuid4(), alias="test",  # different product
        )

        result = svc.delete_alias(FAKE_PRODUCT, alias_id)

        assert not result.success
        mocks["alias_repo"].delete.assert_not_called()
