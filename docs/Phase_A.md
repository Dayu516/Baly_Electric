# Phase A 開發規範

**適用範圍：** Phase A（活下來版）全部子階段（A0 - A5）

**本文件定義 Phase A 的施工細節，是 v5 規格書的實作補充。任何實作決策與本文件衝突時，以本文件為準。**

**跨 Phase 通用規則請見 [Constitution.md](Constitution.md)。**

---

## 1. Phase A 事件實作方式

**Phase A 不做 full-blown event bus**，用簡單的「commit 後呼叫」模式。

**不用 Redis event bus。** Phase A 用最保守的方式：

```python
# Phase A 做法：transaction 內同步 + commit 後簡單 async

class CheckoutService:
    def checkout(self, ...):
        # ---- 同一個 transaction（全成功或全失敗）----
        with db.transaction():
            sale = self._create_sale(...)
            self._create_sale_lines(sale, cart)
            self._create_stock_movements(sale, cart)
            self._update_inventory_balance(cart)        # 同步更新餘額
            if customer.payment_terms == "monthly_credit":
                self._accumulate_ar(sale, customer)     # 月結累計也同步
            self._create_audit_event(sale)              # 稽核紀錄也同步

        # ---- commit 成功後，做非關鍵操作 ----
        # 這些失敗不影響交易正確性
        try:
            self._check_low_stock_alerts(cart)           # 庫存警示
        except Exception:
            logger.warning("低庫存檢查失敗，不影響交易")

        return sale
```

**為什麼 Phase A 把月結累計放 transaction 裡？**
- PM 說了：SaleCompleted 事件如果沒觸發，月結金額就少算 = 財務損失
- Phase A 沒有 event bus 的重試機制，放 transaction 裡最安全
- Phase B 有了 event 基礎設施 + 監控後，再抽出來

**Phase B 以後再改成：**
```python
# Phase B 做法：核心同步 + 事件驅動
with db.transaction():
    sale = ...
    stock_movements = ...
    audit_event = ...

# commit 後發事件，由各 handler 處理
event_bus.publish(SaleCompleted(sale_id=sale.sale_id, ...))
# handler: update_inventory_balance
# handler: accumulate_ar
# handler: check_low_stock
```

---

## 2. Phase A 不做清單

### 2.1 明確不做的功能

**Phase A 不做以下功能。任何 PR 包含以下功能的程式碼，一律退回。**

#### AI 相關（全部 Phase B/C）

| 不做 | 原因 | 什麼時候做 |
|------|------|-----------|
| 語意搜尋（Embedding + pgvector 搜尋） | Phase B1 | Phase B |
| 語音搜尋（SpeechAdapter） | Phase C1 | Phase C |
| 拍照搜尋（VisionAdapter） | Phase C1 | Phase C |
| AI 品項補齊（CrawlerAdapter + LLMAdapter） | Phase B2 | Phase B |
| AI 分類建議 | Phase B2 | Phase B |
| AI 替代品建議 | Phase B2 | Phase B |
| AI 重複偵測 | Phase B2 | Phase B |
| AI 採購建議 | Phase B3 | Phase B |
| AI 動態安全庫存 | Phase B3 | Phase B |
| AI 庫存異常偵測 | Phase B3 | Phase B |
| AI 季節預測 | Phase C4 | Phase C |
| AI 客戶流失預警 | Phase B4 | Phase B |
| AI 客戶分群 | Phase C4 | Phase C |
| AI 交叉銷售建議 | Phase C4 | Phase C |
| AI 月結摘要 | Phase B4 | Phase B |
| AI 月結異常標記 | Phase B4 | Phase B |
| AI 日報 / 週報 | Phase C3 | Phase C |
| AI 洞察（趨勢/異常） | Phase C3 | Phase C |
| AI 價格建議 | Phase C4 | Phase C |
| AISuggestion 模型 | Phase B | Phase B |
| FeedbackLoop | Phase B | Phase B |
| 信任度自動放行 | Phase C | Phase C |
| LLM 自動客服 | Phase C2 | Phase C |

#### LINE 相關（全部 Phase C）

| 不做 | 什麼時候做 |
|------|-----------|
| LINE Webhook 串接 | Phase C2 |
| LINE 訊息接收/回覆 | Phase C2 |
| LINE 自動回覆 | Phase C2 |
| LINE 報價單 | Phase C 以後 |
| LINE 帳單通知 | Phase C 以後 |

#### 報表（Phase A 只做基礎查詢，不做儀表板）

| 不做 | 什麼時候做 |
|------|-----------|
| 圖表儀表板 | Phase C3 |
| 營收趨勢圖 | Phase C3 |
| 毛利分析 | Phase C3 |
| 庫存周轉率 | Phase C3 |
| PDF / Excel 匯出（月結單 PDF 除外） | Phase C3 |

#### 進階功能

| 不做 | 什麼時候做 |
|------|-----------|
| 多租戶 tenant_id | 未定 |
| 電子發票串接 | 未定 |
| PLC / MQTT 串接 | Phase D（獨立專案） |
| product_substitute（替代品）表 | Phase B2 |
| product_ai_enrichment 表 | Phase B2 |
| product_search_doc.embedding 欄位 | Phase B1 |
| Domain Event Bus（Redis pub/sub） | Phase B |
| Celery 背景任務（爬蟲、AI 批次） | Phase B |
| 報價單 / 訂單草稿 | 未定（可能在 Phase B 後插隊） |

