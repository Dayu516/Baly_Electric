# OTTIMO 架構重構 + 功能開發紀錄

**日期：** 2026-04-03
**範圍：** Phase 1~4 全部完成

---

## Phase 1 — 後端架構重構（已完成）

### 問題
快速開發期間，9 個 API 檔案直接在 API 層寫 SQL 和業務邏輯，違反四層架構規則。

### 修正原則
- **SQL** → 全部搬進 `infrastructure/persistence/query_services/` 分域 class
- **業務邏輯**（狀態轉換、驗收流程、轉單）→ 搬進 `application/` 下的 Service
- **API 層** → 只做 HTTP 轉接（參數驗證 + 呼叫 Service + 回傳結果）

### 修正清單

| API 檔案 | 違規數 | 修正方式 |
|---------|--------|---------|
| `api/v1/purchase_orders.py` | 11 處 SQL + 業務邏輯 | `PurchaseOrderService` + `ProcurementQueryService` |
| `api/v1/inquiries.py` | 10 處 SQL + 業務邏輯 | `InquiryService` + `ProcurementQueryService` |
| `api/v1/quotations.py` | 15 處 SQL + 業務邏輯 | `QuotationService` + `ProcurementQueryService` |
| `api/v1/supplier_prices.py` | 10 處 SQL | `ProductQueryService` + `ProcurementQueryService` |
| `api/v1/product_detail.py` | 9 處 SQL | `ProductQueryService` |
| `api/v1/sales_history.py` | 8 處 SQL | `SalesQueryService` |
| `api/v1/reports.py` | 2 處 SQL | `ProcurementQueryService` |
| `api/v1/alternatives.py` | 2 處 SQL | `ProductQueryService` |
| `api/v1/attributes.py` | 5 處 session.query | `AttributeQueryService` |

### 新建的 Application Service
- `application/procurement/purchase_order_service.py` — 採購單 CRUD + 驗收 + 一鍵補貨
- `application/procurement/inquiry_service.py` — 詢價單完整流程
- `application/procurement/quotation_service.py` — 報價單完整流程

---

## Phase 2 — 前端架構重構（已完成）

### 修正清單

#### settings_page.dart 拆分（1542 → 132 行）
| 新檔案 | 內容 |
|--------|------|
| `settings_widgets.dart` | SuccessBanner, ErrorBanner 共用元件 |
| `company_info_panel.dart` | 公司資料 |
| `parameters_panel.dart` | 系統參數 |
| `category_management_panel.dart` | 分類樹管理（已搬到商品管理） |
| `attribute_template_panel.dart` | 分類屬性模板（已搬到商品管理） |
| `system_tools_panel.dart` | 系統工具 |
| `change_password_panel.dart` | 修改密碼 |
| `user_management_panel.dart` | 帳號管理 |

#### product_info_card.dart 拆分（985 → 245 行）
| 新檔案 | 內容 |
|--------|------|
| `product_info_card/basic_info_tab.dart` | 基本資料 + 屬性編輯 + 別名 + 最近異動 |
| `product_info_card/supplier_pricing_tab.dart` | 各供應商當前報價一覽 |
| `product_info_card/price_quote_history_tab.dart` | 報價歷史 + 比價 + 新增報價 |
| `product_info_card/alternatives_tab.dart` | 替代品搜尋 |

#### 共用元件抽出
| 新檔案 | 內容 |
|--------|------|
| `core/widgets/status_badge.dart` | 統一狀態標籤 |
| `core/widgets/product_search_dialog.dart` | 品項搜尋 dialog |

---

## Phase 3 — 功能開發（已完成）

| # | 功能 | 說明 |
|---|------|------|
| 5 | 首頁 Dashboard | 7 張摘要卡 + 今日銷售 + 低庫存清單，登入預設到 `/dashboard` |
| 6 | 低庫存一鍵建採購單 | 按首選供應商分組自動建 draft PO |
| 7 | 分類管理+屬性模板搬到商品管理 | 從 Settings 移到 Product 頁面，owner 限定 |
| 8 | 庫存總覽頁面 | 搜尋+低庫存過濾+摘要統計列，加入 sidebar |
| 9 | 採購單詳情加金額統計 | 訂購總額/已收金額/每行小計 |
| 10 | 詢價單比價並排表格 | DataTable（行=品項、列=供應商），點格子選取 |

### Bug fix
- `accounts_receivables` 欄位名是 `total_amount - paid_amount`，不是 `amount`
- 狀態是 `open/partial_paid/overdue`，不是 `unpaid`

---

## Phase 4 — 架構補強（已完成）

### 4.1 Service 級 Integration Test（30/30 通過）

| 測試檔 | 測試數 | 覆蓋範圍 |
|--------|--------|---------|
| `test_purchase_order_service.py` | 17 | 建單、確認、取消、全收、部分收、庫存更新、異動紀錄、自動建 PO、金額統計 |
| `test_inquiry_service.py` | 6 | 建詢價、加品項、加報價、選報價→轉 PO 完整流程、取消 |
| `test_quotation_service.py` | 7 | 建報價、加品項、送出/確認、轉銷貨+扣庫存、空報價失敗、取消 |

