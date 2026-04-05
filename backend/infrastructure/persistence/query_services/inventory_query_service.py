"""庫存域查詢服務。"""

from sqlalchemy import text

from .base import BaseQueryService


class InventoryQueryService(BaseQueryService):

    # ── 庫存重算 ─────────────────────────────────────
    def recalc_inventory_balance(self, sku_id: str) -> int:
        """以 SUM(stock_movements.quantity) 重算庫存。回傳正確數字。"""
        sql = text("""
            SELECT COALESCE(SUM(quantity), 0) as total
            FROM stock_movements
            WHERE sku_id = :sku_id
        """)
        result = self._session.execute(sql, {"sku_id": sku_id}).scalar()
        return int(result or 0)

    # ── 庫存總覽 ────────────────────────────────────
    def list_inventory(
        self, *, keyword: str | None = None, low_stock_only: bool = False,
        offset: int = 0, limit: int = 50,
    ) -> tuple[list[dict], int]:
        where = ["s.is_active = true", "p.is_active = true"]
        params: dict = {"offset": offset, "limit": limit}

        if keyword:
            where.append("""(
                p.name ILIKE :kw OR s.brand ILIKE :kw OR s.spec ILIKE :kw
                OR s.barcode = :exact_kw OR s.supplier_code = :exact_kw
            )""")
            params["kw"] = f"%{keyword}%"
            params["exact_kw"] = keyword

        if low_stock_only:
            where.append("s.min_stock IS NOT NULL AND s.min_stock > 0 AND ib.current_stock <= s.min_stock")

        where_clause = " AND ".join(where)

        sql = text(f"""
            SELECT ib.sku_id, ib.current_stock, ib.last_recalc_at,
                   s.barcode, s.spec, s.unit, s.sell_price, s.cost_price, s.min_stock, s.brand, s.item_type,
                   p.name as product_name, p.category_id
            FROM inventory_balances ib
            JOIN skus s ON s.sku_id = ib.sku_id
            JOIN products p ON p.product_id = s.product_id
            WHERE {where_clause}
            ORDER BY p.name, s.spec
            OFFSET :offset LIMIT :limit
        """)
        rows = self._session.execute(sql, params).mappings().all()

        count_sql = text(f"""
            SELECT COUNT(*)
            FROM inventory_balances ib
            JOIN skus s ON s.sku_id = ib.sku_id
            JOIN products p ON p.product_id = s.product_id
            WHERE {where_clause}
        """)
        total = self._session.execute(count_sql, params).scalar() or 0

        return [dict(r) for r in rows], int(total)

    def inventory_summary(self) -> dict:
        row = self._session.execute(text("""
            SELECT COUNT(*) as total_items,
                   COALESCE(SUM(ib.current_stock * COALESCE(s.cost_price, 0)), 0) as total_value,
                   COUNT(*) FILTER (
                       WHERE s.min_stock IS NOT NULL AND s.min_stock > 0 AND ib.current_stock <= s.min_stock
                   ) as low_stock_count,
                   COUNT(*) FILTER (WHERE ib.current_stock <= 0) as zero_stock_count
            FROM inventory_balances ib
            JOIN skus s ON s.sku_id = ib.sku_id AND s.is_active = true
            JOIN products p ON p.product_id = s.product_id AND p.is_active = true
        """)).mappings().first()
        return dict(row) if row else {}

    def all_inventory_sku_ids(self) -> list:
        return list(self._session.execute(
            text("SELECT sku_id FROM inventory_balances")
        ).scalars().all())
