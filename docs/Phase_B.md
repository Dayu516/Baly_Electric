# Phase B 計畫：省力版

**目標：** 用 AI 讓操作更快、更省力。每個功能都是 Phase A 的「增強」，AI 掛了就降級回 A 的行為。

**核心原則：** 先活下來，再變聰明。AI 是肌肉不是骨頭。

---

## 前置條件（Phase A 收尾）

> 以下事項必須在 Phase B 開發前完成，否則 AI 功能沒有資料基礎。

| # | 事項 | 為什麼是前置 | 狀態 |
|---|------|------------|------|
| A-1 | 凌越品項匯入主系統（12,298 筆） | B1 智慧搜尋需要品項資料做 embedding | 🔲 |
| A-2 | 客戶資料匯入主系統（1,053 筆） | B4 客戶洞察需要客戶+交易資料 | 🔲 |
| A-3 | 門市部署 + 印表機 | 系統要真正上線用，才有真實銷售資料 | 🔲 |
| A-4 | 離線結帳基礎版 | 門市斷網時不能停賣 | 🔲 |
| A-5 | 逾期帳款自動提醒 | AR 逾期 N 天 → OperationalAlert | 🔲 |
| A-6 | 月結單 PDF 匯出 | 客戶要紙本帳單 | 🔲 |
| A-7 | 客訂追蹤（任務管理） | 門市最大日常痛點，比 AI 更優先 | 🔲 |

---

## AI 基礎建設（Phase B 開始前建好）

### 需要新建的 DB 表

```sql
-- AI 建議物件（所有 AI 輸出都經過這張表）
CREATE TABLE ai_suggestions (
    suggestion_id   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    suggestion_type VARCHAR(50) NOT NULL,  -- product_enrichment / reorder_suggestion / customer_insight / ...
    source_adapter  VARCHAR(30) NOT NULL,  -- llm / embedding / vision / crawler
    target_entity_type VARCHAR(30),        -- product / sku / customer / ...
    target_entity_id   UUID,
    suggestion_data JSONB NOT NULL,        -- 建議內容（結構依類型而異）
    confidence      DECIMAL(3,2),          -- AI 信心度 0.00 ~ 1.00
    status          VARCHAR(20) NOT NULL DEFAULT 'pending',  -- pending / approved / modified / rejected / auto_approved / expired
    reviewed_by     UUID,
    reviewed_at     TIMESTAMP WITH TIME ZONE,
    applied_changes JSONB,                 -- 實際套用的變更
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at      TIMESTAMP WITH TIME ZONE
);

-- product_search_docs 已有 embedding 欄位（Phase A 建表時預留）
-- 只需 CREATE EXTENSION IF NOT EXISTS vector;
```

### 需要新建的後端目錄

```
infrastructure/ai/
├── __init__.py
├── embedding_adapter.py    -- B1: 文字向量化
├── llm_adapter.py          -- B2/B3/B4: LLM 呼叫
├── crawler_adapter.py      -- B2: 網頁爬取
└── ai_cost_tracker.py      -- 成本追蹤（model / tokens / latency / cost）
```

### AI Adapter 設計規則（已寫在 v5 規格書）

1. 只提供能力，不做業務決策
2. 統一介面，Application Service 不知道底下用 Claude 還是 OpenAI
3. 失敗不影響核心，自動降級
4. 成本可控，每次呼叫記錄成本，可設每日上限
5. 不直接改資料，輸出永遠是 AISuggestion

---

## B1：智慧搜尋（2-3 週）

**「打錯字也找得到」**

### 現在有什麼
- DB LIKE + 全文搜尋 + 別名搜尋
- 搜尋速度 < 100ms
- 使用者必須打對字才找得到

### B1 要加什麼
- `EmbeddingAdapter` 把品名+規格+別名轉成向量
- 存入 `product_search_docs.embedding`（pgvector）
- 搜尋時：精確搜尋先出（現有邏輯），語意搜尋補充（AI）
- 降級：AI 掛了 → 只用精確搜尋，使用者無感

