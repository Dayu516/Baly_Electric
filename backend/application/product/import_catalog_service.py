"""凌越資料匯入 — ImportCatalogService。

職責：
  1. 讀取 CSV
  2. 格式清理（全半形統一、去空白、欄位正規化）
  3. 去重偵測（批次內 + 跨批次 DB 級）
  4. 新 SKU → INSERT，既有 SKU → upsert（安全欄位自動更新）
  5. sell_price / name / item_type 變更 → 不直接寫，記到 review changes
  6. category_path 解析 → 對應 category_id
  7. item_type 傳遞到 SKU
  8. structured_attrs → 批次寫入 product_attributes
  9. 回傳 ImportResult（含 review_changes）

注意：此 service 不做 audit / commit（由 use case 層負責）。
"""

import csv
import io
import json
import uuid
from dataclasses import dataclass, field
from uuid import UUID

from core.logging import get_logger
from core.results import Result
from domain.product.models import Category, Product, SKU
from domain.product.repository import CategoryRepository, ProductRepository, SKURepository
from domain.review.models import ReviewTask
from domain.review.repository import ReviewTaskRepository

logger = get_logger("import_catalog")

VALID_ITEM_TYPES = {"finished", "assembly", "accessory", "component"}

# 可自動更新的欄位（不需 review）
AUTO_UPDATE_FIELDS = {"cost_price", "supplier_code", "internal_code", "min_stock",
                      "raw_name", "series", "model_number"}

# 需要 review 才能更新的欄位
REVIEW_REQUIRED_FIELDS = {"sell_price", "name", "item_type"}


@dataclass
class ImportRow:
    """匯入檔的單行資料。支援 data-cleaner 清洗後的標準 CSV。"""
    name: str = ""
    raw_name: str | None = None
    brand: str | None = None
    series: str | None = None
    model_number: str | None = None
    category_name: str | None = None
    category_path: str | None = None
    spec: str | None = None
    barcode: str | None = None
    supplier_code: str | None = None
    internal_code: str | None = None
    unit: str = "個"
    sell_price: float = 0
    cost_price: float | None = None
    min_stock: int | None = None
    item_type: str = "finished"
    structured_attrs: dict | None = None


