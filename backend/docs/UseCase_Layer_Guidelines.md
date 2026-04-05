# Use Case Layer Guidelines

## 定位

Use Case 層是跨模組正式業務流程的唯一承載點。
每個 use case 是一個 class，有一個 `execute()` 方法。

## 責任邊界

| 責任 | Use Case | Service | API Route |
|------|----------|---------|-----------|
| Transaction commit | ✅ | ❌ | ❌ |
| Audit event 建立 | ✅ | ❌ | ❌ |
| Post-commit side effects | ✅ | ❌ | ❌ |
| Idempotency 檢查 | ✅ | ❌ | ❌ |
| Batch identity 生成 | ✅ | ❌ | ❌ |
| 金額 / 數量計算 | ❌ | ✅ | ❌ |
| 狀態推導 | ❌ | ✅ | ❌ |
| Repository 呼叫 | ❌ | ✅ | ❌ |
| HTTP 轉接 | ❌ | ❌ | ✅ |

## 標準 execute() 結構

```python
def execute(self, ..., user_id: UUID) -> Result:
    # 1. Idempotency / validation（如有）
    # 2. 呼叫 service（transaction 內）
    # 3. Audit（transaction 內）
    # 4. Commit
    # 5. Post-commit side effects（best-effort）
    # 6. Return result
```

## 厚度控制

- execute() 不超過 50 行
- 業務邏輯不在 use case 內（下沉到 service / rules）
- use case 只做流程編排

## Audit Payload 規則

每次 audit.log() 必須帶：

| 欄位 | 必填 | 說明 |
|------|------|------|
| user_id | ✅ | 操作者 |
| action | ✅ | 動作名稱（checkout / receive_po / ...） |
| entity_type | ✅ | 對象類型 |
| entity_id | 有對象時 | UUID |
| detail | 高風險操作 | dict，含關鍵差異資訊 |

高風險操作的 detail 要求：

| 操作 | detail 必須包含 |
|------|----------------|
| checkout | sale_id, total, item_count |
| void_sale | reason |
| receive_po | receipt_id |
| record_payment | amount, new_paid |
| import_catalog | import_batch_id, imported, updated |
| update_price | old_price, new_price |

## 自動檢查

- `test_architecture.py::TestUseCaseHasAuditAndCommit`
  - 每個 use case 的 execute() 必須有 `self._audit.log()` 和 `self._session.commit()`

## 現有 Use Cases

| Use Case | 檔案 |
|----------|------|
| ReceivePurchaseOrderUseCase | `use_cases/receive_purchase_order.py` |
| ImportCatalogUseCase | `use_cases/import_catalog.py` |
| DeactivateImportBatchUseCase | `use_cases/import_catalog.py` |
| CheckoutUseCase | `use_cases/checkout.py` |
| VoidSaleUseCase | `use_cases/checkout.py` |
| GenerateStatementUseCase | `use_cases/monthly_statement.py` |
| RecordPaymentUseCase | `use_cases/monthly_statement.py` |
