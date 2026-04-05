"""預設品項家族分類 + 屬性模板。

基於電控材料行品項分級：
- A級：結構型（接觸器/電磁閥）
- B級：規格型（斷路器/按鈕/電纜/端子...）
- C級：單品型（繼電器/計時器/PLC/變頻器...）
- D級：雜項耗材

Usage:
    cd backend
    PYTHONPATH=. .venv/Scripts/python.exe scripts/seed_product_templates.py
"""

import uuid
from database import SessionLocal
from sqlalchemy import text


def run():
    session = SessionLocal()

    # ═══════════════════════════════════════════════════
    # 先清除 smoke test 產生的假分類
    # ═══════════════════════════════════════════════════
    session.execute(text("DELETE FROM categories WHERE name LIKE 'smoke-cat-%'"))
    session.commit()

    # ═══════════════════════════════════════════════════
    # 分類結構定義
    # ═══════════════════════════════════════════════════
    # 格式：(name, parent_key, sort_order, level, children_or_None)
    # level: A/B/C/D 對應管理等級

    tree = [
        ("開關與保護元件", None, 1, [
            ("接觸器類", None, 1, [
                ("裸接觸器", None, 1, "A"),
                ("積熱電驛", None, 2, "A"),
                ("電磁開關", None, 3, "A"),
                ("接觸器零件", None, 4, "A"),
            ]),
            ("斷路器類", None, 2, [
                ("無熔絲開關", None, 1, "B"),
                ("漏電斷路器", None, 2, "B"),
            ]),
            ("保險絲類", None, 3, [
                ("保險絲", None, 1, "B"),
                ("保險絲座", None, 2, "B"),
            ]),
        ]),
        ("控制開關與操作元件", None, 2, [
            ("按鈕開關", None, 1, "B"),
            ("選擇開關", None, 2, "B"),
            ("指示燈", None, 3, "B"),
            ("微動開關", None, 4, "C"),
            ("限動開關", None, 5, "C"),
        ]),
        ("繼電器與控制模組", None, 3, [
            ("一般繼電器", None, 1, "C"),
            ("計時器", None, 2, "C"),
            ("監控保護模組", None, 3, "C"),
        ]),
        ("PLC與自動化控制", None, 4, [
            ("PLC", None, 1, "C"),
            ("HMI 人機介面", None, 2, "C"),
            ("工業通訊模組", None, 3, "C"),
        ]),
        ("變頻器與驅動", None, 5, [
            ("變頻器", None, 1, "C"),
            ("伺服系統", None, 2, "C"),
            ("軟啟動器", None, 3, "C"),
        ]),
        ("電源與供電", None, 6, [
            ("開關電源", None, 1, "B"),
            ("變壓器", None, 2, "B"),
            ("UPS / 電池", None, 3, "C"),
        ]),
        ("感測器與儀表", None, 7, [
            ("接近開關", None, 1, "C"),
            ("光電開關", None, 2, "C"),
            ("溫度感測器", None, 3, "C"),
            ("儀表", None, 4, "C"),
        ]),
        ("端子與連接材料", None, 8, [
            ("端子台", None, 1, "B"),
            ("壓著端子", None, 2, "B"),
            ("連接器", None, 3, "B"),
            ("配線附件", None, 4, "D"),
        ]),
        ("電線電纜", None, 9, [
            ("控制電纜", None, 1, "B"),
            ("動力電纜", None, 2, "B"),
            ("通訊線", None, 3, "B"),
        ]),
        ("配電盤與箱體", None, 10, [
            ("箱體", None, 1, "B"),
            ("DIN 軌道", None, 2, "D"),
            ("母排 / 安裝件", None, 3, "D"),
        ]),
        ("氣動與電磁閥", None, 11, [
            ("電磁閥本體", None, 1, "A"),
            ("電磁閥線圈", None, 2, "A"),
            ("氣動元件", None, 3, "B"),
        ]),
        ("工具與耗材", None, 12, [
            ("手工具", None, 1, "D"),
            ("電動工具", None, 2, "D"),
            ("耗材", None, 3, "D"),
            ("安裝配件", None, 4, "D"),
        ]),
    ]

    # ═══════════════════════════════════════════════════
    # 屬性模板定義
    # ═══════════════════════════════════════════════════
    templates = {
        # A級：接觸器家族
        "裸接觸器": [
            ("品牌", None, True, "士林,東元,OMRON,施耐德,富士,ABB", "must", 1),
            ("系列", None, True, None, "must", 2),
            ("框架型號", None, True, None, "must", 3),
            ("主接點數", None, True, "3P,4P", "must", 4),
            ("單接點額定電流(A)", "A", True, None, "must", 5),
            ("輔助接點配置", None, True, "1a,1a1b,2a,2a2b", "must", 6),
            ("線圈電壓", None, True, "AC110V,AC220V,AC380V,DC24V", "must", 7),
            ("額定使用類別", None, False, "AC1,AC3", "optional", 8),
            ("適用HP", "HP", False, None, "optional", 9),
            ("適用kW", "kW", False, None, "optional", 10),
        ],
        "積熱電驛": [
            ("品牌", None, True, "士林,東元,OMRON,施耐德,富士,ABB", "must", 1),
            ("系列", None, True, None, "must", 2),
            ("額定電流範圍", "A", True, None, "must", 3),
            ("適用HP", "HP", False, None, "optional", 4),
        ],
        "電磁開關": [
            ("品牌", None, True, "士林,東元,OMRON,施耐德,富士,ABB", "must", 1),
            ("系列", None, True, None, "must", 2),
            ("接觸器框架型號", None, True, None, "must", 3),
            ("線圈電壓", None, True, "AC110V,AC220V,AC380V,DC24V", "must", 4),
            ("積熱型號", None, True, None, "must", 5),
            ("積熱電流", "A", True, None, "must", 6),
            ("適用HP", "HP", False, None, "optional", 7),
            ("適用kW", "kW", False, None, "optional", 8),
        ],
        "接觸器零件": [
            ("零件類型", None, True, "線圈,輔助接點模組,安裝底板", "must", 1),
            ("適用框架型號", None, True, None, "must", 2),
            ("電壓", None, True, "AC110V,AC220V,AC380V,DC24V", "must", 3),
        ],

        # B級：按鈕/選擇/指示燈
        "按鈕開關": [
            ("品牌", None, True, None, "must", 1),
            ("系列", None, True, None, "must", 2),
            ("孔徑", "mm", True, "16,22,25,30", "must", 3),
            ("顏色", None, True, "紅,綠,黃,白,藍,黑", "prefer", 4),
            ("接點型式", None, True, "1a,1b,1a1b,2a,2b", "must", 5),
            ("自復/保持", None, True, "自復,保持", "prefer", 6),
            ("是否照光", None, False, "是,否", "prefer", 7),
            ("燈壓", None, False, "AC110V,AC220V,DC24V,LED", "optional", 8),
            ("頭部型式", None, False, "平頭,凸頭,蘑菇頭,鑰匙", "optional", 9),
        ],
        "選擇開關": [
            ("品牌", None, True, None, "must", 1),
            ("系列", None, True, None, "must", 2),
            ("孔徑", "mm", True, "16,22,25,30", "must", 3),
            ("段數", None, True, "2段,3段", "must", 4),
            ("接點型式", None, True, "1a,1b,1a1b,2a,2b", "must", 5),
            ("長柄/短柄", None, False, "長柄,短柄,標準", "prefer", 6),
            ("是否照光", None, False, "是,否", "optional", 7),
            ("燈壓", None, False, "AC110V,AC220V,DC24V,LED", "optional", 8),
        ],
        "指示燈": [
            ("品牌", None, True, None, "must", 1),
            ("系列", None, True, None, "must", 2),
            ("孔徑", "mm", True, "16,22,25,30", "must", 3),
            ("顏色", None, True, "紅,綠,黃,白,藍", "must", 4),
            ("發光方式", None, False, "LED,燈泡", "prefer", 5),
            ("電壓", None, True, "AC110V,AC220V,DC24V", "must", 6),
            ("是否可換燈泡", None, False, "是,否", "optional", 7),
            ("燈泡型號", None, False, None, "optional", 8),
        ],

        # B級：斷路器
        "無熔絲開關": [
            ("品牌", None, True, None, "must", 1),
            ("系列", None, True, None, "must", 2),
            ("框架型號", None, True, None, "must", 3),
            ("極數", None, True, "1P,2P,3P,4P", "must", 4),
            ("額定電流", "A", True, None, "must", 5),
            ("遮斷容量", "kA", False, None, "prefer", 6),
            ("安裝方式", None, False, "固定型,插入型", "optional", 7),
        ],
        "漏電斷路器": [
            ("品牌", None, True, None, "must", 1),
            ("系列", None, True, None, "must", 2),
            ("極數", None, True, "2P,3P,4P", "must", 3),
            ("額定電流", "A", True, None, "must", 4),
            ("漏電靈敏度", "mA", True, "15,30,50,100,200,500", "must", 5),
            ("遮斷容量", "kA", False, None, "prefer", 6),
        ],

        # B級：電線電纜
        "控制電纜": [
            ("品牌", None, True, None, "must", 1),
            ("線徑", "mm²", True, None, "must", 2),
            ("芯數", None, True, None, "must", 3),
            ("遮蔽", None, False, "有,無", "prefer", 4),
            ("外被材質", None, False, "PVC,PE,矽膠", "optional", 5),
            ("電壓等級", "V", False, None, "optional", 6),
            ("柔性等級", None, False, "固定配線,可動配線,機器人級", "optional", 7),
        ],
        "動力電纜": [
            ("品牌", None, True, None, "must", 1),
            ("線徑", "mm²", True, None, "must", 2),
            ("芯數", None, True, None, "must", 3),
            ("電壓等級", "V", False, None, "prefer", 4),
        ],

        # A級：電磁閥
        "電磁閥本體": [
            ("品牌", None, True, None, "must", 1),
            ("系列", None, True, None, "must", 2),
            ("口數位數", None, True, "2/2,3/2,4/2,5/2,5/3", "must", 3),
            ("接口尺寸", None, True, None, "must", 4),
            ("作動方式", None, False, "直動式,先導式", "prefer", 5),
            ("配管尺寸", None, False, None, "optional", 6),
        ],
        "電磁閥線圈": [
            ("品牌", None, True, None, "must", 1),
            ("適用閥體型號", None, True, None, "must", 2),
            ("電壓", None, True, "AC110V,AC220V,DC24V", "must", 3),
            ("功率", "W", False, None, "optional", 4),
            ("插頭型式", None, False, None, "optional", 5),
        ],

        # C級：繼電器/計時器
        "一般繼電器": [
            ("品牌", None, True, None, "must", 1),
            ("型號", None, True, None, "must", 2),
            ("線圈電壓", None, True, "AC110V,AC220V,DC24V,DC12V", "must", 3),
            ("接點數", None, True, None, "must", 4),
            ("接點型式", None, False, None, "prefer", 5),
            ("底座型號", None, False, None, "optional", 6),
        ],
        "計時器": [
            ("品牌", None, True, None, "must", 1),
            ("型號", None, True, None, "must", 2),
            ("電壓", None, True, "AC110V,AC220V,DC24V", "must", 3),
            ("時間範圍", None, True, None, "must", 4),
            ("功能類型", None, False, "ON delay,OFF delay,Star-Delta,Flicker", "prefer", 5),
            ("接點數", None, False, None, "optional", 6),
        ],

        # B級：其他
        "端子台": [
            ("品牌", None, True, None, "must", 1),
            ("型號", None, True, None, "must", 2),
            ("適用線徑", "mm²", True, None, "must", 3),
            ("層數", None, False, "單層,雙層,三層", "optional", 4),
            ("軌道規格", None, False, "35mm DIN", "optional", 5),
        ],
        "開關電源": [
            ("品牌", None, True, None, "must", 1),
            ("型號", None, True, None, "must", 2),
            ("輸入電壓", None, True, None, "must", 3),
            ("輸出電壓", "V", True, None, "must", 4),
            ("輸出電流", "A", True, None, "must", 5),
            ("瓦數", "W", False, None, "prefer", 6),
        ],
        "變壓器": [
            ("品牌", None, True, None, "must", 1),
            ("型號", None, True, None, "must", 2),
            ("一次側電壓", "V", True, None, "must", 3),
            ("二次側電壓", "V", True, None, "must", 4),
            ("容量", "VA", True, None, "must", 5),
        ],
        "變頻器": [
            ("品牌", None, True, None, "must", 1),
            ("型號", None, True, None, "must", 2),
            ("輸入電壓", None, True, None, "must", 3),
            ("輸出相數", None, True, "單相,三相", "must", 4),
            ("功率", "kW", True, None, "must", 5),
            ("適用馬達", "HP", False, None, "optional", 6),
        ],
        "PLC": [
            ("品牌", None, True, None, "must", 1),
            ("系列", None, True, None, "must", 2),
            ("型號", None, True, None, "must", 3),
            ("點數", None, False, None, "prefer", 4),
            ("IO 類型", None, False, None, "optional", 5),
            ("通訊介面", None, False, None, "optional", 6),
        ],
    }

    import json

    # ═══════════════════════════════════════════════════
    # 建立分類樹
    # ═══════════════════════════════════════════════════
    cat_ids = {}  # name -> uuid

    def create_cat(name, parent_id, sort_order):
        # 檢查是否已存在
        existing = session.execute(
            text("SELECT category_id FROM categories WHERE name = :n AND (parent_id = :pid OR (parent_id IS NULL AND :pid IS NULL))"),
            {"n": name, "pid": str(parent_id) if parent_id else None},
        ).scalar()
        if existing:
            cat_ids[name] = str(existing)
            return str(existing)

        cid = str(uuid.uuid4())
        session.execute(text("""
            INSERT INTO categories (category_id, name, parent_id, sort_order)
            VALUES (:id, :name, :pid, :sort)
        """), {"id": cid, "name": name, "pid": str(parent_id) if parent_id else None, "sort": sort_order})
        cat_ids[name] = cid
        return cid

    for big_name, _, big_sort, children in tree:
        big_id = create_cat(big_name, None, big_sort)
        for child in children:
            if len(child) == 4:
                # 子分類（葉節點）
                sub_name, _, sub_sort, level = child
                create_cat(sub_name, big_id, sub_sort)
            elif len(child) == 4 and isinstance(child[3], list):
                # 中間層
                mid_name, _, mid_sort, grandchildren = child
                mid_id = create_cat(mid_name, big_id, mid_sort)
                for gc in grandchildren:
                    gc_name, _, gc_sort, level = gc
                    create_cat(gc_name, mid_id, gc_sort)

    # 特殊處理：有三層結構的（開關與保護元件）
    # 重新建立三層結構
    parent_1 = cat_ids.get("開關與保護元件")
    if parent_1:
        for group_name, _, group_sort, group_children in tree[0][3]:
            if isinstance(group_children, list):
                group_id = create_cat(group_name, parent_1, group_sort)
                for leaf_name, _, leaf_sort, _ in group_children:
                    create_cat(leaf_name, group_id, leaf_sort)

    session.commit()
    print(f"分類建立完成：{len(cat_ids)} 個")

    # ═══════════════════════════════════════════════════
    # 建立屬性模板
    # ═══════════════════════════════════════════════════
    count = 0
    for cat_name, attrs in templates.items():
        cat_id = cat_ids.get(cat_name)
        if not cat_id:
            print(f"  ⚠ 找不到分類：{cat_name}")
            continue

        # 先刪除舊模板
        session.execute(text("DELETE FROM category_attribute_templates WHERE category_id = :cid"), {"cid": cat_id})

        for attr_key, attr_unit, is_required, options_str, match_type, sort_order in attrs:
            options_json = json.dumps(options_str.split(","), ensure_ascii=False) if options_str else None
            session.execute(text("""
                INSERT INTO category_attribute_templates (template_id, category_id, attr_key, attr_unit, is_required, sort_order, attr_options, match_type, match_priority)
                VALUES (:tid, :cid, :key, :unit, :req, :sort, :opts, :mt, :mp)
            """), {
                "tid": str(uuid.uuid4()), "cid": cat_id, "key": attr_key, "unit": attr_unit,
                "req": is_required, "sort": sort_order, "opts": options_json,
                "mt": match_type, "mp": sort_order,
            })
            count += 1

    session.commit()
    print(f"屬性模板建立完成：{count} 個欄位，涵蓋 {len(templates)} 個分類")

    session.close()


if __name__ == "__main__":
    run()
