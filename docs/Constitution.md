# 開發憲法（跨 Phase 永久生效）

本文件為整個專案（Phase A / B / C）共用之核心架構規範。

所有後續開發必須遵守本文件之規則。

若現有程式碼與本文件衝突：
👉 以本文件為準（程式碼需修正）

---

## 1. 交易一致性規則

### 1.1 核心原則

- **同一個 DB transaction 裡的操作，要嘛全成功、要嘛全失敗**
- **transaction commit 之後才做非關鍵操作**（通知、統計、AI）

### 1.2 Transaction 邊界定義

**每個 use case 的 transaction 包含哪些表，必須嚴格遵守。**

#### 結帳（CheckoutService.checkout）

```
Transaction 內（同步，強一致）：
  ✅ INSERT sale
  ✅ INSERT sale_lines（N 筆）
  ✅ INSERT stock_movements（N 筆，quantity 為負）
  ✅ UPDATE inventory_balance（N 筆 SKU 的 current_stock）
  ✅ INSERT/UPDATE accounts_receivable（月結客戶）
  ✅ INSERT audit_event

Transaction 外（commit 後，失敗不影響交易）：
  ⚡ 檢查低庫存 → 建立 OperationalAlert
  ⚡ [Phase B] 發送 SaleCompleted 事件
```

#### 進貨驗收（PurchaseOrderService.receive_order）

```
Transaction 內：
  ✅ INSERT purchase_receipt
  ✅ INSERT stock_movements（N 筆，quantity 為正）
  ✅ UPDATE inventory_balance（N 筆 SKU 的 current_stock）
  ✅ UPDATE purchase_order_lines.received_quantity
  ✅ UPDATE purchase_order.status（如果全部收齊 → received）
  ✅ INSERT audit_event

Transaction 外（best-effort，失敗不影響驗收）：
  ⚡ 有 source_sale_line_id 的 PO line → BackorderService.mark_arrived()
  ⚡ 進價異常 → 建立 OperationalAlert(warning)
  ⚡ [Phase B] 新品項 → 建立 AISuggestion
```

**進價異常判定規則：**
- 比較基準：`supplier_products.unit_cost`（該 SKU 該供應商的既有進價）
- 異常門檻：本次驗收 `unit_cost > 基準 × 1.2`（漲幅超過 20%）
- severity：`warning`
- alert_type：`price_anomaly`
- 若基準不存在（首次進貨）：不觸發
- 若本次 unit_cost 為 null：不觸發

#### 盤點調整（StockCountService.adjust）

```
Transaction 內：
  ✅ INSERT stock_movements（adjustment 類型）
  ✅ UPDATE inventory_balance
  ✅ UPDATE review_task.status = completed
  ✅ INSERT audit_event

Transaction 外：
  ⚡ 無
```

#### 月結單生成（GenerateStatementService.generate）

```
Transaction 內：
  ✅ INSERT accounts_receivable
  ✅ INSERT review_task（monthly_reconcile，待人工確認）
  ✅ INSERT audit_event

Transaction 外：
  ⚡ [Phase B] AI 生成摘要 → AISuggestion
```

#### 審核通過（ReviewSuggestionService.approve）

```
Transaction 內：
  ✅ UPDATE review_task.status = completed
  ✅ UPDATE 目標主檔（依 review_type 不同）
  ✅ [Phase B] UPDATE ai_suggestion.status = approved
  ✅ INSERT audit_event

Transaction 外：
  ⚡ [Phase B] AI feedback 更新
```

#### 報價轉銷貨（QuotationService.convert_to_sale）

```
Transaction 內（同步，強一致）：
  ✅ INSERT sale
  ✅ INSERT sale_lines（N 筆）
  ✅ INSERT stock_movements（N 筆，quantity 為負）
  ✅ UPDATE inventory_balance（N 筆 SKU 的 current_stock）
  ✅ UPDATE quotation.status = converted
  ✅ INSERT audit_event

Transaction 外（commit 後，失敗不影響交易）：
  ⚡ 檢查低庫存 → 建立 OperationalAlert
```

#### 退貨 / 作廢（VoidSaleService.void）

