# Data Cleaner — 凌越資料清洗工具

獨立的一次性 ETL 工具，不屬於主系統。跑完丟。

## 安裝

```bash
cd tools/data-cleaner
pip install -r requirements.txt
cp .env.example .env
# 編輯 .env 填入 ANTHROPIC_API_KEY
```

## 使用流程

### 1. 放原始 CSV 到 input/

從凌越匯出的 CSV，支援 big5 / utf-8 自動偵測。

欄位名稱可以是中文或英文，工具會自動對應：
- 品名 / name / product_name / 品項名稱
- 廠牌 / brand / 品牌
- 型號 / model_number / model
- 規格 / spec / 規格描述
- 條碼 / barcode / 商品條碼
- 單位 / unit
- 售價 / sell_price / 單價
- 成本 / cost_price / 進價
- 內部編號 / internal_code / 凌越編號 / 料號 / 品號
- 供應商料號 / supplier_code / 供應商編號

### 2. 先跑 50 筆測試

```bash
python cleaner.py --input input/raw.csv --output output/ --sample 50
```

看看 AI 分類準不準，信心分數合不合理。

### 3. 確認沒問題，跑全量

```bash
python cleaner.py --input input/raw.csv --output output/
```

如果中途中斷（關掉視窗、網路斷掉），用 `--resume` 繼續：

```bash
python cleaner.py --input input/raw.csv --output output/ --resume
```

### 4. 檢查輸出

```
output/
├── auto.csv          ← 高信心，直接匯入主系統
├── review.csv        ← 中信心，快速看一下就好
├── manual.csv        ← 低信心，一定要人工確認
├── all_cleaned.csv   ← 全部（含信心分數）
└── aliases.csv       ← 別名對應表（匯入 product_aliases）
```

### 5. 匯入主系統

```bash
# auto.csv 直接匯入
curl -X POST http://localhost:8000/api/v1/products/import \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@output/auto.csv"

# review.csv 人工確認後也可以匯入
# manual.csv 逐筆處理
# aliases.csv 另外匯入別名表
```

## 分桶規則

| 信心分數 | 桶 | 意思 |
|---------|-----|------|
| >= 0.85 | auto | 品名清楚、品牌型號明確，直接入 |
| 0.6 ~ 0.85 | review | 大致可信，快速看一眼 |
| < 0.6 | manual | 不確定，必須人工判斷 |

## AI 會做什麼

- 拆解品名 → 品牌 + 系列 + 型號 + 規格
- 歸類到分類樹
- 產生口語別名（師傅會怎麼叫這個東西）
- 給信心分數

## AI 不會做什麼

- 不會瞎猜品牌（不確定就留空）
- 不會直接改主系統資料
- 不會處理圖片或 PDF（那是 Phase B 爬蟲的事）