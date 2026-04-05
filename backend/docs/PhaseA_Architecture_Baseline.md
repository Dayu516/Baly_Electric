# Phase A Architecture Baseline

本文件記錄 Phase A 架構的最終狀態，作為正式基線（frozen baseline）。

## 架構層次

```
API Route（HTTP 轉接）
  ↓
Use Case（流程編排：audit + commit + post-commit）
  ↓
Application Service（業務邏輯 + repo 呼叫）
  ↓
Domain（models + rules + repository 介面）
  ↓
Infrastructure（repo 實作 + query service + ORM）
```

## 五核心模組

| 模組 | 入口 | 抽象 | 讀寫分離 | 測試 | 說明 | 狀態 |
|------|------|------|---------|------|------|------|
| Procurement | ✅ | ✅ | ✅ | 43u+30i | ✅ | 通過 |
| Sales | ✅ | ✅ | ✅ | 61u+23i | ✅ | 通過 |
| Inventory | ✅ | ✅ | ✅ | 23u+12i | ✅ | 通過 |
| Product | ✅ | ✅ | ✅ | 37u+12i | ✅ | 通過 |
| Customer | ✅ | ✅ | ✅ | 13u+10i | ✅ | 通過 |

## Use Case 層

| Use Case | 流程 | 主要功能 |
|----------|------|---------|
| ReceivePurchaseOrderUseCase | PO 收貨 | idempotency + over-receive 防護 + 同日覆蓋 + low stock resolve |
| ImportCatalogUseCase | 資料匯入 | batch_id + upsert + review 分級 |
| DeactivateImportBatchUseCase | 批次停用 | batch-created 資料停用 |
| CheckoutUseCase | 結帳 | audit + low stock alert 去重 |
| VoidSaleUseCase | 作廢 | audit + commit |
| GenerateStatementUseCase | 月結生成 | audit + ReviewTask |
| RecordPaymentUseCase | 收款 | audit + 全額付清自動結案 ReviewTask |

## CI Guardrails

| 護欄 | 工具 | 模式 |
|------|------|------|
| domain-no-external | import-linter | FAIL |
| domain-no-infra | import-linter | FAIL |
| api-no-infra | import-linter | FAIL |
| application-no-api | import-linter | FAIL |
| infra-no-upward | import-linter | FAIL |
| api-no-orm | test_architecture.py | FAIL |
| application-no-sql | test_architecture.py | FAIL |
| write-routes-have-audit | test_architecture.py | FAIL |
| use-case-has-audit-commit | test_architecture.py | FAIL |
| ruff lint | CI job | FAIL |
| migration 可逆 | CI job | FAIL |

## CI Pipeline

```
static-guard → unit-tests → integration-tests
                          → migration-smoke
```

4 jobs，全 FAIL 模式。

## Constitution Gap 狀態

| Gap | 狀態 |
|-----|------|
| Patch 1（5 項） | ✅ 完成 |
| Patch 2（4 項） | ✅ 完成 |
| api-no-infra 34 處 | ✅ 全清 |
| 35 處寫入 route audit | ✅ 全補 |

## 已知保留到 Phase B 的項目

| 項目 | 說明 |
|------|------|
| CorrectReceiveUseCase | 隔日修正收貨（介面已定） |
| Import dry_run 預覽 | 匯入前預覽（介面已定） |
| AR 逾期自動標記 | scheduled job |
| AR 折讓 / 退款 | 新 use case |
| Low stock alert read_status / resolution_status 拆分 | 目前沿用 is_read |
| Backorder 通知正式狀態欄位 | DB + use case |
| Event bus / saga | Phase B 才考慮 |
