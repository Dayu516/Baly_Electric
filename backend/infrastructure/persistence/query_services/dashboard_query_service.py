"""Dashboard 查詢服務。"""

from sqlalchemy import text

from .base import BaseQueryService


class DashboardQueryService(BaseQueryService):

    # ── Dashboard 彙整 ──────────────────────────────
    def dashboard_stats(self) -> dict:
        """首頁 Dashboard 一次撈齊所有摘要數據。"""
        # 今日銷售
        today_sales = self._session.execute(text("""
            SELECT COUNT(*) as count, COALESCE(SUM(total), 0) as total
            FROM sales
            WHERE status = 'completed'
              AND created_at::date = CURRENT_DATE
        """)).mappings().first()

        # 本月銷售
        month_sales = self._session.execute(text("""
            SELECT COUNT(*) as count, COALESCE(SUM(total), 0) as total
            FROM sales
            WHERE status = 'completed'
              AND TO_CHAR(created_at, 'YYYY-MM') = TO_CHAR(NOW(), 'YYYY-MM')
        """)).mappings().first()

        # 低庫存品項
        low_stock = self._session.execute(text("""
            SELECT COUNT(*) as count FROM (
                SELECT ib.sku_id
                FROM inventory_balances ib
                JOIN skus s ON s.sku_id = ib.sku_id AND s.is_active = true
                WHERE s.min_stock IS NOT NULL
                  AND s.min_stock > 0
                  AND ib.current_stock <= s.min_stock
            ) sub
        """)).scalar() or 0

        # 待審核任務
        pending_reviews = self._session.execute(text("""
            SELECT COUNT(*) FROM review_tasks WHERE status = 'pending'
        """)).scalar() or 0

        # 未讀警示
        unread_alerts = self._session.execute(text("""
            SELECT COUNT(*) FROM operational_alerts WHERE is_read = false
        """)).scalar() or 0

        # 待處理採購單（draft + ordered）
        active_pos = self._session.execute(text("""
            SELECT COUNT(*) FROM purchase_orders WHERE status IN ('draft', 'ordered', 'partial_received')
        """)).scalar() or 0

        # 應收帳款未收
        ar_outstanding = self._session.execute(text("""
            SELECT COALESCE(SUM(total_amount - paid_amount), 0)
            FROM accounts_receivables
            WHERE status IN ('open', 'partial_paid', 'overdue')
        """)).scalar() or 0

        # 欠貨待補統計
        backorder = self._session.execute(text("""
            SELECT
                COUNT(DISTINCT sale_id) FILTER (WHERE backorder_status = 'pending') AS needs_po,
                COUNT(DISTINCT sale_id) FILTER (WHERE backorder_status = 'ordered') AS awaiting_arrival,
                COUNT(DISTINCT sale_id) FILTER (WHERE backorder_status IN ('arrived', 'partial_arrived')) AS ready_pickup,
                COUNT(DISTINCT sale_id) FILTER (WHERE backorder_qty > backorder_delivered_qty AND backorder_qty > 0) AS total_active
            FROM sale_lines
            WHERE backorder_qty > 0
              AND COALESCE(backorder_status, '') != 'cancelled'
        """)).mappings().first()

        return {
            "today_sales_count": int(today_sales["count"]),
            "today_sales_total": float(today_sales["total"]),
            "month_sales_count": int(month_sales["count"]),
            "month_sales_total": float(month_sales["total"]),
            "low_stock_count": int(low_stock),
            "pending_reviews": int(pending_reviews),
            "unread_alerts": int(unread_alerts),
            "active_purchase_orders": int(active_pos),
            "ar_outstanding": float(ar_outstanding),
            "backorder_needs_po": int(backorder["needs_po"]) if backorder else 0,
            "backorder_awaiting_arrival": int(backorder["awaiting_arrival"]) if backorder else 0,
            "backorder_ready_pickup": int(backorder["ready_pickup"]) if backorder else 0,
            "backorder_total_active": int(backorder["total_active"]) if backorder else 0,
        }

    def dashboard_today_sales(self, limit: int = 10) -> list[dict]:
        """今日銷售明細。"""
        sql = text("""
            SELECT s.sale_id, s.customer_id, s.total, s.payment_method, s.created_at,
                   c.name as customer_name,
                   COUNT(sl.sale_line_id) as line_count
            FROM sales s
            LEFT JOIN customers c ON c.customer_id = s.customer_id
            LEFT JOIN sale_lines sl ON sl.sale_id = s.sale_id
            WHERE s.status = 'completed'
              AND s.created_at::date = CURRENT_DATE
            GROUP BY s.sale_id, c.name
            ORDER BY s.created_at DESC
            LIMIT :limit
        """)
        rows = self._session.execute(sql, {"limit": limit}).mappings().all()
        return [dict(r) for r in rows]

    def dashboard_low_stock_items(self, limit: int = 20) -> list[dict]:
        """低庫存品項清單。"""
        sql = text("""
            SELECT s.sku_id, p.name, s.brand, s.spec, s.unit,
                   ib.current_stock, s.min_stock,
                   s.min_stock - ib.current_stock as shortage
            FROM inventory_balances ib
            JOIN skus s ON s.sku_id = ib.sku_id AND s.is_active = true
            JOIN products p ON p.product_id = s.product_id AND p.is_active = true
            WHERE s.min_stock IS NOT NULL
              AND s.min_stock > 0
              AND ib.current_stock <= s.min_stock
            ORDER BY (s.min_stock - ib.current_stock) DESC
            LIMIT :limit
        """)
        rows = self._session.execute(sql, {"limit": limit}).mappings().all()
        return [dict(r) for r in rows]

    # ── 欠貨工作台 ──────────────────────────────────────
    def backorder_worklist(self, status_filter: str | None = None, limit: int = 50) -> list[dict]:
        """欠貨待補工作台 — 跨銷貨/採購的統一視圖。"""
        conditions = ["sl.backorder_qty > 0", "COALESCE(sl.backorder_status, '') != 'cancelled'",
                       "sl.backorder_qty > sl.backorder_delivered_qty"]
        params: dict = {"limit": limit}

        if status_filter:
            conditions.append("sl.backorder_status = :status")
            params["status"] = status_filter

        where = " AND ".join(conditions)
        sql = text(f"""
            SELECT sl.sale_line_id, sl.sale_id, sl.sku_id,
                   sl.product_name, sl.spec, sl.quantity AS ordered_qty,
                   sl.delivered_qty, sl.backorder_qty,
                   sl.backorder_ordered_qty, sl.backorder_arrived_qty, sl.backorder_delivered_qty,
                   sl.fulfillment_status, sl.backorder_status,
                   sl.notified_at, sl.notify_count, sl.reserved_customer_note,
                   s.customer_id, c.name AS customer_name, c.phone AS customer_phone,
                   s.created_at AS sale_date
            FROM sale_lines sl
            JOIN sales s ON s.sale_id = sl.sale_id AND s.status = 'completed'
            LEFT JOIN customers c ON c.customer_id = s.customer_id
            WHERE {where}
            ORDER BY
                CASE sl.backorder_status
                    WHEN 'arrived' THEN 1
                    WHEN 'partial_arrived' THEN 2
                    WHEN 'ordered' THEN 3
                    WHEN 'pending' THEN 4
                    WHEN 'partial_delivered' THEN 5
                END,
                s.created_at
            LIMIT :limit
        """)
        rows = self._session.execute(sql, params).mappings().all()
        return [dict(r) for r in rows]
