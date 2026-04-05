"""AttributeService unit tests — mock repos, no DB."""

import uuid
from unittest.mock import MagicMock

import pytest

from application.product.attribute_service import AttributeService
from domain.product.models import CategoryAttributeTemplate, ProductAttribute


def _make_service(**overrides):
    defaults = {"template_repo": MagicMock(), "attr_repo": MagicMock()}
    defaults.update(overrides)
    return AttributeService(**defaults), defaults


class TestReplaceCategoryTemplates:
    def test_replaces(self):
        svc, mocks = _make_service()
        cat_id = uuid.uuid4()
        templates = [
            CategoryAttributeTemplate(category_id=cat_id, attr_key="額定電流", attr_unit="A"),
            CategoryAttributeTemplate(category_id=cat_id, attr_key="線徑", attr_unit="mm²"),
        ]
        count = svc.replace_category_templates(cat_id, templates)
        assert count == 2
        mocks["template_repo"].replace_for_category.assert_called_once_with(cat_id, templates)

    def test_empty_list(self):
        svc, mocks = _make_service()
        count = svc.replace_category_templates(uuid.uuid4(), [])
        assert count == 0
        mocks["template_repo"].replace_for_category.assert_called_once()


class TestReplaceProductAttributes:
    def test_replaces(self):
        svc, mocks = _make_service()
        pid = uuid.uuid4()
        attrs = [
            ProductAttribute(product_id=pid, attr_key="電壓", attr_value="220V"),
        ]
        count = svc.replace_product_attributes(pid, attrs)
        assert count == 1
        mocks["attr_repo"].replace_for_product.assert_called_once_with(pid, attrs)

    def test_empty_list(self):
        svc, mocks = _make_service()
        count = svc.replace_product_attributes(uuid.uuid4(), [])
        assert count == 0
