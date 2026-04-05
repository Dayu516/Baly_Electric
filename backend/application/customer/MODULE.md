# Customer 模組維護說明

## 組裝入口

`application/customer/__init__.py`

```python
from application.customer import build_generate_statement_service, build_payment_service
svc = build_payment_service(session)
```

API 層只透過 builder 建立 service，不可自行組裝 repo。

## Service 清單

| Service | 檔案 | 職責 |
|---------|------|------|
| `GenerateStatementService` | `generate_statement_service.py` | 月結單生成（檢查客戶 + 彙總銷售 + 建 AR + 建 ReviewTask） |
| `PaymentService` | `payment_service.py` | 收款記錄（累計付款金額 + 推導 paid/partial_paid 狀態） |

所有 service 只依賴抽象 repository，不碰 Session / ORM / raw SQL。

## Repository 介面

定義在 `domain/customer/repository.py`：

| 介面 | 方法 |
|------|------|
| `CustomerRepository` | get_by_id, save, list_all |
| `AccountsReceivableRepository` | get_by_id, save, get_by_customer_period |

Concrete 實作在 `infrastructure/persistence/repositories/customer_repo_impl.py`。

跨模組 repo（沿用）：
- `ReviewTaskRepository`（domain/review）— 月結建 ReviewTask

## QueryService 責任

Customer 相關查詢由 `SalesQueryService` 提供（純讀）：
- `sum_customer_sales(customer_id, period)` — 月銷售彙總
- `list_accounts_receivable(customer_id)` — AR 列表
- `get_customer_prices(customer_id, sku_ids)` — 客戶歷史售價
- `get_customer_info(customer_id)` — 客戶基本資訊

這些查詢的是 sales / AR 表的資料，語意上屬於銷售域讀模型，不需搬到獨立 CustomerQueryService。

## 測試結構

### Unit tests（`tests/unit/`，不需要 DB）

| 檔案 | 測試數 | 覆蓋 |
|------|--------|------|
| `test_generate_statement_service.py` | 7 | 正常生成/非月結拒絕/客戶不存在/重複拒絕/零金額/ReviewTask建立/AR欄位 |
| `test_payment_service.py` | 6 | 部分收款/全額收款/累計收款/超額允許/AR不存在/paid_at設定時機 |

### Integration tests（`tests/integration/`，需要 DB）

| 檔案 | 測試數 | 覆蓋 |
|------|--------|------|
| `test_customer_integration.py` | 10 | Customer CRUD/月結生成端到端/重複拒絕/非月結拒絕/ReviewTask/部分收款/全額收款/累計收款 |

### 何時用 unit test vs integration test

- **Service 流程驗證**（狀態推導、拒絕邏輯）→ unit test
- **DB 寫入一致性**（AR 累計、paid_at 設定）→ integration test
- **端到端流程**（生成月結 → 收款 → 結清）→ integration test
