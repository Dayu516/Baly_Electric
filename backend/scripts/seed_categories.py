"""建立電控材料行標準分類樹。

Usage:
    cd backend
    .venv/Scripts/python.exe -m scripts.seed_categories

可重複執行 — 已存在的分類會跳過。
"""

import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy.orm import Session
from database import SessionLocal
from infrastructure.persistence.orm_models import CategoryORM

# ── 分類定義（name, children）──────────────────────────
CATEGORY_TREE = [
    ("斷路器", 1, [
        ("無熔絲開關 (NFB/BH)", 1, []),
        ("漏電斷路器", 2, []),
        ("配線用斷路器", 3, []),
    ]),
    ("配線器材", 2, [
        ("電線電纜", 1, []),
        ("壓接端子", 2, []),
        ("PVC管/線槽", 3, []),
        ("配線槽/扎帶", 4, []),
    ]),
    ("開關插座", 3, [
        ("開關", 1, []),
        ("插座", 2, []),
        ("蓋板", 3, []),
    ]),
    ("照明", 4, [
        ("LED燈管/燈泡", 1, []),
        ("燈具", 2, []),
        ("安定器/驅動器", 3, []),
    ]),
    ("控制器材", 5, [
        ("接觸器/電磁開關", 1, []),
        ("繼電器", 2, []),
        ("計時器", 3, []),
        ("溫控器", 4, []),
        ("變頻器", 5, []),
    ]),
    ("配電盤/箱體", 6, [
        ("配電箱", 1, []),
        ("開關箱", 2, []),
        ("端子台", 3, []),
    ]),
    ("感測器/偵測器", 7, [
        ("光電感測器", 1, []),
        ("近接開關", 2, []),
        ("煙霧/瓦斯偵測", 3, []),
    ]),
    ("工具/耗材", 8, [
        ("手工具", 1, []),
        ("電動工具", 2, []),
        ("絕緣膠帶", 3, []),
        ("其他耗材", 4, []),
    ]),
    ("其他", 99, []),
]


def seed_categories():
    session: Session = SessionLocal()
    created = 0
    skipped = 0

    try:
        for name, sort_order, children in CATEGORY_TREE:
            parent = _ensure_category(session, name, None, sort_order)
            if parent == "exists":
                skipped += 1
            else:
                created += 1

            parent_id = _get_category_id(session, name)
            for child_name, child_sort, grandchildren in children:
                child = _ensure_category(session, child_name, parent_id, child_sort)
                if child == "exists":
                    skipped += 1
                else:
                    created += 1

                if grandchildren:
                    child_id = _get_category_id_by_parent(session, child_name, parent_id)
                    for gc_name, gc_sort, _ in grandchildren:
                        gc = _ensure_category(session, gc_name, child_id, gc_sort)
                        if gc == "exists":
                            skipped += 1
                        else:
                            created += 1

        session.commit()
        print(f"分類樹建立完成：新增 {created} 筆，跳過 {skipped} 筆")
    finally:
        session.close()


def _ensure_category(session: Session, name: str, parent_id, sort_order: int):
    existing = session.query(CategoryORM).filter(
        CategoryORM.name == name,
        CategoryORM.parent_id == parent_id,
    ).first()
    if existing:
        return "exists"

    cat = CategoryORM(
        category_id=uuid.uuid4(),
        name=name,
        parent_id=parent_id,
        sort_order=sort_order,
    )
    session.add(cat)
    session.flush()
    return cat


def _get_category_id(session: Session, name: str):
    cat = session.query(CategoryORM).filter(
        CategoryORM.name == name,
        CategoryORM.parent_id == None,  # noqa: E711
    ).first()
    return cat.category_id if cat else None


def _get_category_id_by_parent(session: Session, name: str, parent_id):
    cat = session.query(CategoryORM).filter(
        CategoryORM.name == name,
        CategoryORM.parent_id == parent_id,
    ).first()
    return cat.category_id if cat else None


if __name__ == "__main__":
    seed_categories()