測試使用 `begin_nested()` savepoint，每個測試結束自動 rollback，不留副作用。

### 4.2 POS 頁面拆分（1142 → 5 檔）

| 檔案 | 行數 | 內容 |
|------|------|------|
| `pos_page.dart` | 57 | 主頁 + Layout 組裝 |
| `pos_search_panel.dart` | 362 | 搜尋面板（掃碼+搜尋+快速新增） |
| `pos_cart_panel.dart` | 342 | 購物車面板 + 客戶選擇器 |
| `pos_cart_item_tile.dart` | 185 | 購物車單品（改量/改價/刪除） |
| `pos_checkout_success.dart` | 119 | 結帳成功 + 出貨單預覽 |

### 4.3 Facade 退場（21 檔遷移 + 刪除）

**過程：**
1. Phase 1 先建了集中式 `query_service.py`（~45 個方法）
2. Phase 3.5 拆成 6 個分域 class，原檔改為 Facade 委派
3. Phase 4.3 逐檔遷移 21 個使用者到分域 class
4. 確認零引用後刪除 `query_service.py`

**遷移對照：**
| 分域 | Class | 方法數 | 使用者 |
|------|-------|--------|--------|
| 品項 | `ProductQueryService` | 9 | product_detail, alternatives, search, supplier_prices, products |
| 採購 | `ProcurementQueryService` | 19 | purchase_orders, inquiries, quotations, supplier_prices, reports, dashboard |
| 銷售 | `SalesQueryService` | 5 | sales_history, customers, products |
| 庫存 | `InventoryQueryService` | 4 | inventory, stock_recalc_service |
| 屬性 | `AttributeQueryService` | 5 | attributes |
| Dashboard | `DashboardQueryService` | 3 | dashboard |

**驗證：** 109/109 測試通過（79 smoke + 30 integration）後刪除 Facade。

---

## 風險控制

### 已消除的風險
| 風險 | 消除方式 | Phase |
|------|---------|-------|
| API 層亂寫 SQL | grep 驗證 + CLAUDE.md 禁止規則 | 1 |
| QueryService God Object | 分域拆分為 6 個 class | 3.5 |
| Facade 間接層 | 遷移 21 檔 + 刪除 Facade | 4.3 |
| Application Service 裸奔 | 30 個 integration test | 4.1 |
| 前端巨型檔案 | settings(1542→8檔)、product_info(985→5檔)、POS(1142→5檔) | 2, 4.2 |
| 重複元件 | StatusBadge + ProductSearchDialog 抽出 | 2 |

### 仍需注意的風險
| 風險 | 狀態 |
|------|------|
| 無已知架構債 | 全部已清除 |

現行規則以 CLAUDE.md / Constitution.md 為準。

---

## Phase 5 — UX 修正 + 追加需求（已完成）

### 5.1 功能重複整理
- 商品管理：移除進貨驗收+盤點（5 tab → 3 tab：商品列表、分類管理、屬性模板）
- 採購進貨：加入進貨驗收（2 tab → 3 tab：採購單、詢價單、進貨驗收）
- 庫存總覽：移除進貨驗收（3 tab → 2 tab：庫存查詢、盤點）

### 5.2 UX 修正
- 採購/詢價空白引導：加 icon + 「點左側列表選擇」文字
- POS 結帳後 5 秒自動回搜尋（倒數顯示在按鈕上）
- 品項資訊卡加快速編輯（售價/成本/安全庫存）
- 「分類管理」亂碼修正（UTF-8 截斷）

### 5.3 追加需求
- 已取消採購單可刪除（`DELETE /purchase-orders/{po_id}`，僅限 cancelled）
- 供應商歷史交易紀錄（`GET /suppliers/{id}/history`，摘要+逐筆紀錄，PO 詳情點供應商名可查）

### 5.4 最後一輪技術債清除
- customers/receipt/aliases/suppliers 殘留 SQL 全部搬進分域 QueryService
- passlib → bcrypt 直接呼叫（消除啟動 warning）
- 公版通用規則補 7 條從實戰來的規則
- 經驗總結寫入 AAA 知識庫

---

## 最終系統狀態（Phase A 開發完成，2026-04-04）

### Sidebar 導航
1. 首頁（Dashboard）
2. POS 結帳
3. 商品管理（商品列表 + 分類管理 + 屬性模板）
4. 採購進貨（採購單 + 詢價單 + 進貨驗收）
5. 銷售管理
6. 庫存總覽（庫存查詢 + 盤點）
7. 客戶管理
8. 審核待辦
9. 通知中心
10. 系統設定

### 後端架構
- API 層：全部模組零 SQL
- Application 層：7 個 Service
- Query 層：6 個分域 class，零 Facade
- 安全：bcrypt 直接呼叫，零 warning
- 測試：79 smoke + 30 integration = **109 項全通過**
- 技術債：**零**

### 前端架構
- 所有 .dart 檔案 < 500 行
- 共用元件：StatusBadge、ProductSearchDialog、SupplierHistoryDialog
- Flutter analyze：零 error

### 下一步
- Phase A 收尾（匯入+部署+客訂追蹤）→ Phase B（AI 省力版）
- 詳見 `docs/PHASE_B_PLAN.md`