@dataclass
class ImportResult:
    total_rows: int = 0
    imported: int = 0
    updated: int = 0
    skipped_duplicate: int = 0
    review_changes: list[dict] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class ImportCatalogService:
    def __init__(
        self,
        product_repo: ProductRepository,
        sku_repo: SKURepository,
        review_repo: ReviewTaskRepository,
        category_repo: CategoryRepository | None = None,
        attribute_writer=None,
        product_query=None,  # ProductQueryService for cross-batch dedup
    ):
        self._product_repo = product_repo
        self._sku_repo = sku_repo
        self._review_repo = review_repo
        self._category_repo = category_repo
        self._attr_writer = attribute_writer
        self._product_query = product_query
        self._category_cache: dict[str, uuid.UUID | None] = {}

    def import_csv(self, csv_content: str, created_by: uuid.UUID, batch_id: uuid.UUID | None = None) -> Result:
        """從 CSV 字串匯入品項。batch_id 由 use case 提供。"""
        rows = self._parse_csv(csv_content)
        if not rows:
            return Result.fail("ERR-BIZ-001", "CSV 無有效資料")

        result = self._process_rows(rows, created_by, batch_id)

        logger.info(
            "import_completed",
            total=result.total_rows,
            imported=result.imported,
            updated=result.updated,
            skipped=result.skipped_duplicate,
            review_changes=len(result.review_changes),
            errors=len(result.errors),
        )

        return Result.ok(
            data={
                "import_batch_id": str(batch_id) if batch_id else None,
                "total_rows": result.total_rows,
                "imported": result.imported,
                "updated": result.updated,
                "skipped_duplicate": result.skipped_duplicate,
                "review_changes": result.review_changes[:20],
                "errors": result.errors[:20],
            },
            message=f"匯入完成：新增 {result.imported} / 更新 {result.updated} / 跳過 {result.skipped_duplicate}",
        )

    def _parse_csv(self, csv_content: str) -> list[ImportRow]:
        rows: list[ImportRow] = []
        reader = csv.DictReader(io.StringIO(csv_content))

        for raw in reader:
            try:
                raw_name = self._clean(raw.get("原始品名", raw.get("raw_name")))
                name = self._clean(raw.get("品名", raw.get("name", "")))
                row = ImportRow(
                    name=name or raw_name or "",
                    raw_name=raw_name or name,
                    brand=self._clean(raw.get("廠牌", raw.get("brand"))),
                    series=self._clean(raw.get("系列", raw.get("series"))),
                    model_number=self._clean(raw.get("型號", raw.get("model_number"))),
                    category_name=self._clean(raw.get("分類", raw.get("category"))),
                    spec=self._clean(raw.get("規格", raw.get("spec"))),
                    barcode=self._clean(raw.get("條碼", raw.get("barcode"))),
                    supplier_code=self._clean(raw.get("供應商料號", raw.get("supplier_code"))),
                    internal_code=self._clean(raw.get("內部編號", raw.get("internal_code"))),
                    unit=self._clean(raw.get("單位", raw.get("unit"))) or "個",
                    sell_price=self._to_float(raw.get("售價", raw.get("sell_price", "0"))),
                    cost_price=self._to_float(raw.get("成本", raw.get("cost_price"))),
                    min_stock=self._to_int(raw.get("安全庫存", raw.get("min_stock"))),
                    item_type=self._parse_item_type(raw.get("品項型態", raw.get("item_type"))),
                    category_path=self._clean(raw.get("分類路徑", raw.get("category_path"))),
                    structured_attrs=self._parse_json(raw.get("結構化屬性", raw.get("structured_attrs"))),
                )
                if row.name:
                    rows.append(row)
            except Exception:
                continue

        return rows

    def _process_rows(self, rows: list[ImportRow], created_by: uuid.UUID, batch_id: uuid.UUID | None) -> ImportResult:
        result = ImportResult(total_rows=len(rows))
        seen_products: dict[str, uuid.UUID] = {}
        seen_skus: set[str] = set()

        for i, row in enumerate(rows):
            try:
                product_key = f"{row.name}|{row.spec or ''}"
                sku_key = f"{row.name}|{row.spec or ''}|{row.brand or ''}"

                # 批次內去重
                if sku_key in seen_skus:
                    result.skipped_duplicate += 1
                    continue
                seen_skus.add(sku_key)

                # 條碼去重
                if row.barcode:
                    existing_sku = self._sku_repo.get_by_barcode(row.barcode)
                    if existing_sku:
                        # 既有 SKU（by barcode） → upsert
                        self._upsert_existing_sku(existing_sku, row, result, i)
                        continue

                # 跨批次 DB 級去重（name + spec + brand）
                if self._product_query:
                    existing = self._product_query.find_existing_sku(row.name, row.spec, row.brand)
                    if existing:
                        sku = self._sku_repo.get_by_id(existing["sku_id"])
                        if sku:
                            self._upsert_existing_sku(sku, row, result, i)
                            continue

                # ── 新資料 INSERT ──────────────────────────
                category_id = self._resolve_category(row.category_path, row.category_name)

                if product_key in seen_products:
                    product_id = seen_products[product_key]
                else:
                    product = Product(
                        name=row.name,
                        raw_name=row.raw_name,
                        series=row.series,
                        model_number=row.model_number,
                        category_id=category_id,
                        source_batch_id=batch_id,
                    )
                    saved_product = self._product_repo.save(product)
                    product_id = saved_product.product_id
                    seen_products[product_key] = product_id

                sku = SKU(
                    product_id=product_id,
                    brand=row.brand,
                    barcode=row.barcode,
                    supplier_code=row.supplier_code,
                    internal_code=row.internal_code,
                    spec=row.spec,
                    unit=row.unit,
                    sell_price=row.sell_price,
                    cost_price=row.cost_price,
                    min_stock=row.min_stock,
                    item_type=row.item_type,
                    source_batch_id=batch_id,
                )
                self._sku_repo.save(sku)

                # structured_attrs
                if row.structured_attrs and self._attr_writer:
                    self._write_product_attributes(product_id, row.structured_attrs)

                # search_text 增強
                if self._attr_writer:
                    extra = [row.brand]
                    if row.structured_attrs:
                        extra.extend(str(v) for v in row.structured_attrs.values() if v)
                    self._attr_writer.update_search_text(str(product_id), extra)

                result.imported += 1

            except Exception as e:
                result.errors.append(f"第 {i+1} 行「{row.name}」匯入失敗：{e}")

        # 建立 ReviewTask
        if result.imported > 0 or result.updated > 0 or result.review_changes:
            review_detail = f"新增 {result.imported} / 更新 {result.updated} / 跳過 {result.skipped_duplicate}"
            if result.review_changes:
                review_detail += f"\n\n需確認的變更（{len(result.review_changes)} 筆）：\n"
                for ch in result.review_changes[:10]:
                    review_detail += f"  SKU {ch['sku_id']}: {ch['field']} {ch['old']} → {ch['new']}\n"

            review = ReviewTask(
                review_type="product_confirm",
                title=f"匯入 {result.imported + result.updated} 筆品項待確認",
                detail=review_detail,
                reference_type="import_batch",
                reference_id=batch_id,
            )
            self._review_repo.save(review)

        return result

    def _upsert_existing_sku(self, sku: SKU, row: ImportRow, result: ImportResult, row_idx: int) -> None:
        """更新既有 SKU：安全欄位自動更新，敏感欄位記到 review_changes。"""
        changed = False

        # 安全欄位自動更新
        if row.cost_price is not None and row.cost_price != sku.cost_price:
            sku.cost_price = row.cost_price
            changed = True
        if row.supplier_code and row.supplier_code != sku.supplier_code:
            sku.supplier_code = row.supplier_code
            changed = True
        if row.internal_code and row.internal_code != sku.internal_code:
            sku.internal_code = row.internal_code
            changed = True
        if row.min_stock is not None and row.min_stock != sku.min_stock:
            sku.min_stock = row.min_stock
            changed = True

        # 敏感欄位 → 不直接寫，記到 review_changes
        if row.sell_price and row.sell_price != sku.sell_price:
            result.review_changes.append({
                "sku_id": str(sku.sku_id),
                "field": "sell_price",
                "old": sku.sell_price,
                "new": row.sell_price,
                "row": row_idx + 1,
            })
        if row.item_type != sku.item_type:
            result.review_changes.append({
                "sku_id": str(sku.sku_id),
                "field": "item_type",
                "old": sku.item_type,
                "new": row.item_type,
                "row": row_idx + 1,
            })

        if changed:
            self._sku_repo.save(sku)
            result.updated += 1
        else:
            result.skipped_duplicate += 1

    @staticmethod
    def _clean(value: str | None) -> str | None:
        if value is None:
            return None
        result = value.strip()
        result = result.replace("\u3000", " ")
        result = result.replace("\uff0c", ",")
        return result if result else None

    @staticmethod
    def _to_float(value: str | None) -> float:
        if not value:
            return 0
        try:
            return float(str(value).strip().replace(",", ""))
        except (ValueError, TypeError):
            return 0

    @staticmethod
    def _to_int(value: str | None) -> int | None:
        if not value:
            return None
        try:
            return int(float(str(value).strip().replace(",", "")))
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _parse_item_type(value: str | None) -> str:
        if not value:
            return "finished"
        cleaned = value.strip().lower()
        return cleaned if cleaned in VALID_ITEM_TYPES else "finished"

    @staticmethod
    def _parse_json(value: str | None) -> dict | None:
        if not value or not value.strip():
            return None
        try:
            parsed = json.loads(value.strip())
            return parsed if isinstance(parsed, dict) else None
        except (json.JSONDecodeError, TypeError):
            return None

    def _resolve_category(self, category_path: str | None, category_name: str | None) -> uuid.UUID | None:
        path = category_path or category_name
        if not path or not self._category_repo:
            return None
        if path in self._category_cache:
            return self._category_cache[path]
        if not self._category_cache:
            self._build_category_cache()
        return self._category_cache.get(path)

    def _build_category_cache(self) -> None:
        all_cats = self._category_repo.list_all()
        by_id: dict[uuid.UUID, Category] = {c.category_id: c for c in all_cats}
        for cat in all_cats:
            if cat.parent_id and cat.parent_id in by_id:
                parent = by_id[cat.parent_id]
                self._category_cache[f"{parent.name}>{cat.name}"] = cat.category_id
            self._category_cache[cat.name] = cat.category_id

    def _write_product_attributes(self, product_id: uuid.UUID, attrs: dict) -> None:
        self._attr_writer.bulk_insert_product_attributes(str(product_id), attrs)
