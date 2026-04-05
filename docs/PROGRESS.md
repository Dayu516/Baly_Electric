# OTTIMO 專案進度摘要

**最後更新：** 2026-04-04
**專案：** 電控材料行數位化轉型系統
**當前階段：** Phase A 收尾 → Phase B 準備

---

## 專案結構

```
D:\OneDrive\6_projects\ottimo\
├── backend/              ← FastAPI 後端 (Python 3.11)
│   ├── core/             ← Results, Errors, Security, Logging
│   ├── domain/           ← 純 Python 業務模型 (9 個子模組)
│   ├── application/      ← Use case services (7 個 service)
│   ├── infrastructure/   ← ORM, Repositories, 6 個分域 QueryService
│   ├── api/v1/           ← REST API routes (零 SQL)
│   ├── migrations/       ← Alembic (001~006)
│   ├── tests/            ← 79 smoke + 30 integration = 109 項
│   └── scripts/          ← seed_owner, seed_categories, seed_attribute_templates
├── frontend/             ← Flutter Desktop (Windows + Web + iPad + iPhone)
│   ├── lib/core/         ← Auth, Router, Theme, FeatureFlags, Widgets
│   ├── lib/modules/      ← Dashboard, POS, Product, Procurement, Sales, Inventory, Customer, Review, Alert, Settings
│   └── lib/integrations/ ← BarcodeScanner, ReceiptPrinter
├── tools/
│   └── data-cleaner/     ← 獨立清洗工具 (Web UI + CLI)
└── docs/                 ← PROGRESS.md, REFACTORING_LOG.md, Phase B 計畫
```

---

## 環境

| 元件 | 狀態 |
|------|------|
| Python 3.11 | 已安裝 |
| Docker Desktop | 已安裝，PostgreSQL 跑在 Docker |
| Flutter 3.41 | 已安裝，C:\flutter |
| Visual Studio 2022 | 已安裝，Windows Desktop build OK |
| 後端 venv | `backend/.venv/` |
| data-cleaner venv | `tools/data-cleaner/.venv/` |

**啟動指令：**
```bash
# 後端
cd backend && PYTHONPATH=. .venv/Scripts/uvicorn.exe main:app --host 0.0.0.0 --port 8000

# 前端 (build)
cd frontend && C:/flutter/bin/flutter build windows --debug

# 前端 (run)
frontend/build/windows/x64/runner/Debug/ottimo.exe

# 全部測試
cd backend && PYTHONIOENCODING=utf-8 PYTHONPATH=. .venv/Scripts/python.exe tests/run_all_tests.py
```

---

## Phase A 完成狀態

### 後端 API

| 路由前綴 | 功能 | 狀態 |
|---------|------|------|
| `/auth` | Login, Me | ✅ |
| `/dashboard` | 摘要統計 + 今日銷售 + 低庫存 + 一鍵建採購單 | ✅ |
| `/products` | CRUD + Search + Categories + Tree | ✅ |
| `/skus` | SKU Detail + Product Detail + 快速編輯 | ✅ |
| `/aliases` | 品項別名 CRUD | ✅ |
| `/attributes` | 品項屬性 + 分類屬性模板 | ✅ |
| `/import` | 凌越 CSV 匯入 | ✅ |
| `/sales` | Checkout（含稅/未稅/稅外加）+ Void | ✅ |
| `/sales` (history) | 銷售紀錄 + 明細 | ✅ |
| `/receipts` | 出貨單資料 + 文字格式 | ✅ |
| `/inventory` | 庫存查詢+搜尋+摘要 + 異動 + 進貨驗收 + 盤點 + 重算 | ✅ |
| `/customers` | CRUD + 月結生成 + 收款 + AR 列表 | ✅ |
| `/suppliers` | CRUD + 歷史交易紀錄 | ✅ |
| `/purchase-orders` | CRUD + 確認 + 取消 + 驗收 + 刪除 | ✅ |
| `/inquiries` | 詢價單完整流程 + 比價 + 轉 PO | ✅ |
| `/quotations` | 報價單完整流程 + 轉銷貨 | ✅ |
| `/reviews` | List + Create + Claim + Resolve | ✅ |
| `/alerts` | List + Mark Read | ✅ |
| `/reports` | 供應商月度統計 | ✅ |
| `/settings` | 公司資料 + 系統參數 | ✅ |
| `/users` | 帳號管理 + 改密碼 | ✅ |

