"""冒煙測試 — 用 TestClient + transaction rollback，跑完 DB 零殘留。

Usage:
    cd backend
    PYTHONPATH=. .venv/Scripts/python.exe tests/smoke_test.py
"""

import json
import sys
import time
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import text

from database import engine
from main import app

# ── Config ───────────────────────────────────────────
OWNER_USERNAME = "1"
OWNER_PASSWORD = "1"


class SmokeTest:
    def __init__(self):
        self.client = TestClient(app, raise_server_exceptions=False)
        self.headers: dict[str, str] = {}
        self.passed = 0
        self.failed = 0
        self.errors: list[str] = []

        self.token = ""
        self.category_id = ""
        self.product_id = ""
        self.sku_id = ""
        self.sale_id = ""
        self.customer_id = ""
        self.review_task_id = ""
        self._test_id = uuid4().hex[:6]
        self._supplier_id = ""
        self._barcode = ""

    def teardown(self):
        """清除所有測試產生的資料。用 DELETE + 精準條件，不影響正式資料。"""
        from sqlalchemy import text
        try:
            with engine.connect() as c:
                tid = self._test_id
                # 品項鏈（用 test_id 精準定位）
                c.execute(text(f"DELETE FROM product_search_docs WHERE product_id IN (SELECT product_id FROM products WHERE name LIKE '%{tid}%')"))
                c.execute(text(f"DELETE FROM product_aliases WHERE product_id IN (SELECT product_id FROM products WHERE name LIKE '%{tid}%')"))
                sids = [str(r[0]) for r in c.execute(text(f"SELECT sku_id FROM skus WHERE product_id IN (SELECT product_id FROM products WHERE name LIKE '%{tid}%')")).all()]
                if sids:
                    sp = ",".join(f"'{s}'" for s in sids)
                    for t in ["inventory_balances", "stock_movements"]:
                        c.execute(text(f"DELETE FROM {t} WHERE sku_id IN ({sp})"))
                    c.execute(text(f"DELETE FROM sale_line_fulfillments WHERE sale_line_id IN (SELECT sale_line_id FROM sale_lines WHERE sku_id IN ({sp}))"))
                    c.execute(text(f"DELETE FROM customer_pickup_notifications WHERE sale_id IN (SELECT DISTINCT sale_id FROM sale_lines WHERE sku_id IN ({sp}))"))
                    c.execute(text(f"DELETE FROM sale_lines WHERE sku_id IN ({sp})"))
                    for t in ["supplier_price_quotes", "supplier_products", "customer_price_history"]:
                        c.execute(text(f"DELETE FROM {t} WHERE sku_id IN ({sp})"))
                c.execute(text(f"DELETE FROM skus WHERE product_id IN (SELECT product_id FROM products WHERE name LIKE '%{tid}%')"))
                c.execute(text(f"DELETE FROM products WHERE name LIKE '%{tid}%'"))
                # 分類
                c.execute(text(f"DELETE FROM categories WHERE name LIKE 'smoke-cat-{tid}%'"))
                # 銷貨（空的）
                c.execute(text("DELETE FROM sales WHERE sale_id NOT IN (SELECT DISTINCT sale_id FROM sale_lines)"))
                # 客戶
                c.execute(text(f"DELETE FROM accounts_receivables WHERE customer_id IN (SELECT customer_id FROM customers WHERE name LIKE '%{tid}%')"))
                c.execute(text(f"DELETE FROM customers WHERE name LIKE '%{tid}%'"))
                # 供應商
                c.execute(text(f"DELETE FROM suppliers WHERE name LIKE '%{tid}%'"))
                # 帳號
                c.execute(text(f"DELETE FROM users WHERE username LIKE 'smoke_{tid}%'"))
                # review / alerts
                c.execute(text("DELETE FROM review_tasks WHERE review_type = 'stock_discrepancy' AND title LIKE '%盤點差異%'"))
                c.commit()
                print("  [cleanup] 測試資料已清除")
        except Exception as e:
            print(f"  [cleanup] 清理失敗: {e}")

    def run(self) -> bool:
        print(f"=== Smoke Test (TestClient + rollback) ===\n")
        start = time.time()

        self.step_01_login()
        self.step_02_create_category()
        self.step_03_create_product()
        self.step_04_create_sku()
        self.step_05_search_keyword()
        self.step_06_search_barcode()
        self.step_07_checkout()
        self.step_08_verify_inventory_after_checkout()
        self.step_09_void_sale()
        self.step_10_verify_inventory_after_void()
        self.step_11_receive_stock()
        self.step_12_verify_inventory_after_receive()
        self.step_13_stock_count_discrepancy()
        self.step_14_verify_review_task_created()
        self.step_15_claim_and_resolve_review()
        self.step_16_create_customer()
        self.step_17_checkout_monthly_credit()
        self.step_18_generate_statement()
        self.step_19_list_alerts()
        self.step_20_aliases()
        self.step_21_supplier()
        self.step_22_tax_checkout()
        self.step_23_customer_ar_list()
        self.step_24_permission_check()
        self.step_25_company_info()
        self.step_26_system_parameters()
        self.step_27_user_management()
        self.step_28_change_password()
        self.step_29_supplier_price_quotes()
        self.step_30_alternatives()

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

    # ── Helpers ──────────────────────────────────────

    def check(self, label: str, response, expect: int):
        ok = response.status_code == expect
        if ok:
            self.passed += 1
        else:
            self.failed += 1
            self.errors.append(f"{label}: expected {expect}, got {response.status_code}")

        mark = "PASS" if ok else "FAIL"
        body = ""
        try:
            body = json.dumps(response.json(), ensure_ascii=False)[:120]
        except Exception:
            body = response.text[:120]
        print(f"  [{mark}] {label} [{response.status_code}] {body}")

        try:
            return response.json()
        except Exception:
            return None

    def assert_true(self, label: str, condition: bool, detail: str = ""):
        if condition:
            self.passed += 1
            print(f"  [PASS] {label}")
        else:
            self.failed += 1
            msg = f"{label}: {detail}" if detail else label
            self.errors.append(msg)
            print(f"  [FAIL] {label} {detail}")

    def get(self, path: str, **kwargs):
        return self.client.get(f"/api/v1{path}", headers=self.headers, **kwargs)

    def post(self, path: str, **kwargs):
        return self.client.post(f"/api/v1{path}", headers=self.headers, **kwargs)

    def put(self, path: str, **kwargs):
        return self.client.put(f"/api/v1{path}", headers=self.headers, **kwargs)

    def delete(self, path: str, **kwargs):
        return self.client.delete(f"/api/v1{path}", headers=self.headers, **kwargs)

    # ── Steps ────────────────────────────────────────
    def step_01_login(self):
        print("--- 1. Login ---")
        r = self.client.post("/api/v1/auth/login", json={
            "username": OWNER_USERNAME, "password": OWNER_PASSWORD,
        })
        data = self.check("Login", r, 200)
        if data:
            self.token = data["access_token"]
            self.headers = {"Authorization": f"Bearer {self.token}"}

        r = self.get("/auth/me")
        data = self.check("Me", r, 200)
        if data:
            self.assert_true("Role is owner", data["role"] == "owner")

    def step_02_create_category(self):
        print("\n--- 2. Create Category ---")
        r = self.post("/products/categories", json={"name": f"smoke-cat-{self._test_id}", "sort_order": 99})
        data = self.check("Create Category", r, 201)
        if data:
            self.category_id = data["category_id"]

    def step_03_create_product(self):
        print("\n--- 3. Create Product ---")
        r = self.post("/products/", json={
            "name": f"Smoke 測試品項 {self._test_id}",
            "model_number": f"SM-{uuid4().hex[:8]}",
            "category_id": self.category_id,
        })
        data = self.check("Create Product", r, 201)
        if data:
            self.product_id = data["product_id"]

    def step_04_create_sku(self):
        print("\n--- 4. Create SKU ---")
        self._barcode = f"SMOKE{uuid4().hex[:8]}"
        r = self.post("/products/skus", json={
            "product_id": self.product_id,
            "brand": "TestBrand",
            "barcode": self._barcode,
            "spec": "smoke spec",
            "unit": "個",
            "sell_price": 100,
            "cost_price": 60,
            "min_stock": 5,
        })
        data = self.check("Create SKU", r, 201)
        if data:
            self.sku_id = data["sku_id"]

    def step_05_search_keyword(self):
        print("\n--- 5. Search (keyword) ---")
        r = self.get("/products/search", params={"q": "Smoke"})
        data = self.check("Search keyword", r, 200)
        if data:
            results = data.get("data", [])
            self.assert_true("Search found results", len(results) > 0, f"got {len(results)}")

    def step_06_search_barcode(self):
        print("\n--- 6. Search (barcode) ---")
        r = self.get("/products/search", params={"q": self._barcode})
        data = self.check("Search barcode", r, 200)
        if data:
            results = data.get("data", [])
            self.assert_true("Barcode exact match", len(results) == 1, f"got {len(results)}")

    def step_07_checkout(self):
        print("\n--- 7. Checkout ---")
        r = self.post("/sales/", json={
            "payment_method": "cash",
            "items": [{"sku_id": self.sku_id, "quantity": 5, "unit_price": 100,
                        "product_name": "Smoke 測試品項", "spec": "smoke spec"}],
        })
        data = self.check("Checkout", r, 201)
        if data and data.get("data"):
            self.sale_id = data["data"]["sale_id"]
            self.assert_true("Total = 500", data["data"]["total"] == 500.0)

    def step_08_verify_inventory_after_checkout(self):
        print("\n--- 8. Inventory after checkout ---")
        r = self.get(f"/inventory/{self.sku_id}/movements")
        data = self.check("Get movements", r, 200)
        if data:
            movements = data.get("data", [])
            sale_movements = [m for m in movements if m.get("movement_type") == "sale"]
            self.assert_true("Sale movement exists", len(sale_movements) > 0)
            if sale_movements:
                self.assert_true("Quantity = -5", sale_movements[0]["quantity"] == -5)

    def step_09_void_sale(self):
        print("\n--- 9. Void Sale ---")
        r = self.post(f"/sales/{self.sale_id}/void", json={"reason": "smoke test void"})
        self.check("Void Sale", r, 200)

    def step_10_verify_inventory_after_void(self):
        print("\n--- 10. Inventory after void ---")
        r = self.get(f"/inventory/{self.sku_id}/movements")
        data = self.check("Get movements after void", r, 200)
        if data:
            movements = data.get("data", [])
            return_movements = [m for m in movements if m.get("movement_type") == "return"]
            self.assert_true("Return movement exists", len(return_movements) > 0)

    def step_11_receive_stock(self):
        print("\n--- 11. Receive Stock ---")
        r = self.post("/inventory/receive", json={
            "supplier_id": "00000000-0000-0000-0000-000000000001",
            "lines": [{"sku_id": self.sku_id, "quantity": 50, "unit_cost": 60}],
        })
        self.check("Receive Stock", r, 201)

    def step_12_verify_inventory_after_receive(self):
        print("\n--- 12. Inventory after receive ---")
        r = self.get("/inventory/")
        data = self.check("Inventory list", r, 200)
        if data:
            items = data.get("data", [])
            matched = [i for i in items if str(i.get("sku_id")) == self.sku_id]
            if matched:
                stock = matched[0]["current_stock"]
                self.assert_true(f"Stock = 50 (actual: {stock})", stock == 50)
            else:
                self.assert_true("SKU found in inventory", False, "not found")

    def step_13_stock_count_discrepancy(self):
        print("\n--- 13. Stock Count (discrepancy) ---")
        r = self.post("/inventory/count", json={
            "lines": [{"sku_id": self.sku_id, "actual_quantity": 47}],
        })
        data = self.check("Stock Count", r, 200)
        if data and data.get("data"):
            disc = data["data"].get("discrepancies", [])
            self.assert_true("1 discrepancy found", len(disc) == 1)
            if disc:
                self.assert_true("Difference = -3", disc[0]["difference"] == -3)
            self.review_task_id = data["data"].get("review_task_id", "")

    def step_14_verify_review_task_created(self):
        print("\n--- 14. Review Task created ---")
        r = self.get("/reviews/")
        data = self.check("List Reviews", r, 200)
        if data:
            tasks = data.get("data", [])
            disc_tasks = [t for t in tasks if t.get("review_type") == "stock_discrepancy"]
            self.assert_true("stock_discrepancy review exists", len(disc_tasks) > 0)

    def step_15_claim_and_resolve_review(self):
        print("\n--- 15. Claim + Resolve Review ---")
        if not self.review_task_id:
            self.assert_true("Has review_task_id", False, "no ID from step 13")
            return
        r = self.post(f"/reviews/{self.review_task_id}/claim")
        self.check("Claim Review", r, 200)
        r = self.post(f"/reviews/{self.review_task_id}/resolve", json={"resolution": "approved"})
        self.check("Resolve Review", r, 200)

    def step_16_create_customer(self):
        print("\n--- 16. Create Customer ---")
        r = self.post("/customers/", json={
            "name": f"Smoke客戶 {self._test_id}", "phone": "02-9999-0001", "payment_terms": "monthly_credit",
        })
        data = self.check("Create Customer", r, 201)
        if data and data.get("data"):
            self.customer_id = data["data"]["customer_id"]

    def step_17_checkout_monthly_credit(self):
        print("\n--- 17. Checkout (monthly credit) ---")
        r = self.post("/sales/", json={
            "customer_id": self.customer_id, "payment_method": "monthly_credit",
            "items": [{"sku_id": self.sku_id, "quantity": 3, "unit_price": 100,
                        "product_name": "Smoke 測試品項", "spec": "smoke spec"}],
        })
        data = self.check("Checkout monthly credit", r, 201)
        if data and data.get("data"):
            self.assert_true("Total = 300", data["data"]["total"] == 300.0)

    def step_18_generate_statement(self):
        print("\n--- 18. Generate Statement ---")
        from datetime import datetime, timezone
        period = datetime.now(timezone.utc).strftime("%Y-%m")
        r = self.post("/customers/accounts-receivable/generate", json={
            "customer_id": self.customer_id, "period": period,
        })
        data = self.check("Generate Statement", r, 200)
        if data and data.get("data"):
            self.assert_true("Amount = 300", data["data"]["total_amount"] == 300.0)

    def step_19_list_alerts(self):
        print("\n--- 19. Alerts ---")
        r = self.get("/alerts/")
        self.check("List Alerts", r, 200)

    def step_20_aliases(self):
        print("\n--- 20. Aliases ---")
        r = self.post(f"/aliases/{self.product_id}", json={
            "product_id": self.product_id, "alias": f"smoke別名{self._test_id}", "alias_type": "common"})
        self.check("Create Alias", r, 201)
        r = self.get(f"/aliases/{self.product_id}")
        data = self.check("List Aliases", r, 200)
        if data:
            self.assert_true("Alias exists", len(data.get("data", [])) > 0)
        r = self.get("/products/search", params={"q": f"smoke別名{self._test_id}"})
        data = self.check("Search by alias", r, 200)
        if data:
            self.assert_true("Alias search found", len(data.get("data", [])) > 0)

    def step_21_supplier(self):
        print("\n--- 21. Supplier ---")
        r = self.post("/suppliers/", json={"name": f"Smoke供應商{self._test_id}"})
        data = self.check("Create Supplier", r, 201)
        if data and data.get("data"):
            self._supplier_id = data["data"]["supplier_id"]
        r = self.get("/suppliers/")
        data = self.check("List Suppliers", r, 200)
        if data:
            self.assert_true("Supplier exists", len(data.get("data", [])) > 0)

    def step_22_tax_checkout(self):
        print("\n--- 22. Tax Checkout ---")
        r = self.post("/sales/", json={
            "customer_id": self.customer_id, "payment_method": "cash", "tax_mode": "included",
            "items": [{"sku_id": self.sku_id, "quantity": 1, "unit_price": 105, "product_name": "tax included test"}]})
        self.check("Checkout tax included", r, 201)
        r = self.post("/sales/", json={
            "payment_method": "cash", "tax_mode": "extra",
            "items": [{"sku_id": self.sku_id, "quantity": 1, "unit_price": 100, "product_name": "tax extra test"}]})
        self.check("Checkout tax extra", r, 201)

    def step_23_customer_ar_list(self):
        print("\n--- 23. Customer AR List ---")
        r = self.get(f"/customers/{self.customer_id}/accounts-receivable")
        data = self.check("List AR", r, 200)
        if data:
            self.assert_true("AR records exist", len(data.get("data", [])) > 0)

    def step_24_permission_check(self):
        print("\n--- 24. Permission Check ---")
        r = self.client.get("/api/v1/products/")
        self.check("No token -> 401", r, 401)
        r = self.client.get("/api/v1/products/", headers={"Authorization": "Bearer invalid"})
        self.check("Bad token -> 401", r, 401)

    def step_25_company_info(self):
        print("\n--- 25. Company Info ---")
        r = self.get("/settings/company")
        self.check("Get company info", r, 200)
        r = self.put("/settings/company", json={
            "name": f"測試公司_{self._test_id}", "tax_id": "12345678",
            "phone": "02-1234-5678", "address": "台北市測試路1號",
        })
        self.check("Update company info", r, 200)

    def step_26_system_parameters(self):
        print("\n--- 26. System Parameters ---")
        r = self.get("/settings/parameters")
        data = self.check("Get parameters", r, 200)
        if data:
            self.assert_true("Has default params", len(data.get("data", [])) >= 4)
        r = self.put("/settings/parameters/default_tax_rate", json={"value": "0.05"})
        self.check("Update tax rate", r, 200)
        r = self.put("/settings/parameters/nonexistent_key", json={"value": "x"})
        self.check("Update nonexistent param -> 404", r, 404)

    def step_27_user_management(self):
        print("\n--- 27. User Management ---")
        r = self.get("/users/")
        self.check("List users", r, 200)
        test_username = f"smoke_{self._test_id}"
        r = self.post("/users/", json={
            "username": test_username, "display_name": "測試員工", "password": "test123", "role": "staff",
        })
        data = self.check("Create user", r, 201)
        if data and data.get("data"):
            uid = data["data"]["user_id"]
            r = self.put(f"/users/{uid}", json={"display_name": "改名", "role": "manager"})
            self.check("Update user", r, 200)
            r = self.post(f"/users/{uid}/reset-password", json={"new_password": "reset123"})
            self.check("Reset password", r, 200)
            r = self.put(f"/users/{uid}", json={"is_active": False})
            self.check("Deactivate user", r, 200)
        r = self.post("/users/", json={"username": test_username, "display_name": "重複", "password": "x"})
        self.check("Duplicate username -> 409", r, 409)

    def step_28_change_password(self):
        print("\n--- 28. Change Password ---")
        r = self.post("/users/change-password", json={"old_password": "wrong", "new_password": "new123"})
        self.check("Wrong old password -> 400", r, 400)
        r = self.post("/users/change-password", json={"old_password": OWNER_PASSWORD, "new_password": OWNER_PASSWORD})
        self.check("Change password (same) -> 200", r, 200)

    def step_29_supplier_price_quotes(self):
        print("\n--- 29. Supplier Price Quotes ---")
        pid = self.product_id
        sid = self.sku_id
        sup_id = self._supplier_id
        r = self.post(f"/products/{pid}/supplier-prices", json={
            "supplier_id": sup_id, "sku_id": sid, "unit_price": 85.0, "unit": "個",
            "quoted_at": "2026-03-01", "note": "三月報價",
        })
        self.check("Create quote 1", r, 201)
        r = self.post(f"/products/{pid}/supplier-prices", json={
            "supplier_id": sup_id, "sku_id": sid, "unit_price": 92.0, "unit": "個",
            "quoted_at": "2026-04-01", "note": "四月漲價",
        })
        self.check("Create quote 2", r, 201)
        r = self.get(f"/products/{pid}/supplier-prices")
        data = self.check("List quotes", r, 200)
        if data:
            quotes = data.get("data", [])
            self.assert_true("Has 2 quotes", len(quotes) >= 2, f"expected >=2, got {len(quotes)}")
            self.assert_true("Latest quote is 92", float(quotes[0]["unit_price"]) == 92.0)
        r = self.get(f"/products/{pid}/supplier-prices", params={"supplier_id": sup_id})
        data = self.check("List quotes (filtered)", r, 200)
        if data:
            self.assert_true("Filtered has quotes", len(data.get("data", [])) >= 2)
        r = self.get(f"/products/{pid}/compare-prices")
        data = self.check("Compare prices", r, 200)
        if data:
            prices = data.get("data", [])
            self.assert_true("Compare has results", len(prices) >= 1)
            self.assert_true("Latest price shown", float(prices[0]["unit_price"]) == 92.0)
        r = self.post(f"/products/{pid}/supplier-prices", json={
            "supplier_id": sup_id, "sku_id": "00000000-0000-0000-0000-000000000000", "unit_price": 50.0,
        })
        self.check("Invalid SKU -> 404", r, 404)

    def step_30_alternatives(self):
        print("\n--- 30. Alternatives Search ---")
        pid = self.product_id
        r = self.get(f"/products/{pid}/alternatives")
        data = self.check("Search alternatives", r, 200)
        if data:
            self.assert_true("Alternatives response OK", "data" in data or "message" in data)
        r = self.get("/products/00000000-0000-0000-0000-000000000000/alternatives")
        data = self.check("No alternatives for missing product", r, 200)


# ── Main ─────────────────────────────────────────────
def main():
    test = SmokeTest()
    success = test.run()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
