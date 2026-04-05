# 資料清洗系統 (data-cleaner) 進度摘要

**日期：** 2026-04-03
**位置：** `tools/data-cleaner/`

---

## 架構

```
tools/data-cleaner/
├── app.py                 ← FastAPI Web UI（SQLite 版）
├── database.py            ← SQLite 儲存層（CRUD、搜尋、排序）
├── migrate_csv.py         ← CSV → SQLite 匯入腳本
├── cleaner.py             ← CLI 批次清洗（Claude AI 驅動）
├── clean_customers.py     ← 客戶清洗（規則式，無 AI）
├── data.db                ← SQLite 資料庫（migrate 後產生）
├── requirements.txt       ← anthropic, fastapi, uvicorn, httpx, ...
├── .env                   ← ANTHROPIC_API_KEY
├── input/
│   ├── lingyue_products.csv   ← 凌越匯出原始品項 (12,297 筆)
│   └── lingyue_customers.csv  ← 凌越匯出原始客戶 (1,091 筆)
├── output/
│   ├── auto.csv               ← 高信心 ≥0.85 (4,174 筆)
│   ├── review.csv             ← 中信心 0.6~0.85 (6,992 筆)
│   ├── manual.csv             ← 低信心 <0.6 (1,132 筆)
│   ├── all_cleaned.csv        ← 完整資料集 (12,298 筆)
│   ├── aliases.csv            ← 品項別名對照 (3,007 筆)
│   └── customers_cleaned.csv  ← 已清洗客戶 (1,053 筆)
└── templates/
    └── index.html             ← SPA 前端 v3
```

**技術棧：** FastAPI + SQLite + 純 HTML/CSS/JS + Claude Sonnet API
**儲存方式：** SQLite（data.db），支援搜尋/排序/持久化

---

## AI 清洗流程 (cleaner.py)

1. **讀取原始 CSV** — 自動偵測編碼（utf-8-sig / big5 / cp950）
2. **批次送 Claude API** — 每批 20 筆，模型 `claude-sonnet-4-20250514`
3. **AI 任務** — 拆解品名 → 品牌 + 系列 + 型號 + 規格，分類到標準分類樹，產生口語別名，給信心分數
4. **信心分桶** — ≥0.85 auto / 0.6~0.85 review / <0.6 manual
5. **斷點續跑** — 每批存 `.cleaner_progress.json`，`--resume` 可繼續

**System Prompt 角色：** 台灣電控材料行專家，熟悉士林、東元、OMRON、Schneider、Panasonic 等品牌

---

## Web UI (app.py)

**啟動：** `http://localhost:8501`

**功能：**
- 拖拉上傳 CSV 或載入 SQLite 資料
- 三大頁籤：品項審查 / 客戶 / 匯入主系統
- 即時統計卡片 + 審查進度條
- **搜尋** — 品名、品牌、型號、規格、別名關鍵字搜尋
- **排序** — 點擊欄位標題排序（品名/品牌/分類/信心/桶）
- **篩選** — 品牌下拉、分類下拉篩選
- **Inline 編輯** — 點擊即可修改品名、品牌、系列、分類、規格
- **批次操作** — 多選 + 批次指定品牌/分類 + 批次確認/刪除
- **匯出** — 按桶匯出 CSV + 匯出別名
- **分類下拉** — 從主系統 `localhost:8000` 拉分類樹（離線用本地分類）
- **鍵盤快捷鍵** — N=下一筆待審, S=搜尋, 1-4=切Tab, ←→=翻頁
- **匯入主系統** — 預覽 + 品項匯入 + 客戶匯入 + 別名匯入
- 分頁顯示（每頁 50 筆，SQL LIMIT/OFFSET）
- 編輯即存（SQLite 持久化，重啟不丟失）

**API 端點：**

