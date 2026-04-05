"""凌越資料匯入 — ImportCatalogService。

職責：
  1. 讀取 CSV/Excel
  2. 格式清理（全半形統一、去空白、欄位正規化）
  3. 去重偵測（同品名+同規格 = 疑似重複）
  4. 拆 Product / SKU
  5. category_path 解析 → 對應 category_id
  6. item_type 傳遞到 SKU
  7. structured_attrs → 批次寫入 product_attributes
  8. 匯入結果建立 ReviewTask（product_confirm）
"""

import csv
import io
import json
import uuid
from dataclasses import dataclass, field

from core.logging import get_logger
from core.results import Result
from domain.product.models import Category, Product, SKU
from domain.product.repository import CategoryRepository, ProductRepository, SKURepository
from domain.review.models import ReviewTask
from domain.review.repository import ReviewTaskRepository

logger = get_logger("import_catalog")

VALID_ITEM_TYPES = {"finished", "assembly", "accessory", "component"}


@dataclass
class ImportRow:
    """匯入檔的單行資料。支援 data-cleaner 清洗後的標準 CSV。"""
    name: str = ""                          # 標準化品名（清洗後）
    raw_name: str | None = None             # 原始品名（保留底）
    brand: str | None = None
    series: str | None = None               # 系列
    model_number: str | None = None
    category_name: str | None = None
    category_path: str | None = None        # 分類路徑（如「接觸器類>裸接觸器」）
    spec: str | None = None
    barcode: str | None = None
    supplier_code: str | None = None        # 供應商料號
    internal_code: str | None = None        # 凌越原始編號
    unit: str = "個"
    sell_price: float = 0
    cost_price: float | None = None
    min_stock: int | None = None
    item_type: str = "finished"             # finished/assembly/accessory/component
    structured_attrs: dict | None = None    # {"線圈電壓":"AC220V","框架型號":"S-P11"}


@dataclass
class ImportResult:
    total_rows: int = 0
    imported: int = 0
    skipped_duplicate: int = 0
    errors: list[str] = field(default_factory=list)


