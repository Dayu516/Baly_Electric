# Inventory 模組維護說明

## 組裝入口

`application/inventory/__init__.py`

```python
from application.inventory import build_receive_stock_service, build_stock_count_service, build_stock_recalc_service
svc = build_receive_stock_service(session)
```

API 層只透過這 3 個 builder 建立 service，不可自行組裝 repo。

## Service 清單

| Service | 檔案 | 職責 |
|---------|------|------|
| `ReceiveStockService` | `receive_stock_service.py` | 進貨驗收（建 StockMovement + 更新 InventoryBalance） |
| `StockCountService` | `stock_count_service.py` | 盤點提交（偵測差異 + 建 ReviewTask）+ 盤點調整（建 adjustment movement） |
| `StockRecalcService` | `stock_recalc_service.py` | 庫存重算（SUM movements → 覆寫 balance） |

所有 service 只依賴抽象 repository，不碰 Session / ORM / raw SQL。

## Repository 介面

定義在 `domain/inventory/repository.py`：

| 介面 | 方法 |
|------|------|
| `StockMovementRepository` | save, list_by_sku, list_by_reference |
| `InventoryBalanceRepository` | get_by_sku, atomic_update, ensure_exists, set_stock |

Concrete 實作在 `infrastructure/persistence/repositories/inventory_repo_impl.py`。

`atomic_update` vs `set_stock`：
- `atomic_update(sku_id, qty_delta)` — 增量更新，併發安全，日常入庫/出庫用
- `set_stock(sku_id, stock)` — 絕對值覆寫，僅限重算流程

跨模組 repo（沿用）：
- `ReviewTaskRepository`（domain/review）— 盤點差異建 ReviewTask
- `OperationalAlertRepository`（domain/alert）— 重算異常建 Alert

## QueryService 責任

`infrastructure/persistence/query_services/inventory_query_service.py`

只做讀取，不做寫入：
- `recalc_inventory_balance(sku_id)` — SUM(movements) 算出正確庫存
- `list_inventory(keyword, low_stock_only, ...)` — 庫存總覽 + 搜尋
- `inventory_summary()` — 彙總統計
- `all_inventory_sku_ids()` — 全品項 ID（批次重算用）

## 測試結構

### Unit tests（`tests/unit/`，不需要 DB）

| 檔案 | 測試數 | 覆蓋 |
|------|--------|------|
| `test_receive_stock_service.py` | 8 | 單筆/多筆入庫、空明細/負數拒絕、ensure_exists + atomic_update 呼叫順序 |
| `test_stock_count_service.py` | 10 | 帳實相符/差異偵測/ReviewTask建立、正負差調整、零差不調、note傳遞 |
| `test_stock_recalc_service.py` | 5 | set_stock 呼叫正確、零/負庫存、不碰 _session（架構驗證） |

### Integration tests（`tests/integration/`，需要 DB）

| 檔案 | 測試數 | 覆蓋 |
|------|--------|------|
| `test_inventory_integration.py` | 12 | 入庫累計/ensure_exists冪等/盤點差異偵測/調整寫入/重算修正/重算冪等/完整流程/atomic正確 |

### 何時用 unit test vs integration test

- **Service 流程 + 拒絕邏輯** → unit test
- **DB 寫入一致性 + atomic update** → integration test
- **跨操作流程（入庫→盤點→重算）** → integration test
