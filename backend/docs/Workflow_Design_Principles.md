# Workflow Design Principles

## Phase A 決策

- 不採用重型 workflow / saga / event bus framework
- 採用輕量 Use Case 層（`application/use_cases/`）
- 原有 Service 下沉為可重用的業務邏輯層
- API Route 只做 HTTP 轉接

## 流程正式化判斷標準

一個流程應建立正式 Use Case，當它符合以下任一條件：

1. 是正式業務流程（非純 CRUD）
2. 跨多模組 / 多聚合根
3. 同時涉及 transaction + audit + alert/review + compensation
4. 未來可能有多入口（API / batch / job / LINE / internal trigger）

## Transaction 邊界原則

- Transaction commit 在 Use Case 內
- 主要寫入在 transaction 內
- Alert / 通知在 commit 後（best-effort）
- Post-commit 操作必須 try/except，不可回滾主交易

## Post-Commit Side Effects 模式

```python
# 在 use case execute() 末尾
try:
    self._do_side_effect()
except Exception:
    logger.warning("side_effect_failed", exc_info=True)
```

Side effects 包含：
- Low stock alert 建立 / resolve
- Backorder 通知
- 進價異常 alert

## Idempotency 模式

| 流程 | 機制 |
|------|------|
| Checkout | client_tx_id（service 內部處理） |
| PO Receive | receipt idempotency_key（use case 層 + 同日覆蓋） |
| Statement Generate | customer_id + period（service 層防重複） |
| Product Import | batch_id + 跨批次 DB 去重 |

## Low Stock Alert 生命週期

```
結帳後 current_stock <= min_stock
  → 檢查 active alert（同 SKU + low_stock + is_read=false）
  → 有 → 不重建
  → 無 → 建立新 alert

進貨後 current_stock > min_stock
  → 找 active alert → is_read = true（resolve）

再次跌破 → 建立新 alert
```

NOTE: Phase B 應拆分 read_status 與 resolution_status。

## Phase B 觸發條件

以下場景出現時，考慮升級 workflow 機制：
- 需要跨 service 的 saga
- Event bus 引入後需要 handler orchestration
- 離線同步衝突需要 compensating transaction
- LINE webhook 觸發業務流程