```
Transaction 內：
  ✅ UPDATE sale.status = voided
  ✅ INSERT stock_movements（quantity 為正，退回庫存）
  ✅ UPDATE inventory_balance
  ✅ UPDATE accounts_receivable（月結客戶退款）
  ✅ INSERT audit_event

Transaction 外：
  ⚡ 無
```

### 1.3 InventoryBalance 更新規則

**每筆 StockMovement 同步更新 InventoryBalance。**

```python
def create_stock_movement(self, sku_id, quantity, movement_type, reference_type, reference_id, ...):
    with db.transaction():
        # 1. 寫入異動紀錄
        movement = StockMovement(
            sku_id=sku_id,
            quantity=quantity,          # 正=入庫，負=出庫
            movement_type=movement_type,
            reference_type=reference_type,
            reference_id=reference_id,
            ...
        )
        db.add(movement)

        # 2. 同步更新餘額（用 DB 層 atomic update，避免 race condition）
        db.execute("""
            UPDATE inventory_balance
            SET current_stock = current_stock + :qty,
                updated_at = NOW()
            WHERE sku_id = :sku_id
        """, {"qty": quantity, "sku_id": sku_id})
```

**為什麼用 DB 層 `current_stock + :qty` 而不是 Python 先讀再寫？**
- 避免 race condition：兩個人同時結帳同一品項時，DB 層 atomic update 不會覆蓋
- 這是唯一允許在 repository 裡寫原生 SQL 的地方

**重算機制（StockRecalcService）：**
- 盤點後觸發
- 手動觸發（Owner 功能）
- 做法：`UPDATE inventory_balance SET current_stock = (SELECT SUM(quantity) FROM stock_movements WHERE sku_id = ...) WHERE sku_id = ...`
- 重算完記錄 `last_recalc_at`

### 1.4 並行安全規則

| 場景 | 處理方式 |
|------|---------|
| 兩人同時結帳同一 SKU | DB atomic update `current_stock + qty`，不會衝突 |
| 兩人同時修改同一品項 | Optimistic Lock（version check），後者收到衝突錯誤 |
| 結帳時庫存已為 0 | 允許負庫存（電控行常見：先賣再補），但產生 OperationalAlert |
| 盤點與結帳同時進行 | 盤點紀錄盤點當下數字，結帳照常。差異在盤點完成時比對 |

---

## 2. 錯誤恢復策略

### 2.1 核心原則

- **關鍵失敗必須被看見**，不能只寫 log
- **使用者永遠有退路**，不會被卡住
- **資料寧可多記不可少記**

### 2.2 錯誤分級

| 等級 | 定義 | 處理方式 | 例子 |
|------|------|---------|------|
| **Critical** | 交易資料可能不一致 | 停止操作 + OperationalAlert(critical) + 通知 Owner | DB transaction 失敗、庫存重算不一致 |
| **Warning** | 功能受限但核心可用 | 降級 + OperationalAlert(warning) + 記 log | AI 掛了、印表機斷線、LINE API 失敗 |
| **Info** | 小問題，自動處理 | 自動重試或忽略 + 記 log | 爬蟲某網站暫時無法連線 |

### 2.3 各場景錯誤恢復

#### 收據列印失敗

```
場景：結帳完成，但印表機沒反應
    ↓
處理：
  1. 交易已寫入 DB → 不會受影響（DB 先於印表機）
  2. UI 顯示「列印失敗」+ 「重新列印」按鈕
  3. 交易紀錄裡標記 receipt_printed = false
  4. 老闆娘可以之後再印

絕對不會發生：
  ✗ 印表機失敗 → 交易回滾（不可以）
  ✗ 卡在印表機等待 → 無法繼續結帳（不可以）
```

#### DB Transaction 失敗

```
場景：結帳過程中 DB 寫入失敗
    ↓
處理：
  1. 整個 transaction rollback → 什麼都沒寫入
  2. UI 顯示「結帳失敗，請重試」
  3. 購物車內容保留，不會清掉
  4. 記 error log + OperationalAlert(critical)
  5. 如果連續失敗 → 提示「系統異常，請聯繫管理員」

使用者退路：
  手寫收據 → 稍後補單（提供「補建歷史交易」功能）
```

