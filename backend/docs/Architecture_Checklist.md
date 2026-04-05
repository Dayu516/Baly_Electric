# Architecture Checklist

本文件用於 code review 與新功能開發時的固定檢查。
搭配 `tests/test_architecture.py` 的自動化護欄使用。

---

## A. 高風險操作 Checklist

以下操作必須逐項確認：

**適用範圍：** 結帳、作廢、進貨驗收、盤點調整、月結生成、收款、匯入、報價轉銷貨、刪除

| # | 檢查項 | 說明 |
|---|--------|------|
| 1 | `require_role` | 每個 route 必須有權限檢查 |
| 2 | `AuditService.log()` | 寫入操作必須在 `session.commit()` 前記 audit |
| 3 | Transaction 內/外分清 | 主要寫入在 transaction 內；alert / 通知在 commit 後 |
| 4 | Post-commit side effect 不回滾主交易 | best-effort 必須 try/except |
| 5 | Integration test | 每個 use case 至少一個真 DB 測試 |

---

## B. 新模組 / 新 Use Case Checklist

| # | 檢查項 | 說明 |
|---|--------|------|
| 1 | 單一組裝入口 | `application/<module>/__init__.py` 有 builder |
| 2 | Service 不碰 Session / ORM / raw SQL | 只依賴抽象 repository |
| 3 | QueryService 只讀 | 不做 INSERT / UPDATE / DELETE |
| 4 | Repository 負責寫 | domain 定義介面，infrastructure 實作 |
| 5 | MODULE.md | 維護說明（service 清單、repo 清單、測試結構） |
| 6 | Unit tests | 業務規則 + 拒絕邏輯 |
| 7 | Integration tests | transaction 行為 + DB 一致性 |

---

## C. Import 邊界規則（自動化，`tests/test_architecture.py`）

| 規則 | 檢查 | 模式 |
|------|------|------|
| `domain-no-external` | domain/ 不可 import sqlalchemy, fastapi, openai 等 | **FAIL** |
| `domain-no-infra` | domain/ 不可 import infrastructure/ | **FAIL** |
| `application-no-api` | application/ 不可 import api/ | **FAIL** |
| `infra-no-upward` | infrastructure/ 不可 import application/ 或 api/ | **FAIL** |
| `api-no-orm` | api/ 不可直接 import orm_models | **FAIL** |
| `application-no-sql` | application/ service 不可 import sqlalchemy（builder 除外） | **FAIL** |

---

## D. 已知合法例外

| 位置 | import | 理由 |
|------|--------|------|
| `application/<module>/__init__.py` | `from sqlalchemy.orm import Session` | builder 型別註記 |
| `application/<module>/__init__.py` | `from infrastructure...` re-export | builder 橋接層 |
| `inventory_repo_impl.py` | raw SQL `UPDATE ... current_stock + :qty` | Constitution §9 架構例外 |

---

## E. Audit 覆蓋狀態

✅ **全部寫入 route 已補齊 audit（2026-04-05）**

自動檢查：`test_architecture.py::TestWriteRoutesHaveAudit`
- 掃描所有 `@router.post/put/delete` + `session.commit()` 的 route
- 必須有 `build_audit_service` 呼叫
- 豁免：`login`（非業務寫入）
