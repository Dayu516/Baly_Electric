## 系統架構規則（永久生效）

## Application Service 強制限制（最高優先）

以下規則優先於所有歷史實作與舊代碼：

1. Application Service 不可直接使用 SQLAlchemy Session
2. Application Service 不可透過任何方式取得 _session（包含 query_service._session）
3. Application Service 不可 import ORM model（*ORM）

4. 所有資料存取必須透過 repository 介面
5. raw SQL 僅允許存在於 infrastructure 層（repository / query_service）

6. 若某段邏輯無法在「不啟動 DB」的情況下測試，視為設計錯誤

---

## 違規優先處理原則

若現有程式碼違反上述規則：

- 不可延續錯誤模式
- 新增/修改程式碼必須符合新規則
- 舊程式碼採「逐步替換」，不可一次大重構

本系統採用四層架構，每層有明確職責邊界：

### Domain 層（domain/）
- 純業務模型與業務規則
- 不得 import 任何外部套件（SQLAlchemy、FastAPI、openai 等）
- 不得直接存取 DB、檔案系統、外部 API
- 只能定義：models、events、repository 介面（abstract）
- 可以被單獨測試，不需要任何外部依賴

### Application 層（application/）
- 負責 use case 編排，一個 use case 一個 service
- 可以呼叫 domain model 和 infrastructure（repository impl、adapter）
- 業務決策在這裡，不在 infrastructure 或 API 層
- 不得直接寫 SQL（SQL 放 infrastructure/persistence/query_services/）
- 不得直接 import 外部 AI 套件（透過 adapter 介面）

### Infrastructure 層（infrastructure/）
- 所有外部依賴的實作：DB、Redis、AI adapter、LINE、檔案儲存
- Repository 介面的實作（xxx_repo_impl.py）
- 手寫 SQL 集中在 query_services/ 分域 class
- AI adapter 只提供能力，不做業務決策

### API 層（api/）
- 只做 HTTP 轉接：參數驗證 + 呼叫 application service + 回傳結果
- 不得放業務邏輯
- 不得直接查 DB
- 不得直接呼叫 AI adapter
- 每個 route 必須有 require_role 權限檢查

### 禁止事項
- 禁止在 API route 裡寫業務邏輯或 DB 查詢
- 禁止在 application service 裡寫原生 SQL
- 禁止在 domain model 裡 import 任何框架套件
- 禁止業務邏輯散落在多層（一個決策只能在一個地方做）
- 禁止過度抽象（Phase A 不需要 DDD 的 Aggregate Root / Value Object / Domain Service 全套）
- 禁止提前做事件驅動（Phase A 用 transaction 同步，不用 event bus）

## 開發鐵律（所有開發者 + AI 必須遵守）

### 讀寫分離
- **查詢（讀）** 只走 QueryService 分域 class，不可在其他地方寫 SQL
- **狀態變更（寫）** 只能在 Application Service 裡做，不可在 API 層或 UI 直接操作 ORM
- 唯一例外：InventoryBalance atomic update 放在 inventory_repo_impl.py

### 狀態變更必須走 Application Service 的操作
| 操作 | 所在 Service | 禁止的捷徑 |
|------|-------------|-----------|
| 建採購單 / 更新 / 確認 / 取消 | PurchaseOrderService | API 直接 session.add(PurchaseOrderORM) |
| 採購單驗收（含入庫） | PurchaseOrderService.receive_order | API 直接寫 StockMovement + InventoryBalance |
| 低庫存自動建 PO | PurchaseOrderService.auto_create_from_low_stock | API 直接迴圈建 PO |
| 建詢價 / 加報價 / 選報價 / 轉 PO | InquiryService | API 直接操作 inquiry ORM |
| 建報價 / 送出 / 確認 / 轉銷貨 | QuotationService | API 直接建 Sale + 扣庫存 |
| 結帳（POS） | CheckoutService | API 直接寫 sale + sale_lines |
| 作廢交易 | VoidSaleService | API 直接改 status + 退庫存 |
| 進貨驗收 | ReceiveStockService | API 直接寫 stock_movement |
| 盤點 | StockCountService | API 直接改 InventoryBalance |
| 庫存重算 | StockRecalcService | API 直接 UPDATE |
| 月結生成 | GenerateStatementService | API 直接寫 accounts_receivables |

### QueryService 分域結構
```
infrastructure/persistence/query_services/
├── base.py                      — BaseQueryService（只提供 self._session）
├── product_query_service.py     — 品項搜尋、SKU 詳情、替代品
├── procurement_query_service.py — 採購單、詢價單、報價單、供應商報價
├── sales_query_service.py       — 銷售紀錄、客戶歷史售價、月結
├── inventory_query_service.py   — 庫存查詢、重算
├── attribute_query_service.py   — 屬性模板、品項屬性
└── dashboard_query_service.py   — Dashboard 摘要
```
- 原 `query_service.py` Facade 已刪除，所有程式碼直接用分域 class
- **新功能必須直接用對應的分域 class**