#### AI Adapter 失敗

```
場景：呼叫 LLM / Embedding / Vision / Speech API 失敗
    ↓
處理：
  1. 增強功能自動降級（見 v5 第 5 章降級規則）
  2. 記 warning log（含 adapter 名、錯誤碼、latency）
  3. 連續失敗 N 次 → OperationalAlert(warning) 通知 Owner
  4. 不影響任何必需功能
```

#### 離線同步中斷

```
場景：離線交易上傳到一半，網路又斷了
    ↓
處理：
  1. 已上傳成功的 → server 確認收到（ACK）→ 本地標記已同步
  2. 未上傳的 → 繼續保留在離線暫存區
  3. 下次連線自動繼續上傳（從斷點續傳，不重傳已 ACK 的）
  4. UI 顯示「同步中斷，還有 N 筆待同步」

防止重複上傳：
  每筆離線交易有 client_tx_id（UUID，client 端生成）
  server 端用 client_tx_id 做冪等檢查
  同一筆上傳兩次 → server 忽略第二次
```

#### 離線同步衝突（主檔類）

```
場景：離線時修改了品項售價，上線後發現 server 端也被改過了
    ↓
處理：
  1. Server 比對 version → 不一致 = 衝突
  2. 回傳 server 版本 + client 版本
  3. UI 顯示衝突對照表：
     ┌─────────────────────────────────────────┐
     │  欄位       Server 版本    你的版本       │
     │  售價       $150          $180           │
     │  修改人     老闆          老闆娘          │
     │  修改時間   03/28 14:00   03/28 15:30    │
     │                                         │
     │  [保留 Server 版本]  [保留我的版本]       │
     └─────────────────────────────────────────┘
  4. 使用者選擇後，以選擇版本寫入 + version +1
  5. 記 AuditEvent（含衝突解決過程）
```

#### 庫存重算不一致

```
場景：StockRecalcService 重算後，發現 SUM(movements) ≠ inventory_balance
    ↓
處理：
  1. 這代表有某筆 movement 或 balance 更新出了問題
  2. 以 SUM(movements) 為準（movements 是 append-only 真相）
  3. 更新 inventory_balance 為正確值
  4. 產生 OperationalAlert(critical)：「SKU xxx 庫存不一致，已自動修正」
  5. 記 AuditEvent（含修正前後數值）
  6. Owner 應調查根因
```

#### 備份失敗

```
場景：每日自動備份 DB 失敗
    ↓
處理：
  1. SystemJob.status = failed + error_message
  2. 產生 OperationalAlert(critical) 通知 Owner
  3. 自動重試 1 次（30 分鐘後）
  4. 仍失敗 → 再次通知 Owner
  5. 連續 3 天失敗 → 強制通知（Owner 不可忽略）
```

#### Event Handler 失敗（Phase B 以後）

```
Phase B 規則：
  1. handler 失敗 → 記 error log + 標記 event 為 failed
  2. 自動重試 3 次（exponential backoff：1s, 5s, 30s）
  3. 仍失敗 → OperationalAlert(warning) + 進入 dead letter queue
  4. Owner 可在系統管理頁看到失敗事件 + 手動重觸發
  5. 關鍵 handler（如月結累計）在無 event bus 時放 transaction 內
```

---

## 3. 資料字典 / 命名規範

### 3.1 ID 命名規則

| 規則 | 格式 | 例子 |
|------|------|------|
| 主鍵命名 | `{entity}_id` | `sale_id`, `sku_id`, `product_id` |
| 外鍵命名 | 與目標主鍵同名 | `customer_id`, `supplier_id` |
| 主鍵型別 | `UUID`（所有表統一） | `550e8400-e29b-41d4-a716-446655440000` |
| 禁止 | auto-increment int 做主鍵 | 離線同步時 ID 會衝突 |

**為什麼用 UUID：**
- 離線時 client 端可自行生成 ID，上線同步不衝突
- 不暴露業務量（auto-increment 的 sale_id = 5000 暴露你賣了 5000 筆）

### 3.2 時間欄位規則

