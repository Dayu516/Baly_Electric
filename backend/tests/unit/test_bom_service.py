"""BomService unit tests — mock repos, no DB."""

import uuid
from unittest.mock import MagicMock

import pytest

from application.product.bom_service import BomService
from domain.product.models import SKU


FAKE_PARENT = uuid.uuid4()
FAKE_CHILD_1 = uuid.uuid4()
FAKE_CHILD_2 = uuid.uuid4()


def _make_service(**overrides):
    defaults = {"sku_repo": MagicMock(), "bom_repo": MagicMock()}
    defaults.update(overrides)
    return BomService(**defaults), defaults


def _sku(sku_id, item_type="assembly"):
    return SKU(sku_id=sku_id, item_type=item_type)


class TestSaveBom:
    def test_successful_save(self):
        svc, mocks = _make_service()
        mocks["sku_repo"].get_by_id.side_effect = [
            _sku(FAKE_PARENT, "assembly"),
            _sku(FAKE_CHILD_1, "component"),
        ]
        result = svc.save_bom(FAKE_PARENT, [{"child_sku_id": str(FAKE_CHILD_1), "quantity": 2}])
        assert result.success
        mocks["bom_repo"].replace_children.assert_called_once()

    def test_parent_not_found(self):
        svc, mocks = _make_service()
        mocks["sku_repo"].get_by_id.return_value = None
        result = svc.save_bom(FAKE_PARENT, [])
        assert not result.success
        assert "不存在" in result.message

    def test_parent_not_assembly(self):
        svc, mocks = _make_service()
        mocks["sku_repo"].get_by_id.return_value = _sku(FAKE_PARENT, "finished")
        result = svc.save_bom(FAKE_PARENT, [{"child_sku_id": str(FAKE_CHILD_1)}])
        assert not result.success
        assert "組合品" in result.message

    def test_child_not_found(self):
        svc, mocks = _make_service()
        mocks["sku_repo"].get_by_id.side_effect = [_sku(FAKE_PARENT), None]
        result = svc.save_bom(FAKE_PARENT, [{"child_sku_id": str(FAKE_CHILD_1)}])
        assert not result.success
        assert "零件" in result.message

    def test_empty_children(self):
        svc, mocks = _make_service()
        mocks["sku_repo"].get_by_id.return_value = _sku(FAKE_PARENT)
        result = svc.save_bom(FAKE_PARENT, [])
        assert result.success
        mocks["bom_repo"].replace_children.assert_called_once()

    def test_multiple_children(self):
        svc, mocks = _make_service()
        mocks["sku_repo"].get_by_id.side_effect = [
            _sku(FAKE_PARENT), _sku(FAKE_CHILD_1, "component"), _sku(FAKE_CHILD_2, "component"),
        ]
        result = svc.save_bom(FAKE_PARENT, [
            {"child_sku_id": str(FAKE_CHILD_1)},
            {"child_sku_id": str(FAKE_CHILD_2)},
        ])
        assert result.success
        children = mocks["bom_repo"].replace_children.call_args[0][1]
        assert len(children) == 2


class TestValidateItemTypeChange:
    def test_assembly_to_finished_with_children_blocked(self):
        svc, mocks = _make_service()
        mocks["sku_repo"].get_by_id.return_value = _sku(FAKE_PARENT, "assembly")
        mocks["bom_repo"].has_children.return_value = True
        result = svc.validate_item_type_change(FAKE_PARENT, "finished")
        assert not result.success

    def test_assembly_to_finished_without_children_ok(self):
        svc, mocks = _make_service()
        mocks["sku_repo"].get_by_id.return_value = _sku(FAKE_PARENT, "assembly")
        mocks["bom_repo"].has_children.return_value = False
        result = svc.validate_item_type_change(FAKE_PARENT, "finished")
        assert result.success

    def test_component_to_finished_when_used_blocked(self):
        svc, mocks = _make_service()
        mocks["sku_repo"].get_by_id.return_value = _sku(FAKE_CHILD_1, "component")
        mocks["bom_repo"].is_child.return_value = True
        result = svc.validate_item_type_change(FAKE_CHILD_1, "finished")
        assert not result.success

    def test_invalid_type(self):
        svc, mocks = _make_service()
        result = svc.validate_item_type_change(FAKE_PARENT, "invalid")
        assert not result.success

    def test_sku_not_found(self):
        svc, mocks = _make_service()
        mocks["sku_repo"].get_by_id.return_value = None
        result = svc.validate_item_type_change(uuid.uuid4(), "finished")
        assert not result.success
