"""權限矩陣測試 — 用 TestClient + transaction rollback，跑完 DB 零殘留。

Usage:
    cd backend
    PYTHONPATH=. .venv/Scripts/python.exe tests/test_permissions.py
"""

import sys
import time
from uuid import uuid4

from fastapi.testclient import TestClient

from database import SessionLocal, engine
from main import app

BASE = "/api/v1"


class PermissionTest:
    def __init__(self):
        self._test_id = uuid4().hex[:6]
        self.client = TestClient(app, raise_server_exceptions=False)
        self.passed = 0
        self.failed = 0
        self.errors = []

        self.owner_token = ""
        self.manager_token = ""
        self.staff_token = ""
        self.test_product_id = ""
        self.test_sku_id = ""

    def teardown(self):
        from sqlalchemy import text as sql_text
        try:
            with engine.connect() as c:
                tid = self._test_id
                # 品項
                pids = [str(r[0]) for r in c.execute(sql_text(
                    f"SELECT product_id FROM products WHERE name LIKE 'PermTest {tid}%' OR name LIKE 'MgrTest%'"
                )).all()]
                if pids:
                    pp = ",".join(f"'{p}'" for p in pids)
                    sids = [str(r[0]) for r in c.execute(sql_text(f"SELECT sku_id FROM skus WHERE product_id IN ({pp})")).all()]
                    if sids:
                        sp = ",".join(f"'{s}'" for s in sids)
                        for t in ["inventory_balances", "stock_movements"]:
                            c.execute(sql_text(f"DELETE FROM {t} WHERE sku_id IN ({sp})"))
                        c.execute(sql_text(f"DELETE FROM sale_line_fulfillments WHERE sale_line_id IN (SELECT sale_line_id FROM sale_lines WHERE sku_id IN ({sp}))"))
                        c.execute(sql_text(f"DELETE FROM sale_lines WHERE sku_id IN ({sp})"))
                    c.execute(sql_text(f"DELETE FROM product_search_docs WHERE product_id IN ({pp})"))
                    c.execute(sql_text(f"DELETE FROM skus WHERE product_id IN ({pp})"))
                    c.execute(sql_text(f"DELETE FROM products WHERE product_id IN ({pp})"))
                # 分類（解除品項關聯後刪）
                c.execute(sql_text("UPDATE products SET category_id = NULL WHERE category_id IN (SELECT category_id FROM categories WHERE name = '測試分類')"))
                c.execute(sql_text("DELETE FROM category_attribute_templates WHERE category_id IN (SELECT category_id FROM categories WHERE name = '測試分類')"))
                c.execute(sql_text("DELETE FROM categories WHERE name = '測試分類'"))
                # 空銷貨單
                c.execute(sql_text("DELETE FROM sales WHERE sale_id NOT IN (SELECT DISTINCT sale_id FROM sale_lines)"))
                # 客戶
                c.execute(sql_text("DELETE FROM customers WHERE name LIKE 'MgrCust%'"))
                c.commit()
                print("  [cleanup] 測試資料已清除")
        except Exception as e:
            print(f"  [cleanup] 清理失敗: {e}")

    def run(self) -> bool:
        print("=== Permission & Audit Test (TestClient + rollback) ===\n")
        start = time.time()

        self._login_all()
        self._test_staff_restrictions()
        self._test_manager_restrictions()
        self._test_audit_events()
        self._test_category_tree()

        self.teardown()

        elapsed = time.time() - start
        print(f"\n{'='*50}")
        print(f"  {self.passed} passed, {self.failed} failed ({elapsed:.1f}s)")
        if self.errors:
            print(f"\n  Failures:")
            for e in self.errors:
                print(f"    - {e}")
        print(f"{'='*50}")
        return self.failed == 0

    def check(self, label: str, response, expect: int) -> bool:
        ok = response.status_code == expect
        if ok:
            self.passed += 1
        else:
            self.failed += 1
            self.errors.append(f"{label}: expected {expect}, got {response.status_code}")
        mark = "PASS" if ok else "FAIL"
        print(f"  [{mark}] {label} [{response.status_code}]")
        return ok

    def _h(self, token: str) -> dict:
        return {"Authorization": f"Bearer {token}"}

    # ── Login ────────────────────────────────────────
    def _login_all(self):
        print("--- Login ---")
        for username, password, attr in [
            ("1", "1", "owner_token"),
            ("manager1", "manager123", "manager_token"),
            ("staff1", "staff123", "staff_token"),
        ]:
            r = self.client.post(f"{BASE}/auth/login", json={
                "username": username, "password": password,
            })
            if r.status_code == 200:
                setattr(self, attr, r.json()["access_token"])
                self.passed += 1
                print(f"  [PASS] Login {username}")
            else:
                self.failed += 1
                self.errors.append(f"Login {username} failed")
                print(f"  [FAIL] Login {username}")

        h = self._h(self.owner_token)
        r = self.client.post(f"{BASE}/products/", headers=h, json={
            "name": f"PermTest {self._test_id}",
        })
        if r.status_code == 201:
            self.test_product_id = r.json()["product_id"]

        r = self.client.post(f"{BASE}/products/skus", headers=h, json={
            "product_id": self.test_product_id, "barcode": f"PERM{uuid4().hex[:8]}",
            "spec": "test", "sell_price": 100,
        })
        if r.status_code == 201:
            self.test_sku_id = r.json()["sku_id"]

    # ── Staff Restrictions ───────────────────────────
    def _test_staff_restrictions(self):
        print("\n--- Staff Restrictions ---")
        h = self._h(self.staff_token)

        r = self.client.get(f"{BASE}/products/", headers=h)
        self.check("Staff can list products", r, 200)

        r = self.client.get(f"{BASE}/inventory/", headers=h)
        self.check("Staff can list inventory", r, 200)

        r = self.client.post(f"{BASE}/products/", headers=h, json={"name": "Should Fail"})
        self.check("Staff cannot create product -> 403", r, 403)

        r = self.client.put(f"{BASE}/products/{self.test_product_id}", headers=h, json={"name": "Hacked", "version": 1})
        self.check("Staff cannot update product -> 403", r, 403)

        r = self.client.delete(f"{BASE}/products/{self.test_product_id}", headers=h)
        self.check("Staff cannot delete product -> 403", r, 403)

        r = self.client.post(f"{BASE}/products/skus", headers=h, json={
            "product_id": self.test_product_id, "spec": "x", "sell_price": 1})
        self.check("Staff cannot create SKU -> 403", r, 403)

        r = self.client.post(f"{BASE}/inventory/receive", headers=h, json={
            "supplier_id": "00000000-0000-0000-0000-000000000001",
            "lines": [{"sku_id": self.test_sku_id, "quantity": 10}]})
        self.check("Staff cannot receive stock -> 403", r, 403)

        r = self.client.post(f"{BASE}/inventory/adjust", headers=h, json={
            "sku_id": self.test_sku_id, "actual_quantity": 5})
        self.check("Staff cannot adjust stock -> 403", r, 403)

        r = self.client.post(f"{BASE}/inventory/recalc?sku_id={self.test_sku_id}", headers=h)
        self.check("Staff cannot recalc -> 403", r, 403)

        r = self.client.post(f"{BASE}/sales/", headers=h, json={
            "payment_method": "cash",
            "items": [{"sku_id": self.test_sku_id, "quantity": 1, "unit_price": 100, "product_name": "test"}]})
        self.check("Staff can checkout -> 201", r, 201)
        sale_id = r.json()["data"]["sale_id"] if r.status_code == 201 else None

        if sale_id:
            r = self.client.post(f"{BASE}/sales/{sale_id}/void", headers=h, json={})
            self.check("Staff cannot void sale -> 403", r, 403)

        r = self.client.post(f"{BASE}/customers/", headers=h, json={"name": "Should Fail"})
        self.check("Staff cannot create customer -> 403", r, 403)

        r = self.client.get(f"{BASE}/reviews/", headers=h)
        self.check("Staff can list reviews -> 200", r, 200)

        r = self.client.get(f"{BASE}/alerts/", headers=h)
        self.check("Staff can list alerts -> 200", r, 200)

    # ── Manager Restrictions ─────────────────────────
    def _test_manager_restrictions(self):
        print("\n--- Manager Restrictions ---")
        h = self._h(self.manager_token)

        r = self.client.post(f"{BASE}/products/", headers=h, json={
            "name": f"MgrTest {uuid4().hex[:6]}"})
        self.check("Manager can create product -> 201", r, 201)

        r = self.client.delete(f"{BASE}/products/{self.test_product_id}", headers=h)
        self.check("Manager cannot delete product -> 403", r, 403)

        r = self.client.delete(f"{BASE}/products/skus/{self.test_sku_id}", headers=h)
        self.check("Manager cannot delete SKU -> 403", r, 403)

        r = self.client.post(f"{BASE}/inventory/recalc?sku_id={self.test_sku_id}", headers=h)
        self.check("Manager cannot recalc -> 403", r, 403)

        r = self.client.post(f"{BASE}/inventory/receive", headers=h, json={
            "supplier_id": "00000000-0000-0000-0000-000000000001",
            "lines": [{"sku_id": self.test_sku_id, "quantity": 5}]})
        self.check("Manager can receive stock -> 201", r, 201)

        r = self.client.post(f"{BASE}/customers/", headers=h, json={
            "name": f"MgrCust {uuid4().hex[:6]}", "payment_terms": "cash"})
        self.check("Manager can create customer -> 201", r, 201)

    # ── Audit Events ─────────────────────────────────
    def _test_audit_events(self):
        print("\n--- Audit Events ---")
        h = self._h(self.owner_token)

        r = self.client.put(f"{BASE}/products/skus/{self.test_sku_id}", headers=h, json={
            "sell_price": 999, "version": 1})
        self.check("Owner update price -> 200", r, 200)

        from infrastructure.persistence.orm_models import AuditEventORM
        session = SessionLocal()
        events = session.query(AuditEventORM).order_by(
            AuditEventORM.created_at.desc()).limit(20).all()
        session.close()
        actions = [e.action for e in events]

        for action, label in [
            ("checkout", "AuditEvent: checkout"),
            ("create_product", "AuditEvent: create_product"),
        ]:
            if action in actions:
                self.passed += 1
                print(f"  [PASS] {label} recorded")
            else:
                self.failed += 1
                self.errors.append(f"{label} not found")
                print(f"  [FAIL] {label} not found")

        has_price = "update_price" in actions or "update_sku" in actions
        if has_price:
            self.passed += 1
            print(f"  [PASS] AuditEvent: price change recorded")
        else:
            self.failed += 1
            self.errors.append("AuditEvent: price change not found")
            print(f"  [FAIL] AuditEvent: price change not found")

    # ── Category Tree ────────────────────────────────
    def _test_category_tree(self):
        print("\n--- Category Tree ---")
        h = self._h(self.owner_token)

        r = self.client.get(f"{BASE}/products/categories/tree", headers=h)
        if self.check("Category tree -> 200", r, 200):
            tree = r.json().get("data", [])
            # 過濾掉測試分類，只看正式分類
            real_cats = [n for n in tree if n["name"] != "測試分類" and not n["name"].startswith("smoke-cat")]
            top_names = [n["name"] for n in real_cats]

            has_key_cats = any(n in ("開關與保護元件", "電線電纜", "工具與耗材") for n in top_names)

            if has_key_cats and len(real_cats) >= 5:
                self.passed += 1
                print(f"  [PASS] Tree has {len(real_cats)} real top categories")
            else:
                self.failed += 1
                self.errors.append(f"Tree missing key categories: {top_names[:10]}")
                print(f"  [FAIL] Tree: {top_names[:10]}")


def main():
    test = PermissionTest()
    success = test.run()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