| 欄位名 | 用途 | 必填 | 說明 |
|--------|------|------|------|
| `created_at` | 建立時間 | 是 | DB default = NOW()，不可修改 |
| `updated_at` | 最後更新時間 | 是 | 每次 UPDATE 自動更新 |
| `confirmed_at` | 人工確認時間 | 否 | 只有需要確認的實體才有 |
| `claimed_at` | 領取時間 | 否 | ReviewTask 專用 |
| `resolved_at` | 處理完成時間 | 否 | ReviewTask 專用 |
| `received_at` | 驗收時間 | 否 | PurchaseReceipt 專用 |
| `expires_at` | 過期時間 | 否 | OperationalAlert / AISuggestion |
| `last_login_at` | 最後登入 | 否 | User 專用 |
| `last_recalc_at` | 最後重算 | 否 | InventoryBalance 專用 |

**時間格式統一：**
- DB 儲存：`TIMESTAMP WITH TIME ZONE`（UTC）
- API 傳輸：ISO 8601（`2026-03-30T08:15:30Z`）
- 前端顯示：轉為 local timezone（Asia/Taipei，UTC+8）

### 3.3 Status Enum 統一規範

**原則：每個 entity 的 status enum 獨立定義，但命名風格統一。**

```
命名風格：snake_case，全小寫

Sale.status:
  - completed          交易完成
  - voided             已作廢

PurchaseOrder.status:
  - draft              草稿
  - ordered            已下單
  - partial_received   部分到貨
  - received           全部到貨
  - cancelled          已取消

ReviewTask.status:
  - pending            待處理
  - claimed            已領取（鎖定中）
  - completed          已完成
  - rejected           已退回

ReviewTask.resolution:
  - approved           通過
  - modified           修改後通過
  - rejected           退回

OperationalAlert.severity:
  - info               參考資訊
  - warning            需注意
  - critical           需立即處理

SystemJob.status:
  - running            執行中
  - completed          完成
  - failed             失敗

AccountsReceivable.status:
  - open               未付
  - partial_paid       部分付款
  - paid               已付清
  - overdue            逾期

AISuggestion.status:（Phase B）
  - pending            待審核
  - approved           通過
  - modified           修改後通過
  - rejected           退回
  - auto_approved      自動放行
  - expired            過期未處理

StockMovement.movement_type:
  - sale               銷售出庫
  - purchase_receive   進貨入庫
  - adjustment         盤點調整
  - return             退貨入庫
  - initial            初始庫存（凌越匯入）

StockMovement.reference_type:
  - sale               對應 Sale
  - purchase_receipt   對應 PurchaseReceipt
  - stock_count        對應盤點
  - manual             手動調整
  - import             匯入

Customer.payment_terms:
  - cash               現金
  - monthly_credit     月結

Sale.payment_method:
  - cash               現金
  - transfer           轉帳
  - monthly_credit     月結

ProductSubstitute.compatibility:（Phase B）
  - full               完全相容
  - partial            部分相容
  - needs_check        需確認
```

### 3.4 Quantity 正負號規則

**統一規則：入庫為正，出庫為負。**

| 場景 | StockMovement.quantity | 說明 |
|------|----------------------|------|
| 銷售 | **-N** | 出庫 |
| 進貨入庫 | **+N** | 入庫 |
| 退貨 | **+N** | 退回入庫 |
| 盤點調整（實際比帳面多） | **+N** | 補正 |
| 盤點調整（實際比帳面少） | **-N** | 補正 |
| 初始庫存匯入 | **+N** | 入庫 |

**InventoryBalance.current_stock = SUM(所有 StockMovement.quantity)**

允許負庫存：電控行常見「先賣再叫貨」，不擋結帳，但產生 OperationalAlert。

### 3.5 金額欄位規則

| 規則 | 說明 |
|------|------|
| DB 型別 | `DECIMAL(12, 2)`（不用 FLOAT，避免精度問題） |
| 幣別 | 固定 TWD，不做多幣別 |
| 稅 | 欄位預留，依 Phase 決定何時處理 |
| 折扣 | 存折扣金額 `discount_amount`，不存折扣率 |

### 3.6 DB 表命名規則

