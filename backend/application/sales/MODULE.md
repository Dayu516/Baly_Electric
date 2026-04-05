# Sales 模組維護說明

## 組裝入口

`application/sales/__init__.py`

```python
from application.sales import build_checkout_service, build_void_sale_service, build_backorder_service
svc = build_checkout_service(session)
```

API 層只透過這 3 個 builder 建立 service，不可自行組裝 repo。

## Service 清單

| Service | 檔案 | 職責 |
|---------|------|------|
| `CheckoutService` | `checkout_service.py` | POS 結帳（建 sale + lines + 庫存扣減 + 月結累計 + 售價記錄） |
| `VoidSaleService` | `void_sale_service.py` | 作廢交易（庫存退回 + AR 扣減） |
| `BackorderService` | `backorder_service.py` | 欠貨全生命週期（建立/綁PO/到貨/補交/通知/取消） |

所有 service 只依賴抽象 repository，不碰 Session / ORM / raw SQL。

## Repository 介面

定義在 `domain/sales/repository.py`：

| 介面 | 方法 |
|------|------|
| `SaleRepository` | get_by_id, save, save_lines, get_by_client_tx_id, delete_with_children |
| `SaleLineRepository` | get_by_id, save, list_by_sale_id |
| `SaleLineFulfillmentRepository` | save, list_by_sale_line_id, list_by_sale_line_and_source |
| `CustomerPickupNotificationRepository` | save |
| `CustomerPriceHistoryRepository` | upsert |

Concrete 實作在 `infrastructure/persistence/repositories/sales_repo_impl.py`。

跨模組 repo（已有，沿用）：
- `StockMovementRepository` / `InventoryBalanceRepository`（庫存）
- `AccountsReceivableRepository` / `CustomerRepository`（客戶）
- `OperationalAlertRepository`（告警，BackorderService 到貨通知用，best-effort）

## QueryService 責任

`infrastructure/persistence/query_services/sales_query_service.py`

只做讀取，不做寫入：
- 客戶歷史售價查詢
- 銷售紀錄列表 + keyword/date 篩選
- 銷售明細查詢
- 月結彙總
- 應收帳款列表
- 出貨單查詢（receipt）
- 客戶資訊查詢

## 純邏輯（可獨立 unit test）

集中在 `application/sales/rules.py`：

| 函數 | 用途 |
|------|------|
| `derive_fulfillment_status(line)` | 從 qty 欄位推導履約狀態 |
| `derive_backorder_status(line)` | 從 qty 欄位推導欠貨狀態 |
| `update_line_statuses(line)` | 一次推導兩個狀態 |
| `derive_has_backorder(lines)` | sale 層級快取推導 |
| `calculate_line_total(price, qty, discount)` | 單行明細金額 |
| `calculate_tax(amount, tax_mode)` | 稅額計算三模式（none/included/extra） |
| `build_sale_lines(sale_id, items)` | CartItem → SaleLine domain objects |

## 測試結構

### Unit tests（`tests/unit/`，不需要 DB）

| 檔案 | 測試數 | 覆蓋 |
|------|--------|------|
| `test_sales_rules.py` | 22 | 全部純邏輯函數的各路徑 |
| `test_checkout_service.py` | 11 | 結帳/冪等/月結/售價記錄/稅額 |
| `test_void_sale_service.py` | 8 | 作廢/重複擋住/庫存退回/月結退款 |
| `test_backorder_service.py` | 20 | 建欠貨/綁PO/到貨/補交/通知/取消/alert建立/alert失敗不回滾 |

### Integration tests（`tests/integration/`，需要 DB）

| 檔案 | 測試數 | 覆蓋 |
|------|--------|------|
| `test_checkout_integration.py` | 7 | 真 DB 結帳 + 庫存扣減 + 冪等 + 月結 + 稅 + 售價記錄 |
| `test_void_integration.py` | 5 | 真 DB 作廢 + 庫存退回 + 重複擋住 + AR 扣減 |
| `test_backorder_integration.py` | 8 | 全流程 + 補交出庫 + 通知 + 取消 |
| `test_sale_deletion_integration.py` | 3 | 子表全清 + 不影響其他交易 + movements 不刪 |

### 何時用 unit test vs integration test

- **業務規則**（狀態推導、金額計算、拒絕邏輯）→ unit test
- **跨表 transaction**（結帳入庫、作廢退庫、補交出庫）→ integration test
- **QueryService SQL 查詢正確性** → integration test
- **刪除一致性** → integration test