class ImportCatalogService:
    def __init__(
        self,
        product_repo: ProductRepository,
        sku_repo: SKURepository,
        review_repo: ReviewTaskRepository,
        category_repo: CategoryRepository | None = None,
        attribute_writer=None,  # AttributeQueryService instance
    ):
        self._product_repo = product_repo
        self._sku_repo = sku_repo
        self._review_repo = review_repo
        self._category_repo = category_repo
        self._attr_writer = attribute_writer
        self._category_cache: dict[str, uuid.UUID | None] = {}  # path → category_id

    def import_csv(self, csv_content: str, created_by: uuid.UUID) -> Result:
        """從 CSV 字串匯入品項。"""
        rows = self._parse_csv(csv_content)
        if not rows:
            return Result.fail("ERR-BIZ-001", "CSV 無有效資料")

        result = self._process_rows(rows, created_by)

        logger.info(
            "import_completed",
            total=result.total_rows,
            imported=result.imported,
            skipped=result.skipped_duplicate,
            errors=len(result.errors),
        )

        return Result.ok(
            data={
                "total_rows": result.total_rows,
                "imported": result.imported,
                "skipped_duplicate": result.skipped_duplicate,
                "errors": result.errors[:20],  # 最多回傳 20 筆錯誤
            },
            message=f"匯入完成：{result.imported}/{result.total_rows} 筆成功",
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

    def _process_rows(self, rows: list[ImportRow], created_by: uuid.UUID) -> ImportResult:
        result = ImportResult(total_rows=len(rows))
        # 去重追蹤：
        #   product_key (name|spec) → product_id  — 同規格歸同一 Product
        #   sku_key (name|spec|brand) → True       — 同品牌同規格跳過
        seen_products: dict[str, uuid.UUID] = {}
        seen_skus: set[str] = set()

        for i, row in enumerate(rows):
            try:
                product_key = f"{row.name}|{row.spec or ''}"
                sku_key = f"{row.name}|{row.spec or ''}|{row.brand or ''}"

                # SKU 層級去重：name + spec + brand 完全相同 → 跳過
                if sku_key in seen_skus:
                    result.skipped_duplicate += 1
                    continue
                seen_skus.add(sku_key)

                # 條碼去重
                if row.barcode:
                    existing_sku = self._sku_repo.get_by_barcode(row.barcode)
                    if existing_sku:
                        result.skipped_duplicate += 1
                        result.errors.append(f"第 {i+1} 行：條碼 {row.barcode} 已存在，跳過")
                        continue

                # 解析分類路徑 → category_id
                category_id = self._resolve_category(row.category_path, row.category_name)

                # Product 層級：name + spec 相同 → 共用同一個 Product
                if product_key in seen_products:
                    product_id = seen_products[product_key]
                else:
                    product = Product(
                        name=row.name,
                        raw_name=row.raw_name,
                        series=row.series,
                        model_number=row.model_number,
                        category_id=category_id,
                    )
                    saved_product = self._product_repo.save(product)
                    product_id = saved_product.product_id
                    seen_products[product_key] = product_id

                # 建立 SKU（brand 在 SKU 層級，item_type 從 CSV 帶入）
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
                )
                self._sku_repo.save(sku)

                # structured_attrs → 寫入 product_attributes
                if row.structured_attrs and self._attr_writer:
                    self._write_product_attributes(product_id, row.structured_attrs)

                # search_text 增強：brand + structured_attrs 值加入搜尋
                if self._attr_writer:
                    extra = [row.brand]
                    if row.structured_attrs:
                        extra.extend(str(v) for v in row.structured_attrs.values() if v)
                    self._attr_writer.update_search_text(str(product_id), extra)

                result.imported += 1

            except Exception as e:
                result.errors.append(f"第 {i+1} 行「{row.name}」匯入失敗：{e}")

        # 建立 ReviewTask
        if result.imported > 0:
            review = ReviewTask(
                review_type="product_confirm",
                title=f"凌越匯入 {result.imported} 筆品項待確認",
                detail=f"總共 {result.total_rows} 筆，匯入 {result.imported} 筆，重複跳過 {result.skipped_duplicate} 筆",
            )
            self._review_repo.save(review)

        return result

    @staticmethod
    def _clean(value: str | None) -> str | None:
        if value is None:
            return None
        # 全形轉半形（常見字元）
        result = value.strip()
        result = result.replace("\u3000", " ")  # 全形空白
        result = result.replace("\uff0c", ",")  # 全形逗號
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
        """解析分類路徑（如「接觸器類>裸接觸器」）→ category_id。

        優先用 category_path，fallback 到 category_name（舊格式相容）。
        """
        path = category_path or category_name
        if not path or not self._category_repo:
            return None

        # 快取命中
        if path in self._category_cache:
            return self._category_cache[path]

        # 懶載入全部分類（一次查完，不逐行查）
        if not self._category_cache:
            self._build_category_cache()

        result = self._category_cache.get(path)
        return result

    def _build_category_cache(self) -> None:
        """建立分類名稱 → category_id 的快取。

        支援三種查詢格式：
          1. 完整路徑：「接觸器類>裸接觸器」
          2. 子分類名稱：「裸接觸器」
          3. 大分類名稱：「接觸器類」
        """
        all_cats = self._category_repo.list_all()
        # name → Category
        by_id: dict[uuid.UUID, Category] = {c.category_id: c for c in all_cats}
        by_name: dict[str, Category] = {}

        for cat in all_cats:
            by_name[cat.name] = cat

        for cat in all_cats:
            # 建完整路徑：parent_name>child_name
            if cat.parent_id and cat.parent_id in by_id:
                parent = by_id[cat.parent_id]
                full_path = f"{parent.name}>{cat.name}"
                self._category_cache[full_path] = cat.category_id

            # 單名稱也能對應（子分類優先）
            self._category_cache[cat.name] = cat.category_id

    def _write_product_attributes(self, product_id: uuid.UUID, attrs: dict) -> None:
        """將 structured_attrs dict 批次寫入 product_attributes 表。

        使用 AttributeQueryService 做 SQL（遵守 QueryService 分域規則）。
        重複 key 會覆蓋（先刪再寫）。
        """
        self._attr_writer.bulk_insert_product_attributes(str(product_id), attrs)