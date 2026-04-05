"""Product module integration tests — real DB, rollback after each test."""

import uuid

import pytest
from sqlalchemy import text

from application.product import (
    build_alias_service,
    build_attribute_service,
    build_bom_service,
    build_category_service,
    build_supplier_price_service,
)
from domain.product.models import (
    CategoryAttributeTemplate,
    ProductAttribute,
)
from infrastructure.persistence.repositories.product_repo_impl import (
    SqlCategoryRepository,
    SqlProductRepository,
    SqlSKURepository,
)
from domain.product.models import Category, Product, SKU


@pytest.fixture
def product_seed(db_session):
    """建立基礎資料：分類 + 品項 + SKU。"""
    category_id = str(uuid.uuid4())
    child_cat_id = str(uuid.uuid4())
    product_id = str(uuid.uuid4())
    sku_id = str(uuid.uuid4())
    sku_id_2 = str(uuid.uuid4())
    supplier_id = str(uuid.uuid4())

    db_session.execute(text(
        "INSERT INTO categories (category_id, name, sort_order) VALUES (:cid, '斷路器', 0)"
    ), {"cid": category_id})
    db_session.execute(text(
        "INSERT INTO categories (category_id, name, parent_id, sort_order) VALUES (:cid, '無熔絲', :pid, 1)"
    ), {"cid": child_cat_id, "pid": category_id})

    db_session.execute(text(
        "INSERT INTO products (product_id, name, category_id, is_active) VALUES (:pid, '無熔絲開關', :cid, true)"
    ), {"pid": product_id, "cid": category_id})

    for sid, spec, itype in [(sku_id, "2P 20A", "assembly"), (sku_id_2, "3P 30A", "component")]:
        db_session.execute(text("""
            INSERT INTO skus (sku_id, product_id, brand, spec, unit, sell_price, cost_price, item_type, is_active)
            VALUES (:sid, :pid, '士林', :spec, '個', 100, 60, :itype, true)
        """), {"sid": sid, "pid": product_id, "spec": spec, "itype": itype})
        db_session.execute(text(
            "INSERT INTO inventory_balances (sku_id, current_stock) VALUES (:sid, 10)"
        ), {"sid": sid})

    db_session.execute(text(
        "INSERT INTO suppliers (supplier_id, name, is_active) VALUES (:sid, '測試供應商', true)"
    ), {"sid": supplier_id})

    # supplier_products（報價測試需要）
    db_session.execute(text("""
        INSERT INTO supplier_products (sp_id, supplier_id, sku_id, unit_cost, is_preferred)
        VALUES (:spid, :sup_id, :sku_id, 60, true)
    """), {"spid": str(uuid.uuid4()), "sup_id": supplier_id, "sku_id": sku_id})

    db_session.flush()

    return {
        "category_id": category_id,
        "child_cat_id": child_cat_id,
        "product_id": product_id,
        "sku_id": sku_id,
        "sku_id_2": sku_id_2,
        "supplier_id": supplier_id,
    }


# ── Product / SKU CRUD ───────────────────────────────────


class TestProductCrudIntegration:
    def test_create_and_get_product(self, db_session, product_seed):
        repo = SqlProductRepository(db_session)
        p = Product(name="測試品", category_id=uuid.UUID(product_seed["category_id"]))
        saved = repo.save(p)
        assert saved.product_id is not None

        fetched = repo.get_by_id(saved.product_id)
        assert fetched is not None
        assert fetched.name == "測試品"

    def test_create_sku_with_inventory(self, db_session, product_seed):
        from infrastructure.persistence.repositories.inventory_repo_impl import SqlInventoryBalanceRepository
        sku_repo = SqlSKURepository(db_session)
        balance_repo = SqlInventoryBalanceRepository(db_session)

        sku = SKU(product_id=uuid.UUID(product_seed["product_id"]), brand="東元", spec="4P 40A", sell_price=300)
        saved = sku_repo.save(sku)
        balance_repo.ensure_exists(saved.sku_id)

        balance = db_session.execute(text(
            "SELECT current_stock FROM inventory_balances WHERE sku_id = :sid"
        ), {"sid": str(saved.sku_id)}).scalar()
        assert balance == 0


# ── BOM ──────────────────────────────────────────────────


class TestBomIntegration:
    def test_save_bom(self, db_session, product_seed):
        svc = build_bom_service(db_session)
        result = svc.save_bom(
            uuid.UUID(product_seed["sku_id"]),
            [{"child_sku_id": product_seed["sku_id_2"], "quantity": 2, "component_role": "主體"}],
        )
        assert result.success

        bom = db_session.execute(text(
            "SELECT * FROM product_bom WHERE parent_sku_id = :pid"
        ), {"pid": product_seed["sku_id"]}).mappings().all()
        assert len(bom) == 1
        assert bom[0]["quantity"] == 2

    def test_replace_bom(self, db_session, product_seed):
        svc = build_bom_service(db_session)
        # First save
        svc.save_bom(uuid.UUID(product_seed["sku_id"]),
                     [{"child_sku_id": product_seed["sku_id_2"], "quantity": 1}])
        # Replace with empty
        svc.save_bom(uuid.UUID(product_seed["sku_id"]), [])

        count = db_session.execute(text(
            "SELECT COUNT(*) FROM product_bom WHERE parent_sku_id = :pid"
        ), {"pid": product_seed["sku_id"]}).scalar()
        assert count == 0

    def test_non_assembly_rejected(self, db_session, product_seed):
        svc = build_bom_service(db_session)
        result = svc.save_bom(
            uuid.UUID(product_seed["sku_id_2"]),  # component, not assembly
            [{"child_sku_id": product_seed["sku_id"]}],
        )
        assert not result.success


