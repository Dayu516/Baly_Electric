"""Seed 範例資料 — 一個品項、5 間供應商、多筆報價歷史。

Usage:
    cd backend
    PYTHONPATH=. .venv/Scripts/python.exe scripts/seed_supplier_quotes.py
"""

import uuid
from datetime import datetime, timezone, timedelta

from sqlalchemy.orm import Session
from database import engine
from infrastructure.persistence.orm_models import (
    CategoryORM, ProductORM, SKUORM, SupplierORM,
    SupplierProductORM, SupplierPriceQuoteORM,
)

def seed():
    session = Session(engine)

    # ── 分類 ──
    cat = session.query(CategoryORM).filter(CategoryORM.name == "電線電纜").first()
    if not cat:
        cat = CategoryORM(name="電線電纜", sort_order=1)
        session.add(cat)
        session.flush()

    # ── 品項 ──
    product = ProductORM(
        name="PVC 單心線 2.0mm²",
        series=None,
        model_number="IV 2.0",
        category_id=cat.category_id,
        description="2.0mm² PVC 絕緣單心線，一般配線用",
    )
    session.add(product)
    session.flush()

    # ── SKU ──
    sku = SKUORM(
        product_id=product.product_id,
        spec="2.0mm² 白色 100M/捲",
        unit="捲",
        sell_price=850,
        cost_price=680,
        barcode=f"WIRE20-{uuid.uuid4().hex[:6]}",
    )
    session.add(sku)
    session.flush()

    # ── 5 間供應商 ──
    suppliers_data = [
        {"name": "太平洋電線電纜", "phone": "02-2761-1111", "contact": "林經理"},
        {"name": "華新麗華",       "phone": "02-2501-6111", "contact": "陳小姐"},
        {"name": "大山電線電纜",   "phone": "02-2999-3388", "contact": "張先生"},
        {"name": "宏泰電工",       "phone": "04-2359-0011", "contact": "王經理"},
        {"name": "東亞電線電纜",   "phone": "02-2291-5111", "contact": "李主任"},
    ]

    suppliers = []
    for sd in suppliers_data:
        sup = session.query(SupplierORM).filter(SupplierORM.name == sd["name"]).first()
        if not sup:
            sup = SupplierORM(name=sd["name"], phone=sd["phone"], contact_name=sd["contact"])
            session.add(sup)
            session.flush()
        suppliers.append(sup)

    # ── supplier_products 關聯 + 報價歷史 ──
    # 每家報價不同，模擬 3 個月的報價變動
    pricing = [
        # (供應商index, 當前成本, is_preferred, 報價歷史 [(月份偏移, 價格, 備註)])
        (0, 680, True,  [(-3, 650, "年初報價"), (-2, 660, "二月微漲"), (-1, 670, "三月調漲"), (0, 680, "四月報價")]),
        (1, 710, False, [(-3, 690, "Q1 報價"), (-1, 700, "三月報價"), (0, 710, "四月漲價5%")]),
        (2, 660, False, [(-2, 640, "促銷價"), (-1, 650, "三月報價"), (0, 660, "四月回調")]),
        (3, 720, False, [(-3, 710, "中部出貨"), (0, 720, "四月報價")]),
        (4, 695, False, [(-4, 670, "年初特價"), (-2, 680, "二月報價"), (-1, 690, "三月調整"), (0, 695, "四月報價")]),
    ]

    now = datetime(2026, 4, 1, tzinfo=timezone.utc)

    for sup_idx, current_cost, is_preferred, quotes in pricing:
        sup = suppliers[sup_idx]

        # supplier_products 關聯
        sp = SupplierProductORM(
            supplier_id=sup.supplier_id,
            sku_id=sku.sku_id,
            supplier_product_name=f"{sup.name} IV線 2.0mm²",
            unit_cost=current_cost,
            pack_unit="100M/捲",
            pack_qty=1,
            min_order_qty=10,
            lead_days=2 if sup_idx < 3 else 3,
            is_preferred=is_preferred,
        )
        session.add(sp)

        # 報價歷史
        for month_offset, price, note in quotes:
            quote_date = now + timedelta(days=month_offset * 30)
            q = SupplierPriceQuoteORM(
                supplier_id=sup.supplier_id,
                sku_id=sku.sku_id,
                unit_price=price,
                unit="捲",
                quoted_at=quote_date,
                note=note,
                created_at=datetime.now(timezone.utc),
            )
            session.add(q)

    session.commit()

    # 取值後再 close
    p_name = product.name
    p_id = product.product_id
    s_spec = sku.spec
    s_price = sku.sell_price
    sup_names = [(suppliers[i].name, c, p, len(q)) for i, c, p, q in pricing]

    session.close()

    print(f"✓ 品項: {p_name} (ID: {p_id})")
    print(f"  SKU: {s_spec} 售價${s_price}")
    print(f"  供應商 x {len(sup_names)}:")
    for name, cost, preferred, qcount in sup_names:
        star = " ★" if preferred else ""
        print(f"    {name}: ${cost}{star} ({qcount} 筆報價)")
    print(f"\n共 {sum(q for _, _, _, q in sup_names)} 筆報價紀錄")


if __name__ == "__main__":
    seed()
