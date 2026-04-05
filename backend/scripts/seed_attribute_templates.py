"""建立分類屬性模板 — 定義每個分類的品項應該有哪些屬性。

Usage:
    cd backend
    .venv/Scripts/python.exe -m scripts.seed_attribute_templates
"""

import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy.orm import Session
from database import SessionLocal
from infrastructure.persistence.orm_models import CategoryORM, CategoryAttributeTemplateORM

# 分類名 → 屬性列表 [(key, unit, required, sort)]
TEMPLATES = {
    "無熔絲開關 (NFB/BH)": [
        ("極數", None, True, 1),
        ("額定電流", "A", True, 2),
        ("框架容量", "AF", False, 3),
        ("啟斷容量", "kA", False, 4),
    ],
    "漏電斷路器": [
        ("極數", None, True, 1),
        ("額定電流", "A", True, 2),
        ("感度電流", "mA", False, 3),
        ("框架容量", "AF", False, 4),
    ],
    "配線用斷路器": [
        ("極數", None, True, 1),
        ("額定電流", "A", True, 2),
        ("框架容量", "AF", False, 3),
    ],
    "電線電纜": [
        ("線徑", "mm²", True, 1),
        ("芯數", None, False, 2),
        ("顏色", None, False, 3),
        ("長度", "M", False, 4),
        ("耐壓", "V", False, 5),
    ],
    "壓接端子": [
        ("適用線徑", "mm²", True, 1),
        ("螺絲規格", None, False, 2),
        ("型式", None, False, 3),
    ],
    "開關": [
        ("迴路數", None, False, 1),
        ("額定電流", "A", False, 2),
        ("額定電壓", "V", False, 3),
    ],
    "插座": [
        ("額定電流", "A", False, 1),
        ("額定電壓", "V", False, 2),
        ("接地", None, False, 3),
    ],
    "接觸器/電磁開關": [
        ("額定電流", "A", True, 1),
        ("線圈電壓", "V", True, 2),
        ("輔助接點", None, False, 3),
        ("主接點數", None, False, 4),
    ],
    "繼電器": [
        ("線圈電壓", "V", True, 1),
        ("接點數", None, False, 2),
        ("接點容量", "A", False, 3),
    ],
    "計時器": [
        ("電壓", "V", True, 1),
        ("時間範圍", None, False, 2),
        ("動作模式", None, False, 3),
    ],
    "溫控器": [
        ("電壓", "V", False, 1),
        ("溫度範圍", "°C", False, 2),
        ("感測器類型", None, False, 3),
    ],
    "變頻器": [
        ("額定容量", "HP", True, 1),
        ("輸入電壓", "V", True, 2),
        ("輸出電壓", "V", False, 3),
    ],
    "LED燈管/燈泡": [
        ("瓦數", "W", True, 1),
        ("色溫", "K", False, 2),
        ("尺寸", None, False, 3),
        ("燈頭規格", None, False, 4),
    ],
}


def seed():
    session: Session = SessionLocal()
    created = 0
    skipped = 0

    try:
        for cat_name, attrs in TEMPLATES.items():
            # 找分類
            cat = session.query(CategoryORM).filter(CategoryORM.name == cat_name).first()
            if not cat:
                print(f"  [SKIP] 分類 '{cat_name}' 不存在")
                skipped += 1
                continue

            # 檢查是否已有模板
            existing = session.query(CategoryAttributeTemplateORM).filter(
                CategoryAttributeTemplateORM.category_id == cat.category_id
            ).count()
            if existing > 0:
                print(f"  [SKIP] '{cat_name}' 已有 {existing} 個屬性模板")
                skipped += 1
                continue

            for key, unit, required, sort in attrs:
                template = CategoryAttributeTemplateORM(
                    template_id=uuid.uuid4(),
                    category_id=cat.category_id,
                    attr_key=key,
                    attr_unit=unit,
                    is_required=required,
                    sort_order=sort,
                )
                session.add(template)
                created += 1

        session.commit()
        print(f"\n屬性模板建立完成：新增 {created} 個，跳過 {skipped} 個分類")
    finally:
        session.close()


if __name__ == "__main__":
    seed()