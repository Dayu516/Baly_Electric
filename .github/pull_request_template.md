## Summary

<!-- 簡述改了什麼、為什麼改 -->

## Checklist

### 必填（所有 PR）
- [ ] CI 全綠（static-guard + unit-tests + integration-tests + migration-smoke）
- [ ] 不新增 `api/ → infrastructure/` 直接 import
- [ ] 不新增 `application/ → api/` import
- [ ] 不新增 `domain/ → infrastructure/` import

### 寫入操作（所有 POST / PUT / DELETE route）
- [ ] 有 `require_role` 權限檢查
- [ ] 有 `build_audit_service(session).log(...)` 在 `session.commit()` 前
- [ ] Audit payload 包含 user_id / entity_type / entity_id
- [ ] CI audit 檢查通過（`test_architecture.py::TestWriteRoutesHaveAudit`）

### 高風險操作（涉及結帳/作廢/進貨/盤點/月結/收款/匯入/報價轉銷貨/刪除）
- [ ] Transaction 內/外分清（alert / 通知在 commit 後）
- [ ] Post-commit side effect 有 try/except（best-effort）
- [ ] 有 integration test

### 新模組 / 新 use case
- [ ] 有單一組裝入口（`application/<module>/__init__.py`）
- [ ] Application service 不碰 Session / ORM / raw SQL
- [ ] QueryService 只讀
- [ ] 有 MODULE.md
- [ ] 有 unit + integration tests
