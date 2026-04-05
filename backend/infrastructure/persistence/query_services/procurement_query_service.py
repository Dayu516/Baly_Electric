"""採購域查詢服務。"""

from sqlalchemy import text

from .base import BaseQueryService


class ProcurementQueryService(BaseQueryService):

    # ── 採購單查詢 ───────────────────────────────────
    def list_purchase_orders(
        self, *, status: str | None = None, supplier_id: str | None = None,
        keyword: str | None = None, date_from: str | None = None, date_to: str | None = None,
        offset: int = 0, limit: int = 20,
    ) -> list[dict]:
        where = ["1=1"]
        params: dict = {"offset": offset, "limit": limit}
        if status:
            where.append("po.status = :status")
            params["status"] = status
        if supplier_id:
            where.append("po.supplier_id = :sup_id")
            params["sup_id"] = supplier_id
        if keyword:
            where.append("(sup.name ILIKE :kw OR po.note ILIKE :kw)")
            params["kw"] = f"%{keyword}%"
        if date_from:
            where.append("po.created_at >= :dfrom")
            params["dfrom"] = date_from
        if date_to:
            where.append("po.created_at < :dto::date + 1")
            params["dto"] = date_to

        sql = text(f"""
            SELECT po.po_id, po.supplier_id, po.status, po.note, po.ordered_at, po.created_at,
                   sup.name as supplier_name,
                   COUNT(pol.po_line_id) as line_count,
                   COALESCE(SUM(pol.ordered_quantity * COALESCE(pol.unit_cost, 0)), 0) as total_amount
            FROM purchase_orders po
            JOIN suppliers sup ON sup.supplier_id = po.supplier_id
            LEFT JOIN purchase_order_lines pol ON pol.po_id = po.po_id
            WHERE {" AND ".join(where)}
            GROUP BY po.po_id, sup.name
            ORDER BY po.created_at DESC
            OFFSET :offset LIMIT :limit
        """)
        rows = self._session.execute(sql, params).mappings().all()
        return [dict(r) for r in rows]

    def get_purchase_order_detail(self, po_id: str) -> dict | None:
        sql = text("""
            SELECT po.po_id, po.supplier_id, po.status, po.note, po.ordered_at, po.created_at,
                   sup.name as supplier_name
            FROM purchase_orders po
            JOIN suppliers sup ON sup.supplier_id = po.supplier_id
            WHERE po.po_id = :po_id
        """)
        row = self._session.execute(sql, {"po_id": po_id}).mappings().first()
        return dict(row) if row else None

    def delete_purchase_order_lines(self, po_id: str) -> None:
        self._session.execute(
            text("DELETE FROM purchase_order_lines WHERE po_id = :po_id"),
            {"po_id": po_id},
        )

    def get_purchase_order_lines(self, po_id: str) -> list[dict]:
        sql = text("""
            SELECT pol.po_line_id, pol.sku_id, pol.ordered_quantity, pol.received_quantity, pol.unit_cost,
                   pol.source_type, pol.source_customer_id, pol.source_sale_id, pol.source_sale_line_id,
                   pol.reserved_qty, pol.allocated_qty,
                   p.name as product_name, s.brand, s.spec, s.unit
            FROM purchase_order_lines pol
            JOIN skus s ON s.sku_id = pol.sku_id
            JOIN products p ON p.product_id = s.product_id
            WHERE pol.po_id = :po_id
        """)
        rows = self._session.execute(sql, {"po_id": po_id}).mappings().all()
        return [dict(r) for r in rows]

    def get_po_line_quantities(self, po_id: str) -> list[dict]:
        sql = text("""
            SELECT ordered_quantity, received_quantity
            FROM purchase_order_lines WHERE po_id = :po_id
        """)
        rows = self._session.execute(sql, {"po_id": po_id}).mappings().all()
        return [dict(r) for r in rows]

    # ── 詢價單查詢 ───────────────────────────────────
    def list_inquiries(self, *, status: str | None = None, keyword: str | None = None,
                         date_from: str | None = None, date_to: str | None = None,
                         offset: int = 0, limit: int = 20) -> list[dict]:
        conditions = ["1=1"]
        params: dict = {"offset": offset, "limit": limit}
        if status:
            conditions.append("i.status = :status")
            params["status"] = status
        if keyword:
            conditions.append("(i.title ILIKE :kw OR i.note ILIKE :kw)")
            params["kw"] = f"%{keyword}%"
        if date_from:
            conditions.append("i.created_at >= :dfrom")
            params["dfrom"] = date_from
        if date_to:
            conditions.append("i.created_at < :dto::date + 1")
            params["dto"] = date_to
        where = " AND ".join(conditions)

        sql = text(f"""
            SELECT i.inquiry_id, i.title, i.status, i.note, i.created_at,
                   COUNT(DISTINCT il.line_id) as line_count,
                   COUNT(DISTINCT iq.quote_id) as quote_count
            FROM purchase_inquiries i
            LEFT JOIN purchase_inquiry_lines il ON il.inquiry_id = i.inquiry_id
            LEFT JOIN purchase_inquiry_quotes iq ON iq.inquiry_id = i.inquiry_id
            WHERE {where}
            GROUP BY i.inquiry_id
            ORDER BY i.created_at DESC
            OFFSET :offset LIMIT :limit
        """)
        rows = self._session.execute(sql, params).mappings().all()
        return [dict(r) for r in rows]

    def get_inquiry_lines(self, inquiry_id: str) -> list[dict]:
        sql = text("""
            SELECT il.line_id, il.sku_id, il.quantity, il.note,
                   p.name as product_name, s.brand, s.spec, s.unit
            FROM purchase_inquiry_lines il
            JOIN skus s ON s.sku_id = il.sku_id
            JOIN products p ON p.product_id = s.product_id
            WHERE il.inquiry_id = :iid
        """)
        rows = self._session.execute(sql, {"iid": inquiry_id}).mappings().all()
        return [dict(r) for r in rows]

    def get_inquiry_quotes(self, inquiry_id: str) -> list[dict]:
        sql = text("""
            SELECT iq.quote_id, iq.line_id, iq.supplier_id, iq.unit_price, iq.note, iq.is_selected,
                   sup.name as supplier_name
            FROM purchase_inquiry_quotes iq
            JOIN suppliers sup ON sup.supplier_id = iq.supplier_id
            WHERE iq.inquiry_id = :iid
            ORDER BY iq.line_id, iq.unit_price ASC
        """)
        rows = self._session.execute(sql, {"iid": inquiry_id}).mappings().all()
        return [dict(r) for r in rows]

    def get_selected_inquiry_quotes(self, inquiry_id: str) -> list[dict]:
        sql = text("""
            SELECT iq.supplier_id, iq.unit_price, il.sku_id, il.quantity
            FROM purchase_inquiry_quotes iq
            JOIN purchase_inquiry_lines il ON il.line_id = iq.line_id
            WHERE iq.inquiry_id = :iid AND iq.is_selected = true
        """)
        rows = self._session.execute(sql, {"iid": inquiry_id}).mappings().all()
        return [dict(r) for r in rows]

    def deselect_all_inquiry_quotes(self, inquiry_id: str) -> None:
        self._session.execute(
            text("UPDATE purchase_inquiry_quotes SET is_selected = false WHERE inquiry_id = :iid"),
            {"iid": inquiry_id},
        )

    def select_inquiry_quote(self, quote_id: str, inquiry_id: str) -> None:
        self._session.execute(
            text("UPDATE purchase_inquiry_quotes SET is_selected = true WHERE quote_id = :qid AND inquiry_id = :iid"),
            {"qid": quote_id, "iid": inquiry_id},
        )

    # ── 報價單查詢 ───────────────────────────────────
    def list_quotations(self, *, status: str | None = None, keyword: str | None = None,
                          date_from: str | None = None, date_to: str | None = None,
                          offset: int = 0, limit: int = 20) -> list[dict]:
        conditions = ["1=1"]
        params: dict = {"offset": offset, "limit": limit}
        if status:
            conditions.append("q.status = :status")
            params["status"] = status
        if keyword:
            conditions.append("(c.name ILIKE :kw OR q.title ILIKE :kw OR q.note ILIKE :kw)")
            params["kw"] = f"%{keyword}%"
        if date_from:
            conditions.append("q.created_at >= :dfrom")
            params["dfrom"] = date_from
        if date_to:
            conditions.append("q.created_at < :dto::date + 1")
            params["dto"] = date_to
        where = " AND ".join(conditions)

        sql = text(f"""
            SELECT q.quotation_id, q.customer_id, q.title, q.status, q.valid_until, q.note, q.created_at,
                   c.name as customer_name,
                   COUNT(ql.line_id) as line_count,
                   COALESCE(SUM(ql.quantity * ql.unit_price), 0) as total_amount
            FROM sales_quotations q
            LEFT JOIN customers c ON c.customer_id = q.customer_id
            LEFT JOIN sales_quotation_lines ql ON ql.quotation_id = q.quotation_id
            WHERE {where}
            GROUP BY q.quotation_id, c.name
            ORDER BY q.created_at DESC
            OFFSET :offset LIMIT :limit
        """)
        rows = self._session.execute(sql, params).mappings().all()
        return [dict(r) for r in rows]

    def get_quotation_detail(self, quotation_id: str) -> dict | None:
        sql = text("""
            SELECT q.quotation_id, q.customer_id, q.title, q.status, q.valid_until, q.note, q.created_at,
                   c.name as customer_name
            FROM sales_quotations q
            LEFT JOIN customers c ON c.customer_id = q.customer_id
            WHERE q.quotation_id = :qid
        """)
        row = self._session.execute(sql, {"qid": quotation_id}).mappings().first()
        return dict(row) if row else None

    def get_quotation_lines(self, quotation_id: str) -> list[dict]:
        sql = text("""
            SELECT ql.line_id, ql.sku_id, ql.quantity, ql.unit_price, ql.note,
                   p.name as product_name, s.brand, s.spec, s.unit
            FROM sales_quotation_lines ql
            JOIN skus s ON s.sku_id = ql.sku_id
            JOIN products p ON p.product_id = s.product_id
            WHERE ql.quotation_id = :qid
        """)
        rows = self._session.execute(sql, {"qid": quotation_id}).mappings().all()
        return [dict(r) for r in rows]

    def get_quotation_lines_for_convert(self, quotation_id: str) -> list[dict]:
        """取得報價明細行 + SKU 快照欄位，用於轉銷貨。"""
        sql = text("""
            SELECT ql.sku_id, ql.quantity, ql.unit_price,
                   p.name as product_name, s.spec
            FROM sales_quotation_lines ql
            JOIN skus s ON s.sku_id = ql.sku_id
            JOIN products p ON p.product_id = s.product_id
            WHERE ql.quotation_id = :qid
        """)
        rows = self._session.execute(sql, {"qid": quotation_id}).mappings().all()
        return [dict(r) for r in rows]

    def get_supplier_product_cost(self, supplier_id: str, sku_id: str) -> float | None:
        """查詢 supplier_products 的既有 unit_cost。"""
        row = self._session.execute(
            text("SELECT unit_cost FROM supplier_products WHERE supplier_id = :sid AND sku_id = :skid"),
            {"sid": supplier_id, "skid": sku_id},
        ).mappings().first()
        return float(row["unit_cost"]) if row and row["unit_cost"] else None

    # ── 供應商報價查詢 ─────────────────────────────────
    def update_supplier_product_cost(self, supplier_id: str, sku_id: str, price: float) -> None:
        self._session.execute(
            text("""
                UPDATE supplier_products
                SET unit_cost = :price, updated_at = NOW()
                WHERE supplier_id = :sup_id AND sku_id = :sku_id
            """),
            {"price": price, "sup_id": supplier_id, "sku_id": sku_id},
        )

    def list_supplier_price_quotes(self, product_id: str, supplier_id: str | None = None) -> list[dict]:
        params: dict = {"pid": product_id}
        where_supplier = ""
        if supplier_id:
            where_supplier = "AND q.supplier_id = :sup_id"
            params["sup_id"] = supplier_id

        sql = text(f"""
            SELECT q.quote_id, q.supplier_id, q.sku_id, q.unit_price, q.unit,
                   q.quoted_at, q.note,
                   sup.name as supplier_name,
                   s.spec as sku_spec
            FROM supplier_price_quotes q
            JOIN suppliers sup ON sup.supplier_id = q.supplier_id
            JOIN skus s ON s.sku_id = q.sku_id
            WHERE s.product_id = :pid {where_supplier}
            ORDER BY q.quoted_at DESC, sup.name
            LIMIT 100
        """)
        rows = self._session.execute(sql, params).mappings().all()
        return [dict(r) for r in rows]

    def compare_supplier_prices(self, product_id: str) -> list[dict]:
        sql = text("""
            WITH latest AS (
                SELECT q.supplier_id, q.sku_id, q.unit_price, q.unit, q.quoted_at, q.note,
                       ROW_NUMBER() OVER (
                           PARTITION BY q.supplier_id, q.sku_id
                           ORDER BY q.quoted_at DESC
                       ) as rn
                FROM supplier_price_quotes q
                JOIN skus s ON s.sku_id = q.sku_id
                WHERE s.product_id = :pid
            )
            SELECT l.supplier_id, l.sku_id, l.unit_price, l.unit, l.quoted_at, l.note,
                   sup.name as supplier_name, sup.phone as supplier_phone,
                   s.spec as sku_spec,
                   sp.is_preferred
            FROM latest l
            JOIN suppliers sup ON sup.supplier_id = l.supplier_id
            JOIN skus s ON s.sku_id = l.sku_id
            LEFT JOIN supplier_products sp ON sp.supplier_id = l.supplier_id AND sp.sku_id = l.sku_id
            WHERE l.rn = 1 AND sup.is_active = true
            ORDER BY l.unit_price ASC
        """)
        rows = self._session.execute(sql, {"pid": product_id}).mappings().all()
        return [dict(r) for r in rows]

    def low_stock_with_preferred_supplier(self) -> list[dict]:
        """低庫存品項 + 首選供應商，用於一鍵建採購單。"""
        sql = text("""
            SELECT s.sku_id, p.name as product_name, s.brand, s.spec, s.unit,
                   ib.current_stock, s.min_stock,
                   s.min_stock - ib.current_stock as shortage,
                   sp.supplier_id, sup.name as supplier_name,
                   sp.unit_cost
            FROM inventory_balances ib
            JOIN skus s ON s.sku_id = ib.sku_id AND s.is_active = true
            JOIN products p ON p.product_id = s.product_id AND p.is_active = true
            JOIN supplier_products sp ON sp.sku_id = s.sku_id AND sp.is_preferred = true
            JOIN suppliers sup ON sup.supplier_id = sp.supplier_id AND sup.is_active = true
            WHERE s.min_stock IS NOT NULL
              AND s.min_stock > 0
              AND ib.current_stock <= s.min_stock
            ORDER BY sup.name, p.name
        """)
        rows = self._session.execute(sql).mappings().all()
        return [dict(r) for r in rows]

    # ── 報表查詢 ──────────────────────────────────────
    def supplier_monthly_stats(self, period: str) -> list[dict]:
        sql = text("""
            SELECT sup.supplier_id, sup.name as supplier_name, sup.phone,
                   COUNT(DISTINCT pr.receipt_id) as receipt_count,
                   SUM(prl.quantity) as total_quantity,
                   SUM(prl.quantity * COALESCE(prl.unit_cost, 0)) as total_amount
            FROM purchase_receipt_lines prl
            JOIN purchase_receipts pr ON pr.receipt_id = prl.receipt_id
            JOIN suppliers sup ON sup.supplier_id = pr.supplier_id
            WHERE TO_CHAR(pr.created_at, 'YYYY-MM') = :period
            GROUP BY sup.supplier_id, sup.name, sup.phone
            ORDER BY total_amount DESC
        """)
        rows = self._session.execute(sql, {"period": period}).mappings().all()
        return [dict(r) for r in rows]

    # ── 供應商歷史交易 ─────────────────────────────
    def supplier_transaction_history(self, supplier_id: str, limit: int = 50) -> list[dict]:
        """某供應商的進貨驗收歷史（按日期倒序）。"""
        sql = text("""
            SELECT pr.receipt_id, pr.created_at,
                   po.po_id, po.note as po_note,
                   COUNT(prl.receipt_line_id) as line_count,
                   SUM(prl.quantity) as total_quantity,
                   SUM(prl.quantity * COALESCE(prl.unit_cost, 0)) as total_amount
            FROM purchase_receipts pr
            LEFT JOIN purchase_orders po ON po.po_id = pr.po_id
            JOIN purchase_receipt_lines prl ON prl.receipt_id = pr.receipt_id
            WHERE pr.supplier_id = :sid
            GROUP BY pr.receipt_id, po.po_id, po.note
            ORDER BY pr.created_at DESC
            LIMIT :limit
        """)
        rows = self._session.execute(sql, {"sid": supplier_id, "limit": limit}).mappings().all()
        return [dict(r) for r in rows]

    def supplier_summary(self, supplier_id: str) -> dict:
        """某供應商的交易摘要。"""
        sql = text("""
            SELECT COUNT(DISTINCT pr.receipt_id) as total_receipts,
                   COALESCE(SUM(prl.quantity), 0) as total_quantity,
                   COALESCE(SUM(prl.quantity * COALESCE(prl.unit_cost, 0)), 0) as total_amount,
                   MAX(pr.created_at) as last_receipt_date
            FROM purchase_receipts pr
            JOIN purchase_receipt_lines prl ON prl.receipt_id = pr.receipt_id
            WHERE pr.supplier_id = :sid
        """)
        row = self._session.execute(sql, {"sid": supplier_id}).mappings().first()
        return dict(row) if row else {}

    # ── 刪除 ────────────────────────────────────────────
    def delete_inquiry(self, inquiry_id: str) -> None:
        self._session.execute(text("DELETE FROM purchase_inquiry_quotes WHERE inquiry_id = :iid"), {"iid": inquiry_id})
        self._session.execute(text("DELETE FROM purchase_inquiry_lines WHERE inquiry_id = :iid"), {"iid": inquiry_id})
        self._session.execute(text("DELETE FROM purchase_inquiries WHERE inquiry_id = :iid"), {"iid": inquiry_id})

    def delete_quotation(self, quotation_id: str) -> None:
        self._session.execute(text("DELETE FROM sales_quotation_lines WHERE quotation_id = :qid"), {"qid": quotation_id})
        self._session.execute(text("DELETE FROM sales_quotations WHERE quotation_id = :qid"), {"qid": quotation_id})

    def get_inquiry_detail(self, inquiry_id: str) -> dict | None:
        sql = text("""
            SELECT inquiry_id, title, status, note, created_at
            FROM purchase_inquiries WHERE inquiry_id = :iid
        """)
        row = self._session.execute(sql, {"iid": inquiry_id}).mappings().first()
        return dict(row) if row else None