### 2.2 Phase A 要做的完整清單

| 子階段 | 交付物 |
|--------|--------|
| **A0 骨架** | FastAPI + PostgreSQL + Flutter + Docker + 登入 + 備份 |
| **A1 品項** | product_master + SKU + Category CRUD + 凌越匯入 + 關鍵字搜尋 + 條碼搜尋 |
| **A2 POS** | POS 介面 + 掃碼 + 購物車 + 結帳 + 收據列印 + Sale + SaleLine + StockMovement |
| **A3 庫存** | 進貨驗收 + Supplier + PurchaseOrder + InventoryBalance + 安全庫存警示 + 盤點 |
| **A4 客戶月結** | Customer + AccountsReceivable + 月結單彙整 + 逾期提醒 + PDF |
| **A5 凌越退場** | 並行運行 + 數據比對 + 切換 + 離線基礎版 + Bug 修復 |

### 2.3 Phase A 建立但不使用的表

以下表在 Phase A migration 中建立（佔位），但 Phase A 不寫入資料、不建 API：

| 表 | 建立原因 | 使用時間 |
|----|---------|---------|
| `product_search_docs` | product_master 的搜尋附屬表，Phase A 只用 search_text，不用 embedding | Phase B1 填 embedding |
| `operational_alerts` | Phase A 就開始用（庫存警示、逾期提醒） | **Phase A 就用** |
| `system_jobs` | Phase A 就開始用（備份紀錄） | **Phase A 就用** |
| `review_tasks` | Phase A 就開始用（盤點差異、月結確認） | **Phase A 就用** |

以下表 Phase A **不建立**，Phase B 再加 migration：

| 表 | 使用時間 |
|----|---------|
| `product_ai_enrichments` | Phase B2 |
| `product_substitutes` | Phase B2 |
| `ai_suggestions` | Phase B |

---

## 3. Phase A 限制規則（給 Claude Code）

1. 不得 import 任何 AI 相關套件（openai, anthropic, langchain 等）
2. 不得建立 infrastructure/ai/ 目錄下的任何檔案
3. 不得建立 LINE 相關程式碼
4. 搜尋功能只用 DB LIKE / PostgreSQL 全文搜尋，不用向量搜尋
5. 不得在 product_search_docs 表寫入 embedding 欄位
6. 不得建立 ai_suggestions 表
7. 所有跨模組操作放在同一個 DB transaction 內，不用 event bus
8. 不得使用 event_bus.publish() 或任何事件發佈機制
9. 報表只做基礎查詢 API，不做圖表、不做 AI 摘要
10. 庫存更新必須透過 StockMovement → InventoryBalance，不得直接改 current_stock
11. 每個 API route 必須有 require_role 權限檢查
12. iPhone 的 Level C 模組用 FeatureLockedPage，不要花時間做完整 UI
13. 不得把簡單功能過度 DDD 化（不需要 Aggregate Root、Value Object 全套）
14. 優先完成 Windows Desktop 版型，再調整 iPad 版型，最後處理 iPhone
15. 不得提前做事件驅動（Phase A 用 transaction 同步，不用 event bus）

---

## 4. 跨裝置策略

**詳細分級規格見「跨裝置功能分級與開放策略」文件。以下為 Phase A 的重點摘要。**

### 4.1 三端定位

| 裝置 | 定位 | Phase A 開發深度 |
|------|------|-----------------|
| Windows 桌面版 | 主戰場 | 所有模組 Level A（完整版） |
| iPad 平板版 | 現場作業 + 簡化管理 | 作業功能 Level A + 管理功能 Level B |
| iPhone 手機版 | 輕量管理 + 隨身決策 | 查詢/審核/通知 Level A，其餘 Level B 或 C |

### 4.2 各子階段的裝置開發範圍

| 子階段 | Windows | iPad | iPhone |
|--------|---------|------|--------|
| A0 骨架 | 登入頁 | 登入頁 | 登入頁 |
| A1 品項 | 品項 CRUD + 搜尋 | 品項搜尋 + 基本編輯 | 品項搜尋 + 查看 |
| A2 POS | 完整 POS | 簡化 POS（掃碼+常用品+基本付款） | FeatureLockedPage |
| A3 庫存 | 完整庫存 + 進貨驗收 + 盤點 | 庫存查詢 + 進貨驗收 + 盤點 | 庫存查詢 + 單品盤點 |
| A4 客戶月結 | 完整客戶 + 月結 | 客戶查詢 + 應收查看 + 標記收款 | 客戶查詢 + 標記收款 |
| A5 凌越退場 | Bug 修復 + 穩定化 | 同步穩定 | 同步穩定 |

### 4.3 開發順序（每個模組）

```
1. 後端 API（一套，不分裝置）
2. State Management / Provider（一套）
3. Desktop Layout（完整版）
4. Tablet Layout（調整版型，功能可能簡化）
5. Phone Layout（大部分用 FeatureLockedPage）
6. Feature Flags 設定
```

### 4.4 硬規則

- **不做裝置專用 API**（禁止 /api/mobile/、/api/tablet/）
- **不做裝置專用 State**（一個模組一個 Provider，三端共用）
- **Level C 的模組也要註冊 route + 建立 page 骨架**（未來改 flag 就開）
- **FeatureLockedPage 是引導頁不是錯誤頁**（「請在桌面版操作」）
- **Feature Flags 集中在一個 class**，不散落各處
