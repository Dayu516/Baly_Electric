# Procurement 模組維護說明

## 組裝入口

`application/procurement/__init__.py`

```python
from application.procurement import build_po_service, build_inquiry_service, build_quotation_service
svc = build_po_service(session)
```

API 層只透過這 3 個 builder 建立 service，不可自行組裝 repo。

## Service 清單

| Service | 檔案 | 職責 |
|---------|------|------|
| `PurchaseOrderService` | `purchase_order_service.py` | 採購單 CRUD + 驗收 + 一鍵補貨 |
| `InquiryService` | `inquiry_service.py` | 詢價單流程 + 報價 + 選取 + 轉 PO |
| `QuotationService` | `quotation_service.py` | 報價單流程 + 轉銷貨結帳 |

所有 service 只依賴抽象 repository，不碰 Session / ORM / raw SQL。

## Repository 介面

定義在 `domain/procurement/repository.py`：

| 介面 | 方法 |
|------|------|
| `PurchaseOrderRepository` | get_by_id, save, delete |
| `PurchaseOrderLineRepository` | get_by_id, save, delete_by_po |
| `PurchaseReceiptRepository` | save |
| `PurchaseReceiptLineRepository` | save |
| `InquiryRepository` | get_by_id, save, delete |
| `InquiryLineRepository` | get_by_id, save |
| `InquiryQuoteRepository` | save |
| `QuotationRepository` | get_by_id, save, delete |
| `QuotationLineRepository` | save |
| `SupplierPriceQuoteRepository` | save |

Concrete 實作在 `infrastructure/persistence/repositories/procurement_repo_impl.py`。

跨模組 repo（已有，沿用）：
- `StockMovementRepository` / `InventoryBalanceRepository`（庫存）
- `SaleRepository`（銷貨）

## QueryService 責任

`infrastructure/persistence/query_services/procurement_query_service.py`

只做讀取，不做寫入：
- 列表查詢（PO / Inquiry / Quotation）+ keyword/date 篩選
- 明細查詢（lines + quotes）
- PO line quantities（判斷驗收狀態）
- 低庫存品項（一鍵補貨用）
- 詢價選取/取消選取（SQL update，但屬於查詢輔助操作）

## 純邏輯（可獨立 unit test）

集中在 `application/procurement/rules.py`：

| 函數 | 用途 |
|------|------|
| `group_by_supplier(items)` | 按供應商 ID 分組（一鍵建 PO / 詢價轉 PO） |
| `calculate_subtotal(lines)` | 報價明細計算未稅小計 |
| `build_sale_lines_from_quotation(sale_id, lines)` | 報價明細 → SaleLine domain objects |
| `determine_payment_method(customer_id)` | 有客戶 = 月結，無客戶 = 現金 |

## 測試結構

### Unit tests（`tests/unit/`，不需要 DB，0.08s）

| 檔案 | 測試數 | 覆蓋 |
|------|--------|------|
| `test_purchase_order_service.py` | 14 | 建單/確認/取消/刪除/驗收/分組 |
| `test_inquiry_service.py` | 15 | 建單/加品項/報價/選取/轉PO/取消/刪除/分組 |
| `test_quotation_service.py` | 16 | 建單/狀態轉換/加品項/轉銷貨/刪除/小計計算/SaleLine建立 |

### Integration tests（`tests/integration/`，需要 DB，0.5s）

| 檔案 | 測試數 | 覆蓋 |
|------|--------|------|
| `test_purchase_order_service.py` | 17 | 真 DB 驗收 + 庫存更新 + PO 狀態推導 |
| `test_inquiry_service.py` | 6 | 完整詢價流程 + 轉 PO |
| `test_quotation_service.py` | 7 | 完整報價流程 + 轉銷貨 + 庫存扣減 |

### 何時用 unit test vs integration test

- **業務規則**（狀態檢查、拒絕邏輯、純計算）→ unit test
- **跨表 transaction**（驗收入庫、轉銷貨扣庫存）→ integration test
- **QueryService SQL 查詢正確性** → integration test