### 技術細節
- pgvector extension 已在 PostgreSQL 可用
- `product_search_docs` 表已有 embedding 欄位
- 向量維度：1536（OpenAI ada-002）或 384（開源 all-MiniLM）
- 搜尋流程：`SELECT * FROM product_search_docs ORDER BY embedding <=> :query_vector LIMIT 10`
- 批次向量化：12,298 品項，ada-002 約 $0.5，開源免費

### 架構
```
ProductQueryService.search_products()      ← 現有精確搜尋（不動）
ProductQueryService.semantic_search()      ← 新增語意搜尋
SearchProductService.search()              ← 組合：精確 + 語意合併去重
EmbeddingAdapter.embed()                   ← infrastructure/ai/
EmbeddingAdapter.batch_embed()             ← 批次向量化
```

### 驗收標準
- [ ] 語意搜尋可用（打錯字、別名、同義詞都能找到）
- [ ] 不影響精確搜尋速度（精確結果先出）
- [ ] AI 掛了 → 自動降級為關鍵字搜尋
- [ ] 向量化成本記錄可查

### 決策待定
- [ ] Embedding 模型選型：OpenAI ada-002（付費、品質高）vs 開源 all-MiniLM（免費、品質中）
- [ ] 中文品名的向量化效果需要實測

---

## B2：AI 品項補齊（2-3 週）

**「AI 幫你填資料」**

### 現在有什麼
- 12,298 品項，很多只有品名
- 分類屬性模板已建（14 分類 × 45 屬性）
- 品項屬性編輯 UI 已有

### B2 要加什麼
- `CrawlerAdapter` 爬原廠網站（士林、東元、OMRON、施耐德...）
- `LLMAdapter` 看品名 → 建議分類、補齊規格
- 所有結果 → `AISuggestion` 表 → `ReviewTask` → 審核待辦池
- 批次確認 UI（高信心一鍵通過）
- 審核結果回饋知識庫

### 架構
```
application/ai/
├── product_enrichment_service.py   ← 品項補齊 use case
└── suggestion_review_service.py    ← 審核 + 套用 use case

AISuggestion 資料流：
  CrawlerAdapter 爬到資料
  → LLMAdapter 整理+建議分類
  → 寫入 AISuggestion (status=pending)
  → 自動建 ReviewTask
  → 人工審核 approved/rejected
  → approved → 寫入 products/skus/product_attributes
```

### 爬蟲目標（按品牌優先度）
| 品牌 | 網站 | 品項數（估） | 難度 |
|------|------|-----------|------|
| 士林電機 | shihlin.com.tw | ~2000 | 中 |
| 東元 | teco.com.tw | ~1000 | 中 |
| OMRON | omron.com.tw | ~500 | 低（結構化好） |
| 施耐德 | se.com/tw | ~800 | 中 |
| ABB | abb.com | ~300 | 低 |

### 驗收標準
- [ ] 爬蟲能補齊至少 3 個品牌的品項規格
- [ ] AI 建議出現在審核待辦池
- [ ] 批次確認可用（高信心一鍵通過）
- [ ] 審核結果有回饋紀錄

---

## B3：AI 庫存建議（2 週）

**「系統告訴你該叫什麼貨」**

### 現在有什麼
- 固定安全庫存（手動設 min_stock）
- 一鍵建採購單（低庫存 + 首選供應商 → 自動建 PO）
- 但只有 ~1000 品項有設庫存，其餘客訂為主

### B3 要加什麼
- 銷速分析（過去 N 天每個品項賣多少）
- AI 動態安全庫存建議（取代手動 min_stock）→ `AISuggestion`
- AI 每週採購建議單 → `AISuggestion` → 人工確認 → 建 PO
- 庫存異常偵測（銷量突增/突降）→ `OperationalAlert`
- 季節性調整（電控材料有冬夏差異嗎？需要使用者回饋）

