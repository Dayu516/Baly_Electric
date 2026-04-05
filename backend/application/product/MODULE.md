# Product 模組維護說明

## 組裝入口

`application/product/__init__.py`

```python
from application.product import build_bom_service, build_category_service, build_attribute_service
svc = build_bom_service(session)
```

API 層只透過 7 個 builder 建立 service，不可自行組裝 repo。

## Service 清單

| Service | 檔案 | 職責 |
|---------|------|------|
| `BomService` | `bom_service.py` | BOM 組成管理（全量覆蓋 + item_type 變更驗證） |
| `SearchProductService` | `search_service.py` | 品項搜尋（純讀取，委派 QueryService） |
| `ImportCatalogService` | `import_catalog_service.py` | CSV 匯入（解析 + 去重 + 建 Product/SKU + ReviewTask） |
| `CategoryService` | `category_service.py` | 分類刪除（遞迴子孫 + 品項檢查 + 批次刪除） |
| `AttributeService` | `attribute_service.py` | 分類模板 / 品項屬性全量覆蓋 |
| `SupplierPriceService` | `supplier_price_service.py` | 供應商報價記錄 + 成本更新 |
| `AliasService` | `alias_service.py` | 品項別名新增 / 刪除 |

所有 service 只依賴抽象 repository，不碰 Session / ORM / raw SQL。

## Repository 介面

定義在 `domain/product/repository.py`：

| 介面 | 方法 |
|------|------|
| `ProductRepository` | get_by_id, save, delete, list_products |
| `SKURepository` | get_by_id, get_by_barcode, save, list_by_product |
| `CategoryRepository` | get_by_id, save, list_all, delete_batch_with_templates |
| `BomRepository` | replace_children, has_children, is_child |
| `ProductAliasRepository` | save, get_by_id, delete |
| `SupplierPriceQuoteRepository` | save |
| `CategoryAttributeTemplateRepository` | replace_for_category |
| `ProductAttributeRepository` | replace_for_product |

Concrete 實作在 `infrastructure/persistence/repositories/product_repo_impl.py`。

跨模組 repo（沿用）：
- `InventoryBalanceRepository`（庫存）— 建 SKU 時 ensure_exists
- `ReviewTaskRepository`（審核）— 匯入後建 ReviewTask

## QueryService 責任

`infrastructure/persistence/query_services/product_query_service.py`

只做讀取，不做寫入：
- 品項搜尋（多欄位 ILIKE）
- SKU 詳情 / 供應商列表 / 別名列表
- BOM 查詢（children / parents / assembly hint）
- 替代品推薦（屬性匹配演算法）
- 分類遞迴查詢 / 品項數量統計

`infrastructure/persistence/query_services/attribute_query_service.py`
- 分類模板查詢 / 品項屬性查詢
- 搜尋文字更新（匯入用）

## 測試結構

### Unit tests（`tests/unit/`，不需要 DB）

| 檔案 | 測試數 | 覆蓋 |
|------|--------|------|
| `test_bom_service.py` | 11 | save/replace BOM、非 assembly 拒絕、child 不存在、item_type 變更驗證 |
| `test_import_catalog_service.py` | 8 | CSV 解析、去重、條碼重複、item_type、ReviewTask |
| `test_category_service.py` | 5 | 遞迴刪除、有品項拒絕、正常刪除 |
| `test_attribute_service.py` | 4 | 模板/屬性全量覆蓋、空列表 |
| `test_supplier_price_service.py` | 4 | 正常報價、SKU 不屬於品項、供應商不存在 |
| `test_alias_service.py` | 5 | 建立/刪除別名、不存在、錯誤 product |

### Integration tests（`tests/integration/`，需要 DB）

| 檔案 | 測試數 | 覆蓋 |
|------|--------|------|
| `test_product_integration.py` | 12 | Product/SKU CRUD、BOM save/replace、Alias CRUD、屬性覆蓋、報價寫入、分類刪除 |

### 何時用 unit test vs integration test

- **Service 驗證邏輯**（BOM 規則、去重、分類檢查）→ unit test
- **DB 寫入一致性**（BOM replace、屬性覆蓋、報價記錄）→ integration test
- **跨表操作**（分類批次刪除 + 模板連帶刪除）→ integration test
