"""品項域查詢服務。"""

from sqlalchemy import text

from .base import BaseQueryService


class ProductQueryService(BaseQueryService):

    # ── 品項搜尋（Phase A：LIKE + 全文搜尋）──────────────
    def search_products(self, keyword: str, offset: int = 0, limit: int = 20) -> list[dict]:
        """關鍵字搜尋品項（型號、品名、條碼、別名、供應商料號、內部編號）。"""
        sql = text("""
            SELECT DISTINCT ON (s.sku_id)
                   p.product_id, p.name, p.raw_name, p.series,
                   p.model_number, p.category_id, p.is_active,
                   s.sku_id, s.brand, s.barcode, s.supplier_code, s.internal_code,
                   s.spec, s.unit, s.sell_price, s.cost_price, s.item_type,
                   COALESCE(ib.current_stock, 0) as current_stock
            FROM products p
            JOIN skus s ON s.product_id = p.product_id
            LEFT JOIN inventory_balances ib ON ib.sku_id = s.sku_id
            LEFT JOIN product_aliases pa ON pa.product_id = p.product_id
            WHERE p.is_active = true AND s.is_active = true
              AND (
                s.barcode = :exact_keyword
                OR s.supplier_code = :exact_keyword
                OR s.internal_code = :exact_keyword
                OR p.name ILIKE :like_keyword
                OR p.raw_name ILIKE :like_keyword
                OR p.model_number ILIKE :like_keyword
                OR s.brand ILIKE :like_keyword
                OR p.series ILIKE :like_keyword
                OR s.spec ILIKE :like_keyword
                OR pa.alias ILIKE :like_keyword
              )
            ORDER BY s.sku_id,
              CASE WHEN s.barcode = :exact_keyword THEN 0
                   WHEN s.internal_code = :exact_keyword THEN 1
                   ELSE 2 END
            OFFSET :offset LIMIT :limit
        """)
        rows = self._session.execute(
            sql,
            {
                "exact_keyword": keyword,
                "like_keyword": f"%{keyword}%",
                "offset": offset,
                "limit": limit,
            },
        ).mappings().all()
        return [dict(r) for r in rows]

    # ── 品項詳情查詢 ─────────────────────────────────
    def get_first_sku_id(self, product_id: str) -> str | None:
        sql = text("SELECT sku_id FROM skus WHERE product_id = :pid AND is_active = true LIMIT 1")
        result = self._session.execute(sql, {"pid": product_id}).scalar()
        return str(result) if result else None

    def get_sku_detail(self, sku_id: str) -> dict | None:
        sql = text("""
            SELECT s.sku_id, s.brand, s.barcode, s.supplier_code, s.internal_code,
                   s.spec, s.unit, s.sell_price, s.cost_price, s.min_stock, s.item_type,
                   p.product_id, p.name, p.raw_name, p.series, p.model_number, p.category_id,
                   COALESCE(ib.current_stock, 0) as current_stock
            FROM skus s
            JOIN products p ON p.product_id = s.product_id
            LEFT JOIN inventory_balances ib ON ib.sku_id = s.sku_id
            WHERE s.sku_id = :sku_id
        """)
        row = self._session.execute(sql, {"sku_id": sku_id}).mappings().first()
        return dict(row) if row else None

    def get_sku_suppliers(self, sku_id: str) -> list[dict]:
        sql = text("""
            SELECT sp.sp_id, sp.supplier_id, sp.supplier_product_name, sp.supplier_product_code,
                   sp.pack_unit, sp.pack_qty, sp.min_order_qty, sp.lead_days,
                   sp.unit_cost, sp.is_preferred, sp.note,
                   sup.name as supplier_name, sup.phone as supplier_phone
            FROM supplier_products sp
            JOIN suppliers sup ON sup.supplier_id = sp.supplier_id
            WHERE sp.sku_id = :sku_id AND sup.is_active = true
            ORDER BY sp.is_preferred DESC, sp.unit_cost ASC
        """)
        rows = self._session.execute(sql, {"sku_id": sku_id}).mappings().all()
        return [dict(r) for r in rows]

    def get_product_aliases(self, product_id: str) -> list[dict]:
        sql = text("""
            SELECT alias_id, alias, alias_type
            FROM product_aliases
            WHERE product_id = :product_id
            ORDER BY alias
        """)
        rows = self._session.execute(sql, {"product_id": product_id}).mappings().all()
        return [dict(r) for r in rows]

    def get_recent_movements(self, sku_id: str, limit: int = 5) -> list[dict]:
        sql = text("""
            SELECT movement_id, quantity, movement_type, note, created_at
            FROM stock_movements
            WHERE sku_id = :sku_id
            ORDER BY created_at DESC
            LIMIT :limit
        """)
        rows = self._session.execute(sql, {"sku_id": sku_id, "limit": limit}).mappings().all()
        return [dict(r) for r in rows]

    # ── 供應商報價查詢 ─────────────────────────────────
    def verify_sku_belongs_to_product(self, sku_id: str, product_id: str) -> bool:
        sql = text("SELECT sku_id FROM skus WHERE sku_id = :sid AND product_id = :pid")
        return self._session.execute(sql, {"sid": sku_id, "pid": product_id}).scalar() is not None

    def get_active_supplier_name(self, supplier_id: str) -> str | None:
        sql = text("SELECT name FROM suppliers WHERE supplier_id = :sid AND is_active = true")
        return self._session.execute(sql, {"sid": supplier_id}).scalar()

    # ── 替代品搜尋 ───────────────────────────────────
    def find_alternatives(self, sku_id: str, limit: int = 20) -> dict:
        """找替代品：同分類、庫存>0、按屬性匹配度排序。

        回傳 {"target": {...}, "templates": [...], "alternatives": [...]}
        """
        # 1. 取得目標 SKU 的資訊 + 分類 + 屬性
        target_sql = text("""
            SELECT s.sku_id, s.brand, s.spec, s.unit, s.sell_price,
                   p.product_id, p.name, p.category_id,
                   COALESCE(ib.current_stock, 0) as current_stock
            FROM skus s
            JOIN products p ON p.product_id = s.product_id
            LEFT JOIN inventory_balances ib ON ib.sku_id = s.sku_id
            WHERE s.sku_id = :sku_id
        """)
        target = self._session.execute(target_sql, {"sku_id": sku_id}).mappings().first()
        if not target or not target["category_id"]:
            return {"target": None, "templates": [], "alternatives": []}

        category_id = str(target["category_id"])

        # 2. 取得分類的屬性模板（有 match_priority 的）
        tmpl_sql = text("""
            SELECT attr_key, match_priority, match_type
            FROM category_attribute_templates
            WHERE category_id = :cat_id AND match_priority IS NOT NULL
            ORDER BY match_priority
        """)
        templates = self._session.execute(tmpl_sql, {"cat_id": category_id}).mappings().all()

        # 3. 取得目標 SKU 的屬性
        target_attrs_sql = text("""
            SELECT attr_key, attr_value
            FROM product_attributes
            WHERE product_id = :pid
        """)
        target_attrs = {
            r["attr_key"]: r["attr_value"]
            for r in self._session.execute(target_attrs_sql, {"pid": str(target["product_id"])}).mappings().all()
        }

        # 加上品牌（品牌在 SKU 層級，不在 product_attributes）
        if target["brand"]:
            target_attrs["品牌"] = target["brand"]

        # 4. 找同分類、庫存>0、排除自己的 SKU
        candidates_sql = text("""
            SELECT s.sku_id, s.brand, s.spec, s.unit, s.sell_price, s.cost_price,
                   p.product_id, p.name,
                   COALESCE(ib.current_stock, 0) as current_stock,
                   s.min_stock
            FROM skus s
            JOIN products p ON p.product_id = s.product_id
            LEFT JOIN inventory_balances ib ON ib.sku_id = s.sku_id
            WHERE p.category_id = :cat_id
              AND s.is_active = true AND p.is_active = true
              AND s.sku_id != :sku_id
              AND COALESCE(ib.current_stock, 0) > 0
        """)
        candidates = self._session.execute(
            candidates_sql, {"cat_id": category_id, "sku_id": sku_id}
        ).mappings().all()

        # 5. 取得所有候選品的屬性（批次查）
        candidate_pids = list({str(c["product_id"]) for c in candidates})
        candidate_attrs: dict[str, dict[str, str]] = {pid: {} for pid in candidate_pids}

        if candidate_pids:
            placeholders = ", ".join(f":pid_{i}" for i in range(len(candidate_pids)))
            attrs_sql = text(f"""
                SELECT product_id, attr_key, attr_value
                FROM product_attributes
                WHERE product_id IN ({placeholders})
            """)
            params = {f"pid_{i}": pid for i, pid in enumerate(candidate_pids)}
            for r in self._session.execute(attrs_sql, params).mappings().all():
                candidate_attrs[str(r["product_id"])][r["attr_key"]] = r["attr_value"]

        # 6. 計算匹配分數
        must_keys = [t["attr_key"] for t in templates if t["match_type"] == "must"]
        prefer_templates = [t for t in templates if t["match_type"] == "prefer"]
        optional_templates = [t for t in templates if t["match_type"] == "optional"]

        scored = []
        for c in candidates:
            pid = str(c["product_id"])
            c_attrs = dict(candidate_attrs.get(pid, {}))
            # 品牌也加入比對
            if c["brand"]:
                c_attrs["品牌"] = c["brand"]

            # must 檢查：任一不符就排除
            must_fail = False
            for key in must_keys:
                target_val = target_attrs.get(key)
                cand_val = c_attrs.get(key)
                if target_val and cand_val and target_val != cand_val:
                    must_fail = True
                    break
            if must_fail:
                continue

            # prefer + optional 計分
            score = 0
            matched = []
            mismatched = []

            for t in prefer_templates:
                key = t["attr_key"]
                target_val = target_attrs.get(key)
                cand_val = c_attrs.get(key)
                weight = max(1, 20 - (t["match_priority"] or 10))
                if target_val and cand_val:
                    if target_val == cand_val:
                        score += weight
                        matched.append(key)
                    else:
                        mismatched.append(f"{key}:{cand_val}")

            for t in optional_templates:
                key = t["attr_key"]
                target_val = target_attrs.get(key)
                cand_val = c_attrs.get(key)
                if target_val and cand_val and target_val == cand_val:
                    score += 1
                    matched.append(key)
                elif target_val and cand_val and target_val != cand_val:
                    mismatched.append(f"{key}:{cand_val}")

            # 庫存充足加分
            if c["min_stock"] and c["current_stock"] > c["min_stock"]:
                score += 5

            scored.append({
                "sku_id": str(c["sku_id"]),
                "product_id": pid,
                "name": c["name"],
                "brand": c["brand"],
                "spec": c["spec"],
                "unit": c["unit"],
                "sell_price": float(c["sell_price"]),
                "cost_price": float(c["cost_price"]) if c["cost_price"] else None,
                "current_stock": int(c["current_stock"]),
                "score": score,
                "matched": matched,
                "mismatched": mismatched,
            })

        # 排序：分數高→低，庫存高→低
        scored.sort(key=lambda x: (-x["score"], -x["current_stock"]))

        return {
            "target": {
                "sku_id": str(target["sku_id"]),
                "name": target["name"],
                "brand": target["brand"],
                "spec": target["spec"],
                "current_stock": int(target["current_stock"]),
                "attributes": target_attrs,
            },
            "templates": [
                {"key": t["attr_key"], "priority": t["match_priority"], "type": t["match_type"]}
                for t in templates
            ],
            "alternatives": scored[:limit],
        }

    # ── 別名查詢 ────────────────────────────────────
    def list_aliases_by_product(self, product_id: str) -> list[dict]:
        sql = text("""
            SELECT alias_id, product_id, alias, alias_type
            FROM product_aliases
            WHERE product_id = :pid
            ORDER BY alias
        """)
        rows = self._session.execute(sql, {"pid": product_id}).mappings().all()
        return [dict(r) for r in rows]

    # ── 供應商列表 ──────────────────────────────────
    def list_active_suppliers(self) -> list[dict]:
        sql = text("""
            SELECT supplier_id, name, contact_name, phone
            FROM suppliers
            WHERE is_active = true
            ORDER BY name
        """)
        rows = self._session.execute(sql).mappings().all()
        return [dict(r) for r in rows]

    # ── BOM 查詢 ────────────────────────────────────
    def get_bom_children(self, parent_sku_id: str) -> list[dict]:
        """成品的組成件列表（含零件庫存，單一 SQL 不做 N+1）。"""
        sql = text("""
            SELECT b.bom_id, b.child_sku_id, b.quantity, b.component_role, b.sort_order, b.note,
                   p.name as product_name, s.brand, s.spec, s.unit, s.item_type,
                   COALESCE(ib.current_stock, 0) as current_stock
            FROM product_bom b
            JOIN skus s ON s.sku_id = b.child_sku_id
            JOIN products p ON p.product_id = s.product_id
            LEFT JOIN inventory_balances ib ON ib.sku_id = s.sku_id
            WHERE b.parent_sku_id = :pid
            ORDER BY b.sort_order, p.name
        """)
        rows = self._session.execute(sql, {"pid": parent_sku_id}).mappings().all()
        return [dict(r) for r in rows]

    def get_bom_parents(self, child_sku_id: str) -> list[dict]:
        """零件被哪些成品使用。"""
        sql = text("""
            SELECT b.bom_id, b.parent_sku_id, b.quantity, b.component_role,
                   p.name as product_name, s.brand, s.spec
            FROM product_bom b
            JOIN skus s ON s.sku_id = b.parent_sku_id
            JOIN products p ON p.product_id = s.product_id
            WHERE b.child_sku_id = :cid
            ORDER BY p.name
        """)
        rows = self._session.execute(sql, {"cid": child_sku_id}).mappings().all()
        return [dict(r) for r in rows]

    def get_assembly_hint(self, parent_sku_id: str) -> dict | None:
        """提示型判斷：零件庫存是否足夠組裝（不是可承諾供貨）。"""
        children = self.get_bom_children(parent_sku_id)
        if not children:
            return None
        can_assemble = all(c["current_stock"] >= c["quantity"] for c in children)
        return {
            "can_assemble": can_assemble,
            "children": [
                {
                    "product_name": c["product_name"],
                    "brand": c["brand"],
                    "spec": c["spec"],
                    "role": c["component_role"],
                    "need": c["quantity"],
                    "stock": c["current_stock"],
                    "enough": c["current_stock"] >= c["quantity"],
                }
                for c in children
            ],
        }

    def has_bom_children(self, sku_id: str) -> bool:
        result = self._session.execute(
            text("SELECT 1 FROM product_bom WHERE parent_sku_id = :sid LIMIT 1"),
            {"sid": sku_id},
        ).scalar()
        return result is not None

    def is_bom_child(self, sku_id: str) -> bool:
        result = self._session.execute(
            text("SELECT 1 FROM product_bom WHERE child_sku_id = :sid LIMIT 1"),
            {"sid": sku_id},
        ).scalar()
        return result is not None

    def count_category_children(self, category_id: str) -> int:
        return self._session.execute(
            text("SELECT COUNT(*) FROM categories WHERE parent_id = :cid"),
            {"cid": category_id},
        ).scalar() or 0

    def count_category_products(self, category_id: str) -> int:
        return self._session.execute(
            text("SELECT COUNT(*) FROM products WHERE category_id = :cid AND is_active = true"),
            {"cid": category_id},
        ).scalar() or 0

    def get_all_descendant_ids(self, category_id: str) -> list[str]:
        """遞迴取得所有子孫分類 ID（含自己）。"""
        sql = text("""
            WITH RECURSIVE tree AS (
                SELECT category_id FROM categories WHERE category_id = :cid
                UNION ALL
                SELECT c.category_id FROM categories c JOIN tree t ON c.parent_id = t.category_id
            )
            SELECT category_id FROM tree
        """)
        rows = self._session.execute(sql, {"cid": category_id}).all()
        return [str(r[0]) for r in rows]

    def count_products_in_categories(self, category_ids: list[str]) -> int:
        if not category_ids:
            return 0
        placeholders = ", ".join(f"'{cid}'" for cid in category_ids)
        sql = text(f"SELECT COUNT(*) FROM products WHERE category_id IN ({placeholders}) AND is_active = true")
        return self._session.execute(sql).scalar() or 0