### 架構
```
application/ai/
└── inventory_suggestion_service.py

資料來源：
  sale_lines（銷售紀錄）→ 計算銷速
  inventory_balances（庫存）→ 當前狀態
  purchase_receipt_lines（進貨）→ 到貨週期

輸出：
  AISuggestion (suggestion_type='reorder_suggestion')
  → 人工確認
  → PurchaseOrderService.create_order()
```

### 驗收標準
- [ ] AI 每週自動產出採購建議（品項+建議數量+理由）
- [ ] 建議可一鍵轉成採購單草稿
- [ ] 銷量異常偵測可用
- [ ] 手動設的 min_stock 仍然有效（AI 建議是輔助不是取代）

### 注意事項
- 只對備庫存品（~1000 品項）有意義
- 客訂品項不需要 AI 庫存建議
- 需要區分「備庫存品」和「客訂品」的標記

---

## B4：AI 客戶洞察（1-2 週）

**「系統比你更了解你的客人」**

### 現在有什麼
- 客戶 CRUD + 月結 + 歷史售價（customer_price_history）
- 銷售紀錄（sales + sale_lines）

### B4 要加什麼
- 客戶流失預警（N 天沒來買 → OperationalAlert）
- 月結異常標記（本月金額比平均高/低很多 → AISuggestion）
- POS 客戶推薦（「這個客人上次也買了 XX」— 已有 customer_price_history 表）
- 月結 AI 摘要（給老闆看重點）

### 架構
```
最簡做法（不需要 LLM）：
  規則引擎就夠 →
  - 客戶 N 天沒交易 → alert
  - 月結金額偏離平均 > 30% → alert
  - POS 選客戶後自動帶出「上次買了什麼」

進階做法（需要 LLM）：
  LLMAdapter 產出月結摘要文字 → AISuggestion
```

### 驗收標準
- [ ] 流失預警出現在通知中心
- [ ] 月結有異常標記
- [ ] POS 選客戶後顯示歷史購買紀錄

---

## Phase B 執行順序

| 順序 | 項目 | 依賴 | 預估 |
|------|------|------|------|
| **0** | Phase A 收尾（匯入+部署+客訂追蹤） | 無 | 2-3 週 |
| **1** | AI 基礎建設（ai_suggestions 表 + adapter 骨架） | A 收尾完 | 1 週 |
| **2** | B1 智慧搜尋 | 品項已匯入 | 2-3 週 |
| **3** | B3 AI 庫存建議 | 有真實銷售資料 | 2 週 |
| **4** | B2 AI 品項補齊 | B1 完成（embedding 可用） | 2-3 週 |
| **5** | B4 AI 客戶洞察 | 有足夠客戶+交易資料 | 1-2 週 |

**為什麼 B3 在 B2 前面：**
- B3 建在一鍵建採購單之上，架構已有
- B2 需要爬蟲，開發+維護成本較高
- B3 對日常營運的幫助更直接（每週都要訂貨）

---

## 降級規則（每個 B 模組都要遵守）

| 情境 | 行為 |
|------|------|
| AI 服務掛了 | 自動降級回 Phase A 行為，使用者看到提示但不阻斷操作 |
| AI 回應太慢（> 3 秒） | 先回傳精確結果，AI 結果非同步補上 |
| AI 成本超日限 | 停止 AI 呼叫，只用 Phase A 功能 |
| AI 建議明顯錯誤 | 使用者 reject → 記錄回饋 → AI 下次修正 |

---

## 成本控制

| 項目 | 估算 |
|------|------|
| Embedding（12,298 品項，一次性） | OpenAI: ~$0.5 / 開源: $0 |
| Embedding（每日新增品項） | 極低，每天幾筆 |
| LLM（品項補齊，12,298 品項） | Claude: ~$5-10 / GPT-4: ~$10-20 |
| LLM（週報+月結摘要） | 每月 < $1 |
| 爬蟲 | $0（自建） |

**每月 AI 成本預估：< $10**（門市規模）
