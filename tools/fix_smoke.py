import pathlib

f = pathlib.Path(r"D:\OneDrive\6_projects\ottimo\backend\tests\smoke_test.py")
content = f.read_text(encoding="utf-8")

# 找 step_20_permission_check 方法
idx = content.find("    def step_20_permission_check(self):")
assert idx > 0, "not found"

# 找方法結尾（下一個 def 或 class 或 \n\n# ── Main）
end_search = content.find("\n\n# ── Main", idx)
if end_search < 0:
    end_search = content.find("\ndef main()", idx)

old_method = content[idx:end_search]

new_methods = '''    def step_20_aliases(self):
        print("\\n--- 20. Aliases ---")
        r = self.post(f"/products/{self.product_id}/aliases", json={
            "product_id": self.product_id, "alias": f"smoke別名{self._test_id}", "alias_type": "common"})
        self.check("Create Alias", r, 201)
        r = self.get(f"/products/{self.product_id}/aliases")
        data = self.check("List Aliases", r, 200)
        if data:
            self.assert_true("Alias exists", len(data.get("data", [])) > 0)
        r = self.get("/products/search", params={"q": f"smoke別名{self._test_id}"})
        data = self.check("Search by alias", r, 200)
        if data:
            self.assert_true("Alias search found", len(data.get("data", [])) > 0)

    def step_21_supplier(self):
        print("\\n--- 21. Supplier ---")
        r = self.post("/suppliers/", json={"name": f"Smoke供應商{self._test_id}"})
        data = self.check("Create Supplier", r, 201)
        if data and data.get("data"):
            self._supplier_id = data["data"]["supplier_id"]
        r = self.get("/suppliers/")
        data = self.check("List Suppliers", r, 200)
        if data:
            self.assert_true("Supplier exists", len(data.get("data", [])) > 0)

    def step_22_tax_checkout(self):
        print("\\n--- 22. Tax Checkout ---")
        r = self.post("/sales/", json={
            "customer_id": self.customer_id, "payment_method": "cash", "tax_mode": "included",
            "items": [{"sku_id": self.sku_id, "quantity": 1, "unit_price": 105, "product_name": "tax included test"}]})
        self.check("Checkout tax included", r, 201)
        r = self.post("/sales/", json={
            "payment_method": "cash", "tax_mode": "extra",
            "items": [{"sku_id": self.sku_id, "quantity": 1, "unit_price": 100, "product_name": "tax extra test"}]})
        self.check("Checkout tax extra", r, 201)

    def step_23_customer_ar_list(self):
        print("\\n--- 23. Customer AR List ---")
        r = self.get(f"/customers/{self.customer_id}/accounts-receivable")
        data = self.check("List AR", r, 200)
        if data:
            self.assert_true("AR records exist", len(data.get("data", [])) > 0)

    def step_24_permission_check(self):
        print("\\n--- 24. Permission Check ---")
        r = self.client.get(f"{self.base}/products/")
        self.check("No token -> 401", r, 401)
        r = self.client.get(f"{self.base}/products/", headers={"Authorization": "Bearer invalid"})
        self.check("Bad token -> 401", r, 401)

'''

content = content.replace(old_method, new_methods)
f.write_text(content, encoding="utf-8")
print("OK")