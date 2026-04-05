"""Seed 替代品搜尋範例資料 — 照光選擇開關 + 屬性模板。

Usage:
    cd backend
    PYTHONPATH=. .venv/Scripts/python.exe scripts/seed_alternatives_demo.py
"""

import json
import uuid

from sqlalchemy.orm import Session
from database import engine
from infrastructure.persistence.orm_models import (
    CategoryORM, ProductORM, SKUORM,
    CategoryAttributeTemplateORM, ProductAttributeORM,
    InventoryBalanceORM,
)


def seed():
    session = Session(engine)

    # ── 分類：按鈕開關 / 照光選擇開關 ──
    parent_cat = session.query(CategoryORM).filter(CategoryORM.name == "按鈕開關").first()
    if not parent_cat:
        parent_cat = CategoryORM(name="按鈕開關", sort_order=5)
        session.add(parent_cat)
        session.flush()

    cat = session.query(CategoryORM).filter(CategoryORM.name == "照光選擇開關").first()
    if not cat:
        cat = CategoryORM(name="照光選擇開關", parent_id=parent_cat.category_id, sort_order=3)
        session.add(cat)
        session.flush()

    # ── 分類屬性模板（含 match 設定）──
    templates = [
        ("孔位",     "mm",  True,  1, "must",    ["30mm", "25mm", "22mm", "16mm"]),
        ("端子型式", None,  True,  2, "must",    ["螺絲", "焊接", "歐式端子"]),
        ("電壓",     None,  True,  3, "must",    ["AC220V", "AC110V", "DC24V", "DC12V"]),
        ("顏色",     None,  False, 4, "prefer",  ["綠色", "紅色", "黃色", "藍色", "白色"]),
        ("段數",     None,  False, 5, "prefer",  ["二段", "三段"]),
        ("外型",     None,  False, 6, "prefer",  ["圓形", "方形"]),
        ("柄長",     None,  False, 7, "optional", ["短柄", "長柄"]),
        ("品牌",     None,  False, 99, "optional", ["雷力", "和泉", "施耐德", "OMRON", "富士"]),
    ]

    # 先清掉舊的模板（如果有的話）
    session.query(CategoryAttributeTemplateORM).filter(
        CategoryAttributeTemplateORM.category_id == cat.category_id
    ).delete()

    for i, (key, unit, required, priority, mtype, options) in enumerate(templates):
        session.add(CategoryAttributeTemplateORM(
            category_id=cat.category_id,
            attr_key=key,
            attr_unit=unit,
            is_required=required,
            sort_order=i,
            attr_options=json.dumps(options, ensure_ascii=False),
            match_priority=priority,
            match_type=mtype,
        ))

    # ── 建立多個照光選擇開關品項 ──
    # Product = 規格概念，SKU = 品牌變體
    # 每個規格組合一個 Product，brand 只在 SKU 層級
    # product_key = 所有非品牌屬性的組合 → 決定是否共用 Product
    switches = [
        # (attrs, brand, sell_price, stock)
        # 目標品項：雷力 30mm AC220V 綠色 二段 圓形 短柄 螺絲 → 庫存 0
        ({"孔位": "30mm", "電壓": "AC220V", "顏色": "綠色", "段數": "二段", "外型": "圓形", "柄長": "短柄", "端子型式": "螺絲"},
         "雷力", 185, 0),

        # 替代品 1：和泉，完全相同規格，庫存 5
        ({"孔位": "30mm", "電壓": "AC220V", "顏色": "綠色", "段數": "二段", "外型": "圓形", "柄長": "短柄", "端子型式": "螺絲"},
         "和泉", 195, 5),

        # 替代品 2：施耐德，三段
        ({"孔位": "30mm", "電壓": "AC220V", "顏色": "綠色", "段數": "三段", "外型": "圓形", "柄長": "短柄", "端子型式": "螺絲"},
         "施耐德", 220, 3),

        # 替代品 3：和泉，紅色
        ({"孔位": "30mm", "電壓": "AC220V", "顏色": "紅色", "段數": "二段", "外型": "圓形", "柄長": "短柄", "端子型式": "螺絲"},
         "和泉", 195, 8),

        # 替代品 4：OMRON，方形 + 長柄
        ({"孔位": "30mm", "電壓": "AC220V", "顏色": "綠色", "段數": "二段", "外型": "方形", "柄長": "長柄", "端子型式": "螺絲"},
         "OMRON", 210, 2),

        # 不該出現：22mm（must fail: 孔位）
        ({"孔位": "22mm", "電壓": "AC220V", "顏色": "綠色", "段數": "二段", "外型": "圓形", "柄長": "短柄", "端子型式": "螺絲"},
         "雷力", 150, 10),

        # 不該出現：DC24V（must fail: 電壓）
        ({"孔位": "30mm", "電壓": "DC24V", "顏色": "綠色", "段數": "二段", "外型": "圓形", "柄長": "短柄", "端子型式": "螺絲"},
         "富士", 175, 4),

        # 不該出現：庫存 0
        ({"孔位": "30mm", "電壓": "AC220V", "顏色": "黃色", "段數": "二段", "外型": "圓形", "柄長": "短柄", "端子型式": "螺絲"},
         "富士", 170, 0),
    ]

    def _attr_key(attrs: dict) -> str:
        """非品牌屬性的組合 → 決定是否共用 Product"""
        return "|".join(f"{k}={v}" for k, v in sorted(attrs.items()))

    def _product_name(attrs: dict) -> str:
        parts = ["照光選擇開關", attrs.get("孔位", ""), attrs.get("段數", "")]
        extra = []
        if attrs.get("顏色") != "綠色":
            extra.append(attrs["顏色"])
        if attrs.get("電壓") != "AC220V":
            extra.append(attrs["電壓"])
        if attrs.get("外型") != "圓形":
            extra.append(attrs["外型"])
        return " ".join(parts + extra)

    products: dict[str, uuid.UUID] = {}
    first_sku_id = None

    for attrs, brand, price, stock in switches:
        ak = _attr_key(attrs)
        pname = _product_name(attrs)
        spec = " ".join(attrs.values())

        # Product（同屬性組合 → 同 Product，不同品牌是不同 SKU）
        if ak not in products:
            p = ProductORM(name=pname, category_id=cat.category_id)
            session.add(p)
            session.flush()
            products[ak] = p.product_id

            # ProductAttributes（只在建新 Product 時寫一次）
            for key, value in attrs.items():
                session.add(ProductAttributeORM(
                    product_id=p.product_id,
                    attr_key=key,
                    attr_value=value,
                ))

        product_id = products[ak]

        # SKU
        sku = SKUORM(
            product_id=product_id, brand=brand, spec=spec,
            unit="個", sell_price=price, cost_price=price * 0.6,
        )
        session.add(sku)
        session.flush()

        if first_sku_id is None:
            first_sku_id = sku.sku_id

        # InventoryBalance
        session.add(InventoryBalanceORM(sku_id=sku.sku_id, current_stock=stock))

    session.commit()

    # 統計
    p_name = "照光選擇開關"
    print(f"✓ 分類：{cat.name} (ID: {cat.category_id})")
    print(f"  屬性模板 x {len(templates)}")
    print(f"  品項 x {len(switches)}")
    print(f"  第一個 SKU (庫存0，用來測替代品): {first_sku_id}")
    print()
    print("  預期替代品搜尋結果：")
    print("    1. 和泉 30mm AC220V 綠色 二段 圓形 短柄 螺絲 (全符合, 庫存5)")
    print("    2. OMRON 30mm AC220V 綠色 二段 方形 長柄 螺絲 (外型不同)")
    print("    3. 施耐德 30mm AC220V 綠色 三段 圓形 短柄 螺絲 (段數不同)")
    print("    4. 和泉 30mm AC220V 紅色 二段 圓形 短柄 螺絲 (顏色不同)")
    print("    ✗ 雷力 22mm (must fail: 孔位)")
    print("    ✗ 富士 DC24V (must fail: 電壓)")
    print("    ✗ 富士 黃色 (庫存 0)")

    session.close()


if __name__ == "__main__":
    seed()