| 規則 | 格式 | 例子 |
|------|------|------|
| 表名 | snake_case，複數 | `products`, `skus`, `sales`, `sale_lines` |
| 欄位名 | snake_case | `product_id`, `created_at`, `cost_price` |
| 索引名 | `ix_{table}_{column}` | `ix_skus_barcode`, `ix_stock_movements_sku_id` |
| 唯一約束 | `uq_{table}_{column}` | `uq_users_username` |
| 外鍵約束 | `fk_{table}_{target}` | `fk_skus_product_id` |

### 3.7 API 命名規則

| 規則 | 格式 | 例子 |
|------|------|------|
| URL | `/api/v1/{resource}` 複數 | `/api/v1/products`, `/api/v1/sales` |
| CRUD | `GET / POST / PUT / DELETE` | `GET /api/v1/products/{id}` |
| 操作型 | `POST /api/v1/{resource}/{id}/{action}` | `POST /api/v1/sales/{id}/void` |
| 搜尋 | `GET /api/v1/{resource}/search?q=xxx` | `GET /api/v1/products/search?q=斷路器` |
| 分頁 | `?page=1&per_page=20` | 統一分頁參數 |

### 3.8 程式碼命名規則

| 層 | 語言 | 規則 | 例子 |
|----|------|------|------|
| Domain Model | Python | PascalCase class, snake_case field | `class Sale:`, `sale_id` |
| Application Service | Python | PascalCase class, snake_case method | `CheckoutService.checkout()` |
| Repository | Python | PascalCase class | `SaleRepository.find_by_id()` |
| API Route | Python | snake_case function | `def create_sale():` |
| Flutter Widget | Dart | PascalCase class | `class PosScreen extends StatefulWidget` |
| Flutter 檔案 | Dart | snake_case file | `pos_screen.dart`, `checkout_provider.dart` |

---

## 4. 權限矩陣

### 4.1 API 權限

**S = Staff, M = Manager, O = Owner**
**✅ = 允許, ❌ = 禁止**

#### 品項模組

| API | S | M | O | 備註 |
|-----|---|---|---|------|
| GET /products (列表/搜尋) | ✅ | ✅ | ✅ | |
| GET /products/{id} | ✅ | ✅ | ✅ | |
| POST /products (新增) | ❌ | ✅ | ✅ | |
| PUT /products/{id} (修改) | ❌ | ✅ | ✅ | |
| DELETE /products/{id} (刪除) | ❌ | ❌ | ✅ | 高風險 |
| GET /skus | ✅ | ✅ | ✅ | |
| POST /skus | ❌ | ✅ | ✅ | |
| PUT /skus/{id} | ❌ | ✅ | ✅ | |
| PUT /skus/{id}/price (改價) | ❌ | ✅ | ✅ | 記 AuditEvent |
| DELETE /skus/{id} | ❌ | ❌ | ✅ | 高風險 |
| GET /categories | ✅ | ✅ | ✅ | |
| POST /categories | ❌ | ✅ | ✅ | |
| PUT /categories/{id} | ❌ | ✅ | ✅ | |

#### POS / 銷售模組

| API | S | M | O | 備註 |
|-----|---|---|---|------|
| POST /sales (結帳) | ✅ | ✅ | ✅ | |
| GET /sales (交易紀錄) | ✅ | ✅ | ✅ | Staff 只看自己的 |
| GET /sales/{id} | ✅ | ✅ | ✅ | Staff 只看自己的 |
| POST /sales/{id}/void (作廢) | ❌ | ✅ | ✅ | 記 AuditEvent |
| PUT /sales/{id}/adjust-price (手動調價) | ❌ | ✅ | ✅ | 結帳中調價 |
| POST /sales/backfill (補建歷史交易) | ❌ | ✅ | ✅ | |

#### 庫存模組

| API | S | M | O | 備註 |
|-----|---|---|---|------|
| GET /inventory (庫存查詢) | ✅ | ✅ | ✅ | |
| GET /inventory/{sku_id}/movements | ✅ | ✅ | ✅ | |
| POST /inventory/receive (進貨入庫) | ❌ | ✅ | ✅ | |
| POST /inventory/adjust (手動調整) | ❌ | ✅ | ✅ | 記 AuditEvent |
| POST /inventory/count (盤點提交) | ✅ | ✅ | ✅ | |
| POST /inventory/recalc (庫存重算) | ❌ | ❌ | ✅ | |

