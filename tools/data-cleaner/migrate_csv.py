"""把既有 CSV 匯入 SQLite。

Usage:
    python migrate_csv.py
    # 讀取 output/*.csv → 寫入 data.db
"""

import csv
import sys
from pathlib import Path

from database import (
    DB_PATH, init_db, get_db,
    insert_products, insert_customers, PRODUCT_COLS, CUSTOMER_COLS,
)


def read_csv(path: Path) -> list[dict]:
    """讀取 CSV，自動嘗試編碼。"""
    for enc in ["utf-8-sig", "big5", "cp950", "utf-8"]:
        try:
            with open(path, "r", encoding=enc) as f:
                return [dict(r) for r in csv.DictReader(f)]
        except (UnicodeDecodeError, UnicodeError):
            continue
    print(f"  [ERROR] 無法讀取 {path}")
    return []


def migrate():
    output_dir = Path(__file__).parent / "output"

    if not output_dir.exists():
        print("output/ 目錄不存在，請先跑清洗")
        sys.exit(1)

    # 如果 DB 已存在，詢問是否覆蓋
    if DB_PATH.exists():
        ans = input(f"data.db 已存在，要刪除重建嗎？(y/N) ")
        if ans.lower() == "y":
            DB_PATH.unlink()
            print("已刪除舊 data.db")
        else:
            print("取消")
            return

    init_db()

    # 匯入品項
    all_cleaned = output_dir / "all_cleaned.csv"
    if all_cleaned.exists():
        rows = read_csv(all_cleaned)
        print(f"讀取 all_cleaned.csv: {len(rows)} 筆")
        # 正規化欄位
        for row in rows:
            for col in ["sell_price", "cost_price", "confidence"]:
                try:
                    row[col] = float(row.get(col, 0) or 0)
                except (ValueError, TypeError):
                    row[col] = 0
        insert_products(rows)
        print(f"已匯入 {len(rows)} 筆品項到 SQLite")
    else:
        print("all_cleaned.csv 不存在，跳過品項匯入")

    # 匯入客戶
    customers_csv = output_dir / "customers_cleaned.csv"
    if customers_csv.exists():
        rows = read_csv(customers_csv)
        print(f"讀取 customers_cleaned.csv: {len(rows)} 筆")
        for row in rows:
            try:
                row["credit_limit"] = float(row.get("credit_limit", 0) or 0)
            except (ValueError, TypeError):
                row["credit_limit"] = 0
        insert_customers(rows)
        print(f"已匯入 {len(rows)} 筆客戶到 SQLite")
    else:
        print("customers_cleaned.csv 不存在，跳過客戶匯入")

    # 統計
    with get_db() as conn:
        p_count = conn.execute("SELECT COUNT(*) FROM products_cleaned").fetchone()[0]
        c_count = conn.execute("SELECT COUNT(*) FROM customers_cleaned").fetchone()[0]
        buckets = conn.execute(
            "SELECT bucket, COUNT(*) FROM products_cleaned GROUP BY bucket"
        ).fetchall()

    print(f"\n{'='*40}")
    print(f"匯入完成！")
    print(f"  品項: {p_count} 筆")
    for b in buckets:
        print(f"    {b[0]}: {b[1]} 筆")
    print(f"  客戶: {c_count} 筆")
    print(f"  資料庫: {DB_PATH}")
    print(f"{'='*40}")


if __name__ == "__main__":
    migrate()
