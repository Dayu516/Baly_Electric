"""CategoryService unit tests — mock repos, no DB."""

import uuid
from unittest.mock import MagicMock

import pytest

from application.product.category_service import CategoryService
from domain.product.models import Category


FAKE_CAT = uuid.uuid4()


def _make_service(**overrides):
    defaults = {"category_repo": MagicMock(), "query_service": MagicMock()}
    defaults.update(overrides)
    return CategoryService(**defaults), defaults


class TestDeleteCategory:
    def test_not_found(self):
        svc, mocks = _make_service()
        mocks["category_repo"].get_by_id.return_value = None
        result = svc.delete_category(FAKE_CAT)
        assert not result.success
        assert "不存在" in result.message

    def test_has_products_rejected(self):
        svc, mocks = _make_service()
        mocks["category_repo"].get_by_id.return_value = Category(category_id=FAKE_CAT, name="分類A")
        mocks["query_service"].get_all_descendant_ids.return_value = [str(FAKE_CAT)]
        mocks["query_service"].count_products_in_categories.return_value = 3

        result = svc.delete_category(FAKE_CAT)
        assert not result.success
        assert "3 個品項" in result.message

    def test_successful_delete(self):
        svc, mocks = _make_service()
        mocks["category_repo"].get_by_id.return_value = Category(category_id=FAKE_CAT, name="分類A")
        mocks["query_service"].get_all_descendant_ids.return_value = [str(FAKE_CAT)]
        mocks["query_service"].count_products_in_categories.return_value = 0

        result = svc.delete_category(FAKE_CAT)
        assert result.success
        mocks["category_repo"].delete_batch_with_templates.assert_called_once()

    def test_recursive_delete(self):
        svc, mocks = _make_service()
        child_id = str(uuid.uuid4())
        mocks["category_repo"].get_by_id.return_value = Category(category_id=FAKE_CAT, name="父分類")
        mocks["query_service"].get_all_descendant_ids.return_value = [str(FAKE_CAT), child_id]
        mocks["query_service"].count_products_in_categories.return_value = 0

        result = svc.delete_category(FAKE_CAT)
        assert result.success
        assert result.data["deleted_count"] == 2
        assert "1 個子分類" in result.message

    def test_empty_category_ok(self):
        svc, mocks = _make_service()
        mocks["category_repo"].get_by_id.return_value = Category(category_id=FAKE_CAT, name="空分類")
        mocks["query_service"].get_all_descendant_ids.return_value = [str(FAKE_CAT)]
        mocks["query_service"].count_products_in_categories.return_value = 0

        result = svc.delete_category(FAKE_CAT)
        assert result.success
