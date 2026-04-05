"""銷售域查詢服務。"""

from sqlalchemy import text

from .base import BaseQueryService


class SalesQueryService(BaseQueryService):

    # ── 客戶歷史售價查詢 ──────────────────────────────
    def get_customer_prices(self, customer_id: str, sku_ids: list[str]) -> dict[str, dict]:
        """查詢某客戶對多個 SKU 的歷史售價。回傳 {sku_id: {last_price, last_cost, last_sold_at}}。"""
        if not sku_ids:
            return {}
        placeholders = ", ".join(f":sku_{i}" for i in range(len(sku_ids)))
        sql = text(f"""
            SELECT sku_id, last_price, last_cost, last_sold_at
            FROM customer_price_history
            WHERE customer_id = :customer_id AND sku_id IN ({placeholders})
        """)
        params = {"customer_id": customer_id}
        for i, sid in enumerate(sku_ids):
            params[f"sku_{i}"] = sid
        rows = self._session.execute(sql, params).mappings().all()
        return {
            str(r["sku_id"]): {
                "last_price": float(r["last_price"]) if r["last_price"] else None,
                "last_cost": float(r["last_cost"]) if r["last_cost"] else None,
                "last_sold_at": str(r["last_sold_at"]) if r["last_sold_at"] else None,
            }
            for r in rows
        }

    # ── 銷售紀錄查詢 ─────────────────────────────────
    def list_sales_history(
        self, *, customer_id: str | None = None, period: str | None = None,
        keyword: str | None = None, date_from: str | None = None, date_to: str | None = None,
        offset: int = 0, limit: int = 20,
    ) -> tuple[list[dict], int]:
        where = ["1=1"]
        params: dict = {"offset": offset, "limit": limit}
        if customer_id:
            where.append("s.customer_id = :cid")
            params["cid"] = customer_id
        if period:
            where.append("TO_CHAR(s.created_at, 'YYYY-MM') = :period")
            params["period"] = period
        if keyword:
            where.append("(c.name ILIKE :kw OR s.note ILIKE :kw)")
            params["kw"] = f"%{keyword}%"
        if date_from:
            where.append("s.created_at >= :dfrom")
            params["dfrom"] = date_from
        if date_to:
            where.append("s.created_at < :dto::date + 1")
            params["dto"] = date_to

        where_clause = " AND ".join(where)

        sql = text(f"""
            SELECT s.sale_id, s.customer_id, s.status, s.payment_method,
                   s.tax_included, s.subtotal, s.tax_amount, s.total,
                   s.note, s.created_at,
                   c.name as customer_name,
                   COUNT(sl.sale_line_id) as line_count
            FROM sales s
            LEFT JOIN customers c ON c.customer_id = s.customer_id
            LEFT JOIN sale_lines sl ON sl.sale_id = s.sale_id
            WHERE {where_clause}
            GROUP BY s.sale_id, c.name
            ORDER BY s.created_at DESC
            OFFSET :offset LIMIT :limit
        """)
        rows = self._session.execute(sql, params).mappings().all()

        count_sql = text(f"SELECT COUNT(*) FROM sales s WHERE {where_clause}")
        total = self._session.execute(count_sql, params).scalar() or 0

        return [dict(r) for r in rows], int(total)

    def get_sale_detail(self, sale_id: str) -> dict | None:
        sql = text("""
            SELECT s.sale_id, s.customer_id, s.status, s.payment_method,
                   s.tax_included, s.subtotal, s.tax_amount, s.total, s.discount_amount,
                   s.note, s.created_at,
                   c.name as customer_name
            FROM sales s
            LEFT JOIN customers c ON c.customer_id = s.customer_id
            WHERE s.sale_id = :sid
        """)
        row = self._session.execute(sql, {"sid": sale_id}).mappings().first()
        return dict(row) if row else None

    def get_sale_lines(self, sale_id: str) -> list[dict]:
        sql = text("""
            SELECT sl.product_name, sl.spec, sl.quantity, sl.unit_price, sl.line_total
            FROM sale_lines sl
            WHERE sl.sale_id = :sid
        """)
        rows = self._session.execute(sql, {"sid": sale_id}).mappings().all()
        return [dict(r) for r in rows]

    # ── 月結彙整 ─────────────────────────────────────
    def sum_customer_sales(self, customer_id: str, period: str) -> float:
        """彙總某客戶某月份的銷售總額。period 格式：YYYY-MM。"""
        sql = text("""
            SELECT COALESCE(SUM(s.total), 0) as total
            FROM sales s
            WHERE s.customer_id = :customer_id
              AND s.status = 'completed'
              AND TO_CHAR(s.created_at, 'YYYY-MM') = :period
        """)
        result = self._session.execute(
            sql, {"customer_id": customer_id, "period": period}
        ).scalar()
        return float(result or 0)

    # ── 應收帳款 ────────────────────────────────────
    def list_accounts_receivable(self, customer_id: str) -> list[dict]:
        sql = text("""
            SELECT ar_id, customer_id, period, total_amount, paid_amount, status, due_date, paid_at, note, created_at
            FROM accounts_receivables
            WHERE customer_id = :customer_id
            ORDER BY period DESC
        """)
        rows = self._session.execute(sql, {"customer_id": customer_id}).mappings().all()
        return [dict(r) for r in rows]

    # ── 出貨單查詢 ──────────────────────────────────
    def get_receipt_sale(self, sale_id: str) -> dict | None:
        sql = text("""
            SELECT s.sale_id, s.customer_id, s.cashier_id, s.status, s.payment_method,
                   s.tax_included, s.subtotal, s.tax_amount, s.discount_amount, s.total,
                   s.note, s.created_at,
                   u.display_name as cashier_name
            FROM sales s
            LEFT JOIN users u ON u.user_id = s.cashier_id
            WHERE s.sale_id = :sale_id
        """)
        row = self._session.execute(sql, {"sale_id": sale_id}).mappings().first()
        return dict(row) if row else None

    def get_receipt_lines(self, sale_id: str) -> list[dict]:
        sql = text("""
            SELECT sl.product_name, sl.spec, sl.quantity, sl.unit_price,
                   sl.discount_amount, sl.line_total
            FROM sale_lines sl
            WHERE sl.sale_id = :sale_id
            ORDER BY sl.product_name
        """)
        rows = self._session.execute(sql, {"sale_id": sale_id}).mappings().all()
        return [dict(r) for r in rows]

    def get_customer_info(self, customer_id: str) -> dict | None:
        sql = text("""
            SELECT c.name, c.phone, c.address, c.payment_terms
            FROM customers c WHERE c.customer_id = :cid
        """)
        row = self._session.execute(sql, {"cid": customer_id}).mappings().first()
        return dict(row) if row else None