## Phase A 限制規則

1. 不得 import 任何 AI 相關套件（openai, anthropic, langchain 等）
2. 不得建立 infrastructure/ai/ 目錄下的任何檔案
3. 不得建立 LINE 相關程式碼
4. 搜尋功能只用 DB LIKE / PostgreSQL 全文搜尋，不用向量搜尋
5. 不得在 product_search_docs 表寫入 embedding 欄位
6. 不得建立 ai_suggestions 表
7. 所有跨模組操作放在同一個 DB transaction 內，不用 event bus
8. 不得使用 event_bus.publish() 或任何事件發佈機制
9. 報表只做基礎查詢 API，不做圖表、不做 AI 摘要
10. 庫存更新必須透過 StockMovement -> InventoryBalance，不得直接改 current_stock
11. 每個 API route 必須有 require_role 權限檢查
12. iPhone 的 Level C 模組用 FeatureLockedPage，不要花時間做完整 UI
13. 不得把簡單功能過度 DDD 化（不需要 Aggregate Root、Value Object 全套）
14. 優先完成 Windows Desktop 版型，再調整 iPad 版型，最後處理 iPhone

## 命名規則

- DB 表名：snake_case 複數（products, skus, sale_lines）
- 主鍵：{entity}_id，UUID 型別
- 外鍵：與目標主鍵同名
- 時間欄位：TIMESTAMP WITH TIME ZONE（UTC）
- 金額欄位：DECIMAL(12, 2)
- API URL：/api/v1/{resource} 複數
- 錯誤碼：ERR-{CATEGORY}-{NUMBER}

## 開發節奏規則（每個功能必須遵守）

### 新增模組前（必做）
1. 重新讀本檔案的「系統架構規則」和「開發鐵律」段落
2. 確認：SQL 放哪個分域 QueryService？狀態變更放哪個 Application Service？API 只做什麼？
3. 回答使用者：「SQL 放 XxxQueryService，業務邏輯放 XxxService，API 只做 HTTP 轉接」

### 開發中（必做）
4. 一次只做一個模組，做完驗證再做下一個
5. 前端單一檔案超過 500 行時，拆成獨立檔案
6. 共用 pattern 出現第 2 次時，抽出共用元件

### 做完後（必做）
7. 跑 smoke test
8. 用 grep 驗證：API 層沒有 `text(`、`session.execute`、`session.query`（除了 get_session）
9. 有違規的立刻修正，不留技術債到下次

### 使用者催促時
- 使用者說「全部都改」「繼續」→ 回答「好的，我按正確分層一個一個做，每個做完驗證再下一個」
- 不可為了速度在 API 層直接寫 SQL
- 不可一次改超過 3 個模組

## 已知架構債

> 2026-04-03 後端 API 層架構債已全部修正（9 個模組 SQL + 業務邏輯搬到 Application Service / QueryService）。
> 前端架構債見 frontend/CLAUDE.md。

| 檔案 | 問題 | 應搬到 | 狀態 |
|------|------|--------|------|
| api/v1/purchase_orders.py | 11 處直接 SQL + 業務邏輯 | Application Service + QueryService | ✅ 已修正 |
| api/v1/inquiries.py | 10 處直接 SQL + 業務邏輯 | Application Service + QueryService | ✅ 已修正 |
| api/v1/quotations.py | 15 處直接 SQL + 業務邏輯 | Application Service + QueryService | ✅ 已修正 |
| api/v1/supplier_prices.py | 10 處直接 SQL | QueryService | ✅ 已修正 |
| api/v1/product_detail.py | 9 處直接 SQL | QueryService | ✅ 已修正 |
| api/v1/sales_history.py | 8 處直接 SQL | QueryService | ✅ 已修正 |
| api/v1/reports.py | 2 處直接 SQL | QueryService | ✅ 已修正 |
| api/v1/alternatives.py | 2 處直接 SQL | QueryService | ✅ 已修正 |
| api/v1/attributes.py | 5 處直接 session.query | QueryService | ✅ 已修正 |

### 技術債狀態
| 項目 | 狀態 |
|------|------|
| API 層全部模組零 SQL | ✅ 已清除（含 customers/receipt/aliases/suppliers） |
| passlib warning | ✅ 已改用 bcrypt 直接呼叫 |

## 交易規則

- 核心操作在同一 transaction 內
- commit 後才做非關鍵操作（通知、告警）
- InventoryBalance 更新用 DB atomic update：current_stock = current_stock + :qty
- 允許負庫存，但需產生 OperationalAlert
- StockMovement 是庫存真相（append-only），InventoryBalance 是 projection
