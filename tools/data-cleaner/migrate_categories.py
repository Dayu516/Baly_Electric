"""把既有的 category 欄位轉換為新的 category_path 格式。

舊分類（cleaner.py v1）→ 新分類路徑（v2）

Usage:
    python migrate_categories.py
"""

from database import get_db, init_db

# 舊分類 → 新 category_path 對照表
CATEGORY_MAP = {
    # 斷路器
    "斷路器/無熔絲開關": "開關與保護元件>斷路器類>無熔絲開關",
    "斷路器/漏電斷路器": "開關與保護元件>斷路器類>漏電斷路器",
    "斷路器/配線用斷路器": "開關與保護元件>斷路器類>無熔絲開關",
    # 配線器材
    "配線器材/電線電纜": "電線電纜>控制電纜",
    "配線器材/壓接端子": "端子與連接材料>壓著端子",
    "配線器材/PVC管線槽": "端子與連接材料>配線附件",
    "配線器材/配線槽扎帶": "端子與連接材料>配線附件",
    # 開關插座
    "開關插座/開關": "控制開關與操作元件>按鈕開關",
    "開關插座/插座": "控制開關與操作元件>按鈕開關",
    "開關插座/蓋板": "工具與耗材>安裝配件",
    # 照明
    "照明/LED燈管燈泡": "工具與耗材>耗材",
    "照明/燈具": "工具與耗材>耗材",
    "照明/安定器驅動器": "電源與供電>變壓器",
    # 控制器材
    "控制器材/接觸器電磁開關": "開關與保護元件>接觸器類>裸接觸器",
    "控制器材/繼電器": "繼電器與控制模組>一般繼電器",
    "控制器材/計時器": "繼電器與控制模組>計時器",
    "控制器材/溫控器": "感測器與儀表>溫度感測器",
    "控制器材/變頻器": "變頻器與驅動>變頻器",
    # 配電盤箱體
    "配電盤箱體/配電箱": "配電盤與箱體>箱體",
    "配電盤箱體/開關箱": "配電盤與箱體>箱體",
    "配電盤箱體/端子台": "端子與連接材料>端子台",
    # 感測器偵測器
    "感測器偵測器/光電感測器": "感測器與儀表>光電開關",
    "感測器偵測器/近接開關": "感測器與儀表>接近開關",
    "感測器偵測器/煙霧瓦斯偵測": "感測器與儀表>儀表",
    # 工具耗材
    "工具耗材/手工具": "工具與耗材>手工具",
    "工具耗材/電動工具": "工具與耗材>電動工具",
    "工具耗材/絕緣膠帶": "工具與耗材>耗材",
    "工具耗材/其他耗材": "工具與耗材>耗材",
    # 其他
    "其他": "",
}


def migrate():
    init_db()

    with get_db() as conn:
        # 檢查有多少筆需要轉換
        rows = conn.execute(
            "SELECT DISTINCT category FROM products_cleaned WHERE category != '' AND (category_path = '' OR category_path IS NULL)"
        ).fetchall()

        if not rows:
            print("沒有需要轉換的分類（category_path 已有值或 category 為空）")
            return

        print(f"找到 {len(rows)} 種舊分類需要轉換：")
        for r in rows:
            old = r["category"]
            new = CATEGORY_MAP.get(old, "")
            print(f"  {old} → {new or '(留空)'}")

        ans = input("\n確定要轉換嗎？(y/N) ")
        if ans.lower() != "y":
            print("取消")
            return

        total = 0
        for old_cat, new_path in CATEGORY_MAP.items():
            cur = conn.execute(
                "UPDATE products_cleaned SET category_path = ? WHERE category = ? AND (category_path = '' OR category_path IS NULL)",
                (new_path, old_cat),
            )
            if cur.rowcount > 0:
                print(f"  {old_cat} → {new_path}: {cur.rowcount} 筆")
                total += cur.rowcount

        print(f"\n轉換完成，共 {total} 筆")

        # 統計
        with_path = conn.execute("SELECT COUNT(*) FROM products_cleaned WHERE category_path != ''").fetchone()[0]
        without_path = conn.execute("SELECT COUNT(*) FROM products_cleaned WHERE category_path = '' OR category_path IS NULL").fetchone()[0]
        total_all = conn.execute("SELECT COUNT(*) FROM products_cleaned").fetchone()[0]
        print(f"有分類路徑: {with_path} / {total_all}")
        print(f"無分類路徑: {without_path} / {total_all}")


if __name__ == "__main__":
    migrate()
