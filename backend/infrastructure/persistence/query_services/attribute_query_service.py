"""屬性域查詢服務。"""

import uuid

from sqlalchemy import text

from infrastructure.persistence.orm_models import ProductAttributeORM
from .base import BaseQueryService


class AttributeQueryService(BaseQueryService):

    def get_category_templates(self, category_id: str) -> list[dict]:
        sql = text("""
            SELECT template_id, attr_key, attr_unit, is_required, sort_order,
                   attr_options, match_priority, match_type
            FROM category_attribute_templates
            WHERE category_id = :cat_id
            ORDER BY sort_order
        """)
        rows = self._session.execute(sql, {"cat_id": category_id}).mappings().all()
        return [dict(r) for r in rows]

    def get_product_attributes(self, product_id: str) -> list[dict]:
        sql = text("""
            SELECT attr_id, attr_key, attr_value, attr_unit
            FROM product_attributes
            WHERE product_id = :pid
            ORDER BY attr_key
        """)
        rows = self._session.execute(sql, {"pid": product_id}).mappings().all()
        return [dict(r) for r in rows]

    def delete_category_templates(self, category_id: str) -> None:
        self._session.execute(
            text("DELETE FROM category_attribute_templates WHERE category_id = :cat_id"),
            {"cat_id": category_id},
        )

    def delete_product_attributes(self, product_id: str) -> None:
        self._session.execute(
            text("DELETE FROM product_attributes WHERE product_id = :pid"),
            {"pid": product_id},
        )

    def bulk_insert_product_attributes(self, product_id: str, attrs: dict) -> None:
        """批次寫入品項屬性。attrs = {"線圈電壓":"AC220V","框架型號":"S-P11"}。

        若該 product 已有屬性，會先合併（新 key 新增，舊 key 更新值）。
        """
        existing = {r["attr_key"]: r for r in self.get_product_attributes(product_id)}

        for key, value in attrs.items():
            if not key or not value:
                continue
            val_str = str(value).strip()
            if not val_str:
                continue

            if key in existing:
                # 更新現有屬性值
                self._session.execute(
                    text("UPDATE product_attributes SET attr_value = :val WHERE attr_id = :aid"),
                    {"val": val_str, "aid": str(existing[key]["attr_id"])},
                )
            else:
                self._session.add(ProductAttributeORM(
                    attr_id=uuid.uuid4(),
                    product_id=uuid.UUID(product_id),
                    attr_key=key.strip(),
                    attr_value=val_str,
                    attr_unit=None,
                ))
        self._session.flush()

    def update_search_text(self, product_id: str, extra_terms: list[str]) -> None:
        """把額外搜尋詞彙附加到 product_search_docs.search_text。"""
        if not extra_terms:
            return
        extra = " ".join(t for t in extra_terms if t)
        if not extra:
            return
        self._session.execute(
            text("""
                UPDATE product_search_docs
                SET search_text = search_text || ' ' || :extra
                WHERE product_id = :pid
            """),
            {"pid": product_id, "extra": extra},
        )
        self._session.flush()

    def get_all_category_templates(self) -> list[dict]:
        sql = text("""
            SELECT cat.name as category_name,
                   t.attr_key, t.attr_unit, t.is_required, t.attr_options,
                   t.match_priority, t.match_type
            FROM category_attribute_templates t
            JOIN categories cat ON cat.category_id = t.category_id
            ORDER BY cat.name, t.sort_order
        """)
        rows = self._session.execute(sql).mappings().all()
        return [dict(r) for r in rows]