#### 採購模組

| API | S | M | O | 備註 |
|-----|---|---|---|------|
| GET /purchase-orders | ✅ | ✅ | ✅ | |
| POST /purchase-orders | ❌ | ✅ | ✅ | |
| PUT /purchase-orders/{id} | ❌ | ✅ | ✅ | |
| POST /purchase-orders/{id}/cancel | ❌ | ✅ | ✅ | |
| GET /suppliers | ✅ | ✅ | ✅ | |
| POST /suppliers | ❌ | ✅ | ✅ | |
| PUT /suppliers/{id} | ❌ | ✅ | ✅ | |

#### 客戶模組

| API | S | M | O | 備註 |
|-----|---|---|---|------|
| GET /customers | ✅ | ✅ | ✅ | |
| GET /customers/{id} | ✅ | ✅ | ✅ | |
| POST /customers | ❌ | ✅ | ✅ | |
| PUT /customers/{id} | ❌ | ✅ | ✅ | |
| PUT /customers/{id}/credit-limit | ❌ | ❌ | ✅ | 高風險 |
| PUT /customers/{id}/discount-rate | ❌ | ✅ | ✅ | |
| GET /accounts-receivable | ❌ | ✅ | ✅ | |
| POST /accounts-receivable/{id}/payment | ❌ | ✅ | ✅ | 記錄收款 |
| POST /accounts-receivable/generate | ❌ | ✅ | ✅ | 產生月結單 |

#### 審核 / 通知

| API | S | M | O | 備註 |
|-----|---|---|---|------|
| GET /reviews (審核待辦) | ✅ | ✅ | ✅ | 依角色過濾可見類型 |
| POST /reviews/{id}/claim (領取) | ✅ | ✅ | ✅ | |
| POST /reviews/{id}/resolve (完成) | ✅ | ✅ | ✅ | 見下方 review 類型權限 |
| GET /alerts (通知) | ✅ | ✅ | ✅ | |
| POST /alerts/{id}/read (標記已讀) | ✅ | ✅ | ✅ | |

#### ReviewTask 類型權限

| review_type | S | M | O |
|-------------|---|---|---|
| product_confirm | ✅ | ✅ | ✅ |
| stock_discrepancy | ✅ | ✅ | ✅ |
| monthly_reconcile | ❌ | ✅ | ✅ |
| llm_reply_review（Phase C） | ❌ | ✅ | ✅ |

#### 系統管理

| API | S | M | O | 備註 |
|-----|---|---|---|------|
| GET /system/jobs | ❌ | ❌ | ✅ | |
| GET /system/audit-events | ❌ | ❌ | ✅ | |
| POST /system/backup (手動備份) | ❌ | ❌ | ✅ | |
| POST /system/recalc-inventory | ❌ | ❌ | ✅ | |
| GET /users | ❌ | ❌ | ✅ | |
| POST /users | ❌ | ❌ | ✅ | |
| PUT /users/{id} | ❌ | ❌ | ✅ | |
| PUT /settings | ❌ | ❌ | ✅ | |

### 4.2 頁面權限

| 頁面 | S | M | O |
|------|---|---|---|
| POS 結帳 | ✅ | ✅ | ✅ |
| 品項查詢 | ✅ | ✅ | ✅ |
| 品項管理（新增/編輯） | ❌ | ✅ | ✅ |
| 庫存查詢 | ✅ | ✅ | ✅ |
| 進貨管理 | ❌ | ✅ | ✅ |
| 盤點 | ✅ | ✅ | ✅ |
| 客戶管理 | ❌ | ✅ | ✅ |
| 月結對帳 | ❌ | ✅ | ✅ |
| 審核待辦池 | ✅ | ✅ | ✅ |
| 通知中心 | ✅ | ✅ | ✅ |
| 報表儀表板 | ❌ | ✅ | ✅ |
| 供應商管理 | ❌ | ✅ | ✅ |
| 帳號管理 | ❌ | ❌ | ✅ |
| 系統設定 | ❌ | ❌ | ✅ |
| 系統工作紀錄 | ❌ | ❌ | ✅ |
| 稽核紀錄 | ❌ | ❌ | ✅ |

