"""SQLite 儲存層 — 取代 CSV + 記憶體。

Tables:
    products_cleaned  — 品項清洗結果
    customers_cleaned — 客戶清洗結果
"""

import sqlite3
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(__file__).parent / "data.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS products_cleaned (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL DEFAULT '',
    raw_name TEXT NOT NULL DEFAULT '',
    brand TEXT DEFAULT '',
    series TEXT DEFAULT '',
    model_number TEXT DEFAULT '',
    category TEXT DEFAULT '',
    category_path TEXT DEFAULT '',
    spec TEXT DEFAULT '',
    barcode TEXT DEFAULT '',
    supplier_code TEXT DEFAULT '',
    internal_code TEXT DEFAULT '',
    unit TEXT DEFAULT '個',
    sell_price REAL DEFAULT 0,
    cost_price REAL DEFAULT 0,
    min_stock INTEGER DEFAULT 0,
    item_type TEXT DEFAULT 'finished',
    structured_attrs TEXT DEFAULT '{}',
    parse_remark TEXT DEFAULT '',
    confidence REAL DEFAULT 0,
    bucket TEXT DEFAULT 'manual',
    aliases TEXT DEFAULT '',
    confirmed INTEGER DEFAULT 0,
    imported INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now','localtime')),
    updated_at TEXT DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS customers_cleaned (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL DEFAULT '',
    raw_name TEXT DEFAULT '',
    short_name TEXT DEFAULT '',
    customer_type TEXT DEFAULT '',
    phone TEXT DEFAULT '',
    mobile TEXT DEFAULT '',
    fax TEXT DEFAULT '',
    address TEXT DEFAULT '',
    unino TEXT DEFAULT '',
    contact TEXT DEFAULT '',
    payment_terms TEXT DEFAULT '',
    credit_limit REAL DEFAULT 0,
    internal_code TEXT DEFAULT '',
    note TEXT DEFAULT '',
    imported INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now','localtime'))
);