| 端點 | 功能 |
|------|------|
| `POST /api/upload` | 上傳 CSV |
| `POST /api/load-results` | 載入 CSV 到 SQLite（DB 空時） |
| `POST /api/clean` | 啟動 AI 清洗 |
| `GET /api/status` | 清洗進度 |
| `GET /api/stats` | 分桶統計 + 審查進度 |
| `GET /api/items` | 品項查詢（分頁+搜尋+排序+篩選） |
| `PUT /api/items/{id}` | 修改單筆 |
| `DELETE /api/items/{id}` | 刪除單筆 |
| `POST /api/batch-update` | 批次更新 |
| `POST /api/batch-delete` | 批次刪除 |
| `GET /api/brands` | 品牌列表 |
| `GET /api/categories` | 主系統分類樹 |
| `GET /api/categories-local` | 本地分類列表 |
| `GET /api/export` | 匯出 CSV |
| `GET /api/export-aliases` | 匯出別名 CSV |
| `GET /api/customers` | 客戶查詢（分頁+搜尋） |
| `GET /api/import-preview` | 匯入預覽 |
| `POST /api/import-to-main` | 匯入品項/客戶到主系統 |
| `POST /api/import-aliases` | 匯入別名到主系統 |

---

## 客戶清洗 (clean_customers.py)

**規則式清洗（無 AI）：**
- 判斷公司/個人（看名稱有無「公司」「行」「企業」等關鍵字）
- 拆分電話/手機/傳真
- 判斷付款方式（月結/現金，看備註欄）
- 標準化地址
- 輸出 1,053 筆已清洗客戶

---

## 資料處理狀態

### 品項 (12,298 筆)

```
auto:    4,174 筆 (34%) ← 高信心，可直接匯入
review:  6,992 筆 (57%) ← 中信心，需快速審查
manual:  1,132 筆 (9%)  ← 低信心，需人工判斷
```

### 客戶 (1,053 筆)

已完成規則清洗，欄位包含：name, customer_type, phone, mobile, fax, address, unino, contact, payment_terms, credit_limit, internal_code

---

## 修改計畫

### Phase 1：SQLite 化 ✅

- [x] 建 SQLite schema（products_cleaned, customers_cleaned 兩張表）
- [x] 寫匯入腳本 migrate_csv.py：讀 output/*.csv → 寫入 SQLite
- [x] app.py 改為讀寫 SQLite（取代記憶體 _state dict）
- [x] 支援搜尋（LIKE 查詢）
- [x] 支援排序（信心/分類/品牌/品名）
- [x] 編輯即存（SQLite 持久化，不再怕重啟丟失）
- [x] 分頁用 SQL LIMIT/OFFSET（不再全部載入）

### Phase 2：審查效率提升 ✅

- [x] 加搜尋列（品名/品牌/分類關鍵字搜尋）
- [x] 加欄位排序（點欄位標題排序）
- [x] 加篩選器（按分類、按品牌篩選）
- [x] 加審查進度條（已確認 / 待審查 / 總數）
- [x] 加「跳到下一筆待審」快捷鍵 (N)
- [x] 鍵盤快捷鍵（S=搜尋, 1-4=切Tab, ←→=翻頁）

### Phase 3：匯入主系統 ✅

- [x] 匯入預覽 API（顯示將匯入幾筆、跳過幾筆）
- [x] 品項匯入：SQLite → 主系統 POST /api/v1/import（CSV 上傳）
- [x] 客戶匯入：逐筆 POST /api/v1/customers
- [x] 別名匯入：逐筆 POST /api/v1/aliases/{product_id}
- [x] 匯入後標記 imported 狀態（避免重複匯入）
- [x] 匯入 UI：預覽按鈕 + 匯入按鈕 + 結果顯示

---

## 啟動方式

```bash
# 首次：CSV → SQLite
cd tools/data-cleaner
.venv/Scripts/python.exe migrate_csv.py

# 啟動 Web UI
.venv/Scripts/python.exe app.py
# 打開 http://localhost:8501

# CLI 清洗（已跑完，通常不需再跑）
.venv/Scripts/python.exe cleaner.py --input input/lingyue_products.csv --output output/

# 客戶清洗（已跑完）
.venv/Scripts/python.exe clean_customers.py
```