### 4.3 權限實作規則

```python
# 後端：每個 route 都用 dependency 檢查角色
from core.security import require_role

@router.post("/products")
def create_product(
    data: ProductCreate,
    user: User = Depends(require_role(["manager", "owner"]))
):
    ...

@router.delete("/products/{id}")
def delete_product(
    id: UUID,
    user: User = Depends(require_role(["owner"]))
):
    ...
```

**硬規則：**
- 每個 API route 必須有 `require_role` dependency，不可省略
- 不靠前端隱藏按鈕做權限控制（前端隱藏是 UX，後端驗證是安全）
- 權限不足 → 回傳 `403 Forbidden` + 錯誤碼 `ERR-SEC-001`
- 所有高風險操作（刪除、改價、作廢、調額度）必須記 AuditEvent

---

## 5. 系統架構規則

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
- 不得直接寫 SQL（SQL 放 infrastructure/persistence/query_service.py）
- 不得直接 import 外部 AI 套件（透過 adapter 介面）

### Infrastructure 層（infrastructure/）
- 所有外部依賴的實作：DB、Redis、AI adapter、LINE、檔案儲存
- Repository 介面的實作（xxx_repo_impl.py）
- 手寫 SQL 集中在 query_service.py
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
- 禁止過度抽象（不需要 DDD 的 Aggregate Root / Value Object / Domain Service 全套）

---

## 6. Application Service 分層落地規則

為確保系統可測試性與長期維護性：

1. Application Service 不得直接依賴 Session
2. Application Service 不得直接使用 ORM model
3. 所有資料存取必須透過 repository abstraction
4. QueryService 僅限查詢，不得做狀態變更
5. raw SQL 僅允許存在於 infrastructure 層
6. 業務邏輯應可透過 mock repository 測試

違反以上任一條：
→ 視為架構錯誤

## 7. Architecture Test 需包含的核心檢查

### 後端（import-linter）

| 規則 | 檢查內容 |
|------|---------|
| domain-no-external | domain/ 不可 import sqlalchemy, fastapi, openai, anthropic, redis, celery |
| domain-no-infra | domain/ 不可 import infrastructure/ |
| api-no-infra | api/ 不可直接 import infrastructure/（必須透過 application） |
| application-no-api | application/ 不可 import api/ |
| application-no-ai | application/ 不可 import openai, anthropic, langchain |
| infra-no-upward | infrastructure/ 不可 import application/ 或 api/ |

### 前端（靠 code review，Flutter 沒有 import-linter）

| 規則 | 檢查內容 |
|------|---------|
| 一套 state | 每個模組只有一個 Provider/Notifier，不可按裝置分 |
| 所有 route 都註冊 | Level C 也要有 route |
| FeatureFlags 集中 | 所有功能開關在 feature_flags.dart |
| 不可裝置專用 API | 不可出現 /api/mobile/ 或 /api/tablet/ |

---

## 8. AuditEvent 落點規則

1. **audit_event 由 API 層負責建立**，放在 `session.commit()` 前
2. 與主交易同一個 session，rollback 時自動消失
3. **必須透過 `AuditService` helper**，不可在 API 層直接操作 ORM
4. Application Service 不負責建 audit_event（避免重複、避免 service 知道 HTTP context）
5. 高風險操作必須記 audit_event：刪除、改價、作廢、調額度、收款、進貨驗收、匯入、月結生成、報價轉銷貨

例外：若未來引入 Workflow 層，audit 可改由 Workflow 統一建立。

---

## 9. Architecture Exception

**本案有一個例外：**

| 例外 | 說明 | 理由 |
|------|------|------|
| InventoryBalance 更新使用原生 SQL | `UPDATE inventory_balance SET current_stock = current_stock + :qty` | 需要 DB 層 atomic update 避免 race condition，ORM 做不到 |

此 SQL 放在 `infrastructure/persistence/repositories/inventory_repo_impl.py`，不違反「SQL 集中」原則（它是 repository 的一部分）。