CREATE INDEX IF NOT EXISTS idx_products_bucket ON products_cleaned(bucket);
CREATE INDEX IF NOT EXISTS idx_products_brand ON products_cleaned(brand);
CREATE INDEX IF NOT EXISTS idx_products_category ON products_cleaned(category);
CREATE INDEX IF NOT EXISTS idx_products_confidence ON products_cleaned(confidence);
CREATE INDEX IF NOT EXISTS idx_products_name ON products_cleaned(name);
"""

# 既有 DB 升級用的 ALTER 語句（加新欄位，已存在則忽略）
MIGRATIONS = [
    "ALTER TABLE products_cleaned ADD COLUMN item_type TEXT DEFAULT 'finished'",
    "ALTER TABLE products_cleaned ADD COLUMN category_path TEXT DEFAULT ''",
    "ALTER TABLE products_cleaned ADD COLUMN structured_attrs TEXT DEFAULT '{}'",
    "ALTER TABLE products_cleaned ADD COLUMN parse_remark TEXT DEFAULT ''",
    "ALTER TABLE products_cleaned ADD COLUMN min_stock INTEGER DEFAULT 0",
]


def init_db():
    """建立資料庫和表格，並跑 migration。"""
    conn = sqlite3.connect(str(DB_PATH))
    conn.executescript(SCHEMA)
    # 跑 migration（既有 DB 加新欄位）
    for sql in MIGRATIONS:
        try:
            conn.execute(sql)
        except sqlite3.OperationalError:
            pass  # 欄位已存在
    # 建新 index（忽略已存在）
    try:
        conn.execute("CREATE INDEX IF NOT EXISTS idx_products_category_path ON products_cleaned(category_path)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_products_item_type ON products_cleaned(item_type)")
    except sqlite3.OperationalError:
        pass
    conn.commit()
    conn.close()


@contextmanager
def get_db():
    """取得 SQLite 連線（with 自動 commit/close）。"""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── Products CRUD ──────────────────────────────────────

PRODUCT_COLS = [
    "name", "raw_name", "brand", "series", "model_number", "category",
    "category_path", "spec", "barcode", "supplier_code", "internal_code",
    "unit", "sell_price", "cost_price", "min_stock", "item_type",
    "structured_attrs", "parse_remark", "confidence", "bucket", "aliases",
]

# 匯出 CSV 用的欄位（對齊主系統 ImportCatalogService 要求）
EXPORT_FIELDNAMES = [
    "name", "raw_name", "brand", "series", "model_number", "spec",
    "barcode", "supplier_code", "internal_code", "unit", "sell_price",
    "cost_price", "min_stock", "item_type", "category_path",
    "structured_attrs", "aliases", "parse_remark",
]

UPDATABLE_COLS = [
    "name", "brand", "series", "model_number", "category", "category_path",
    "spec", "unit", "sell_price", "cost_price", "min_stock", "item_type",
    "structured_attrs", "parse_remark", "bucket", "aliases", "confirmed",
]


def insert_products(rows: list[dict]):
    """批次插入品項。rows 是 dict list，key 對應 PRODUCT_COLS。"""
    if not rows:
        return
    cols = PRODUCT_COLS
    placeholders = ", ".join(["?"] * len(cols))
    sql = f"INSERT INTO products_cleaned ({', '.join(cols)}) VALUES ({placeholders})"
    with get_db() as conn:
        conn.executemany(sql, [
            tuple(row.get(c, "") for c in cols) for row in rows
        ])


def count_products(bucket: str = "all", search: str = "", brand: str = "",
                   category: str = "", item_type: str = "") -> int:
    sql = "SELECT COUNT(*) FROM products_cleaned WHERE 1=1"
    params: list = []
    sql, params = _apply_filters(sql, params, bucket, search, brand, category, item_type)
    with get_db() as conn:
        return conn.execute(sql, params).fetchone()[0]


def query_products(
    bucket: str = "all",
    page: int = 1,
    per_page: int = 50,
    search: str = "",
    brand: str = "",
    category: str = "",
    item_type: str = "",
    sort_by: str = "id",
    sort_dir: str = "asc",
) -> list[dict]:
    allowed_sorts = {
        "id", "name", "brand", "category", "category_path", "confidence",
        "bucket", "sell_price", "cost_price", "item_type",
    }
    if sort_by not in allowed_sorts:
        sort_by = "id"
    if sort_dir not in ("asc", "desc"):
        sort_dir = "asc"

    sql = "SELECT * FROM products_cleaned WHERE 1=1"
    params: list = []
    sql, params = _apply_filters(sql, params, bucket, search, brand, category, item_type)
    sql += f" ORDER BY {sort_by} {sort_dir}"
    sql += " LIMIT ? OFFSET ?"
    params.extend([per_page, (page - 1) * per_page])

    with get_db() as conn:
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]


def _apply_filters(sql, params, bucket, search, brand, category, item_type=""):
    if bucket and bucket != "all":
        sql += " AND bucket = ?"
        params.append(bucket)
    if search:
        sql += " AND (name LIKE ? OR raw_name LIKE ? OR brand LIKE ? OR model_number LIKE ? OR spec LIKE ? OR aliases LIKE ? OR category_path LIKE ?)"
        like = f"%{search}%"
        params.extend([like] * 7)
    if brand:
        sql += " AND brand = ?"
        params.append(brand)
    if category:
        sql += " AND (category = ? OR category_path = ? OR category_path LIKE ?)"
        params.extend([category, category, f"{category}>%"])
    if item_type:
        sql += " AND item_type = ?"
        params.append(item_type)
    return sql, params


def get_product(product_id: int) -> dict | None:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM products_cleaned WHERE id = ?", (product_id,)).fetchone()
        return dict(row) if row else None


def update_product(product_id: int, updates: dict) -> bool:
    fields = {k: v for k, v in updates.items() if k in UPDATABLE_COLS}
    if not fields:
        return False
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    set_clause += ", updated_at = datetime('now','localtime')"
    params = list(fields.values())
    params.append(product_id)
    with get_db() as conn:
        conn.execute(f"UPDATE products_cleaned SET {set_clause} WHERE id = ?", params)
    return True


def delete_product(product_id: int) -> bool:
    with get_db() as conn:
        cur = conn.execute("DELETE FROM products_cleaned WHERE id = ?", (product_id,))
        return cur.rowcount > 0


def batch_update_products(ids: list[int], updates: dict) -> int:
    fields = {k: v for k, v in updates.items() if k in UPDATABLE_COLS}
    if not fields or not ids:
        return 0
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    set_clause += ", updated_at = datetime('now','localtime')"
    params = list(fields.values())
    placeholders = ", ".join(["?"] * len(ids))
    params.extend(ids)
    with get_db() as conn:
        cur = conn.execute(
            f"UPDATE products_cleaned SET {set_clause} WHERE id IN ({placeholders})",
            params,
        )
        return cur.rowcount


def batch_delete_products(ids: list[int]) -> int:
    if not ids:
        return 0
    placeholders = ", ".join(["?"] * len(ids))
    with get_db() as conn:
        cur = conn.execute(f"DELETE FROM products_cleaned WHERE id IN ({placeholders})", ids)
        return cur.rowcount


def get_stats() -> dict:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT bucket, COUNT(*) as cnt FROM products_cleaned GROUP BY bucket"
        ).fetchall()
        total = conn.execute("SELECT COUNT(*) FROM products_cleaned").fetchone()[0]
        confirmed_total = conn.execute("SELECT COUNT(*) FROM products_cleaned WHERE confirmed = 1").fetchone()[0]
        imported_total = conn.execute("SELECT COUNT(*) FROM products_cleaned WHERE imported = 1").fetchone()[0]

    stats = {"auto": 0, "review": 0, "manual": 0, "total": total,
             "confirmed": confirmed_total, "imported": imported_total}
    for r in rows:
        stats[r["bucket"]] = r["cnt"]
    return stats


def get_distinct_brands() -> list[str]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT DISTINCT brand FROM products_cleaned WHERE brand != '' ORDER BY brand"
        ).fetchall()
        return [r["brand"] for r in rows]


def get_distinct_categories() -> list[str]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT DISTINCT category_path FROM products_cleaned WHERE category_path != '' ORDER BY category_path"
        ).fetchall()
        result = [r["category_path"] for r in rows]
        if not result:
            # fallback 到舊欄位
            rows = conn.execute(
                "SELECT DISTINCT category FROM products_cleaned WHERE category != '' ORDER BY category"
            ).fetchall()
            result = [r["category"] for r in rows]
        return result


def get_distinct_item_types() -> list[str]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT DISTINCT item_type FROM products_cleaned WHERE item_type != '' ORDER BY item_type"
        ).fetchall()
        return [r["item_type"] for r in rows]


def export_products(bucket: str = "all") -> list[dict]:
    sql = "SELECT * FROM products_cleaned"
    params = []
    if bucket != "all":
        sql += " WHERE bucket = ?"
        params.append(bucket)
    sql += " ORDER BY id"
    with get_db() as conn:
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]


def get_importable_products(bucket: str = "auto") -> list[dict]:
    sql = "SELECT * FROM products_cleaned WHERE imported = 0 AND bucket = ? ORDER BY id"
    with get_db() as conn:
        rows = conn.execute(sql, (bucket,)).fetchall()
        return [dict(r) for r in rows]


def mark_imported(ids: list[int]):
    if not ids:
        return
    placeholders = ", ".join(["?"] * len(ids))
    with get_db() as conn:
        conn.execute(
            f"UPDATE products_cleaned SET imported = 1, updated_at = datetime('now','localtime') WHERE id IN ({placeholders})",
            ids,
        )


# ── Customers CRUD ────────────────────────────────────

CUSTOMER_COLS = [
    "name", "raw_name", "short_name", "customer_type", "phone", "mobile",
    "fax", "address", "unino", "contact", "payment_terms", "credit_limit",
    "internal_code", "note",
]


def insert_customers(rows: list[dict]):
    if not rows:
        return
    cols = CUSTOMER_COLS
    placeholders = ", ".join(["?"] * len(cols))
    sql = f"INSERT INTO customers_cleaned ({', '.join(cols)}) VALUES ({placeholders})"
    with get_db() as conn:
        conn.executemany(sql, [
            tuple(row.get(c, "") for c in cols) for row in rows
        ])


def count_customers() -> int:
    with get_db() as conn:
        return conn.execute("SELECT COUNT(*) FROM customers_cleaned").fetchone()[0]


def query_customers(page: int = 1, per_page: int = 50, search: str = "") -> list[dict]:
    sql = "SELECT * FROM customers_cleaned WHERE 1=1"
    params: list = []
    if search:
        sql += " AND (name LIKE ? OR short_name LIKE ? OR phone LIKE ? OR address LIKE ?)"
        like = f"%{search}%"
        params.extend([like] * 4)
    sql += " ORDER BY id LIMIT ? OFFSET ?"
    params.extend([per_page, (page - 1) * per_page])
    with get_db() as conn:
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]


def get_importable_customers() -> list[dict]:
    sql = "SELECT * FROM customers_cleaned WHERE imported = 0 ORDER BY id"
    with get_db() as conn:
        rows = conn.execute(sql).fetchall()
        return [dict(r) for r in rows]


def mark_customers_imported(ids: list[int]):
    if not ids:
        return
    placeholders = ", ".join(["?"] * len(ids))
    with get_db() as conn:
        conn.execute(
            f"UPDATE customers_cleaned SET imported = 1 WHERE id IN ({placeholders})",
            ids,
        )


# ── Init on import ─────────────────────────────────────
init_db()