**測試：** 79 smoke + 30 integration = **109 項全過**

### 前端頁面

| 頁面 | 狀態 | 功能 |
|------|------|------|
| **首頁 Dashboard** | ✅ | 7 張摘要卡 + 今日銷售 + 低庫存 + 一鍵建採購單 |
| **POS 結帳** | ✅ | 客戶選擇 → 搜尋/掃碼 → 購物車 → 稅別 → F12 結帳 → 出貨單預覽 → 5 秒自動回搜尋 |
| **商品管理** | ✅ | 分類樹 + 品項列表 + 搜尋 + 品項資訊卡(含快速編輯) + 分類管理 + 屬性模板 |
| **採購進貨** | ✅ | 採購單(含金額統計+刪除) + 詢價單(含比價並排表格) + 進貨驗收 |
| **銷售管理** | ✅ | 報價單 + 銷售紀錄 |
| **庫存總覽** | ✅ | 庫存查詢(搜尋+低庫存過濾+摘要統計) + 盤點 + 異動紀錄 |
| **客戶管理** | ✅ | 列表 + 搜尋 + 新增 + 詳情 + 月結帳款 + 收款 |
| **審核待辦** | ✅ | 列表 + 領取 + 通過/退回 |
| **通知中心** | ✅ | 警示列表 + 類型圖示 + 標記已讀 |
| **系統設定** | ✅ | 公司資料 + 系統參數 + 系統工具 + 改密碼 + 帳號管理 |

### 後端架構狀態

- API 層：**全部模組零 SQL 殘留**
- Application 層：7 個 Service（PO、Inquiry、Quotation、Checkout、VoidSale、ReceiveStock、StockCount、StockRecalc、GenerateStatement）
- Query 層：6 個分域 class（Product、Procurement、Sales、Inventory、Attribute、Dashboard），零 Facade
- 測試：79 smoke + 30 integration = **109 項全通過**
- 技術債：**零**

### 前端架構狀態

- 所有 .dart 檔案 < 500 行
- 共用元件：StatusBadge、ProductSearchDialog、SupplierHistoryDialog
- Flutter analyze：零 error

---

## Phase A 未完事項（需在 Phase B 前收尾）

| # | 事項 | 重要性 | 說明 |
|---|------|--------|------|
| 1 | 凌越品項匯入主系統 | ⭐⭐⭐ | 12,298 品項已清洗，需審查+匯入 |
| 2 | 客戶資料匯入主系統 | ⭐⭐⭐ | 1,053 筆已清好 |
| 3 | 門市部署 + 印表機 | ⭐⭐⭐ | Flutter exe + EPSON LQ-310 針式印表機 |
| 4 | 離線結帳基礎版 | ⭐⭐ | SQLite 快取，斷網也能 POS 結帳 |
| 5 | 逾期帳款自動提醒 | ⭐⭐ | AR 逾期 N 天 → OperationalAlert |
| 6 | 月結單 PDF 匯出 | ⭐ | 可印出給客戶的格式 |
| 7 | 客訂追蹤（任務管理） | ⭐⭐⭐ | 客人訂→貨到→通知來拿（門市最大痛點） |

---

## Phase B 計畫

> 詳見 `docs/PHASE_B_PLAN.md`

---

## 資料清洗 (tools/data-cleaner)

- **凌越 SQL Server 備份** → Docker 還原 → 匯出 CSV
- **品項清洗：** 12,298 筆已跑完 AI 清洗（auto 4,174 / review 6,992 / manual 1,132）
- **客戶清洗：** 1,053 筆已規則清洗
- **Web UI：** 分類下拉 + 品牌下拉 + Inline 編輯 + 批次操作 + 刪除

---

## 重要設計決策（記住）

核心規則請看 Constitution.md / CLAUDE.md。