# ── Alias ────────────────────────────────────────────────


class TestAliasIntegration:
    def test_create_and_delete(self, db_session, product_seed):
        svc = build_alias_service(db_session)
        pid = uuid.UUID(product_seed["product_id"])

        result = svc.create_alias(pid, "NFB", "common")
        assert result.success
        alias_id = uuid.UUID(result.data["alias_id"])

        del_result = svc.delete_alias(pid, alias_id)
        assert del_result.success

        count = db_session.execute(text(
            "SELECT COUNT(*) FROM product_aliases WHERE product_id = :pid"
        ), {"pid": product_seed["product_id"]}).scalar()
        assert count == 0


# ── Attributes ───────────────────────────────────────────


class TestAttributeIntegration:
    def test_replace_category_templates(self, db_session, product_seed):
        svc = build_attribute_service(db_session)
        cat_id = uuid.UUID(product_seed["category_id"])

        svc.replace_category_templates(cat_id, [
            CategoryAttributeTemplate(category_id=cat_id, attr_key="額定電流", attr_unit="A"),
            CategoryAttributeTemplate(category_id=cat_id, attr_key="極數"),
        ])

        count = db_session.execute(text(
            "SELECT COUNT(*) FROM category_attribute_templates WHERE category_id = :cid"
        ), {"cid": product_seed["category_id"]}).scalar()
        assert count == 2

    def test_replace_product_attributes(self, db_session, product_seed):
        svc = build_attribute_service(db_session)
        pid = uuid.UUID(product_seed["product_id"])

        svc.replace_product_attributes(pid, [
            ProductAttribute(product_id=pid, attr_key="電壓", attr_value="220V"),
        ])

        count = db_session.execute(text(
            "SELECT COUNT(*) FROM product_attributes WHERE product_id = :pid"
        ), {"pid": product_seed["product_id"]}).scalar()
        assert count == 1

    def test_replace_overwrites(self, db_session, product_seed):
        svc = build_attribute_service(db_session)
        pid = uuid.UUID(product_seed["product_id"])

        svc.replace_product_attributes(pid, [
            ProductAttribute(product_id=pid, attr_key="電壓", attr_value="220V"),
            ProductAttribute(product_id=pid, attr_key="電流", attr_value="20A"),
        ])
        svc.replace_product_attributes(pid, [
            ProductAttribute(product_id=pid, attr_key="電壓", attr_value="380V"),
        ])

        count = db_session.execute(text(
            "SELECT COUNT(*) FROM product_attributes WHERE product_id = :pid"
        ), {"pid": product_seed["product_id"]}).scalar()
        assert count == 1


# ── Supplier Price ───────────────────────────────────────


class TestSupplierPriceIntegration:
    def test_create_quote(self, db_session, product_seed):
        svc = build_supplier_price_service(db_session)
        result = svc.create_quote(
            product_id=uuid.UUID(product_seed["product_id"]),
            supplier_id=product_seed["supplier_id"],
            sku_id=product_seed["sku_id"],
            unit_price=75.0,
            user_id=uuid.uuid4(),
        )
        assert result.success

        quote = db_session.execute(text(
            "SELECT * FROM supplier_price_quotes WHERE sku_id = :sid"
        ), {"sid": product_seed["sku_id"]}).mappings().first()
        assert quote is not None
        assert float(quote["unit_price"]) == 75.0


# ── Category Delete ──────────────────────────────────────


class TestCategoryDeleteIntegration:
    def test_delete_empty_category(self, db_session):
        """沒有品項綁定的分類可以刪。"""
        cat_id = str(uuid.uuid4())
        db_session.execute(text(
            "INSERT INTO categories (category_id, name, sort_order) VALUES (:cid, '空分類', 0)"
        ), {"cid": cat_id})
        db_session.flush()

        svc = build_category_service(db_session)
        result = svc.delete_category(uuid.UUID(cat_id))
        assert result.success

        count = db_session.execute(text(
            "SELECT COUNT(*) FROM categories WHERE category_id = :cid"
        ), {"cid": cat_id}).scalar()
        assert count == 0

    def test_delete_with_products_rejected(self, db_session, product_seed):
        """有品項綁定的分類不能刪。"""
        svc = build_category_service(db_session)
        result = svc.delete_category(uuid.UUID(product_seed["category_id"]))
        assert not result.success
        assert "品項" in result.message
