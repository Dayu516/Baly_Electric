"""凌越資料清洗工具 — 獨立 CLI，不屬於主系統。

Usage:
    python cleaner.py --input input/raw.csv --output output/
    python cleaner.py --input input/raw.csv --output output/ --sample 100
    python cleaner.py --input input/raw.csv --output output/ --resume

流程：
    1. 讀取凌越 CSV（自動偵測 big5 / utf-8）
    2. 每批 N 筆送 Claude API 分析
    3. 每批完成即存進度檔（斷點續傳）
    4. 全部完成後輸出標準化 CSV，分三桶（auto/review/manual）
    5. auto.csv 可直接餵主系統 ImportCatalogService
"""

import argparse
import csv
import json
import os
import sys
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


# ═══════════════════════════════════════════════════════
# Data Model
# ═══════════════════════════════════════════════════════
@dataclass
class CleanedRow:
    name: str = ""               # 標準化品名
    raw_name: str = ""           # 原始品名
    brand: str = ""
    series: str = ""
    model_number: str = ""
    spec: str = ""
    barcode: str = ""
    supplier_code: str = ""
    internal_code: str = ""
    unit: str = "個"
    sell_price: float = 0
    cost_price: float = 0
    min_stock: int = 0
    item_type: str = "finished"  # finished / assembly / accessory / component
    category_path: str = ""      # 分類路徑，如 "開關與保護元件>接觸器類>裸接觸器"
    structured_attrs: str = "{}" # JSON 結構化屬性
    aliases: str = ""            # AI 建議的別名（逗號分隔）
    parse_remark: str = ""       # AI 未能解析的片段
    confidence: float = 0        # AI 信心分數 0~1
    bucket: str = "manual"       # auto / review / manual
    # 保留舊欄位給相容
    category: str = ""


FIELDNAMES = list(CleanedRow.__dataclass_fields__.keys())

# 匯出用欄位（對齊主系統 ImportCatalogService）
EXPORT_FIELDNAMES = [
    "name", "raw_name", "brand", "series", "model_number", "spec",
    "barcode", "supplier_code", "internal_code", "unit", "sell_price",
    "cost_price", "min_stock", "item_type", "category_path",
    "structured_attrs", "aliases", "parse_remark",
]


# ═══════════════════════════════════════════════════════
# 分類路徑對照表
# ═══════════════════════════════════════════════════════
CATEGORY_PATHS = [
    "開關與保護元件>接觸器類>裸接觸器",
    "開關與保護元件>接觸器類>積熱電驛",
    "開關與保護元件>接觸器類>電磁開關",
    "開關與保護元件>接觸器類>接觸器零件",
    "開關與保護元件>斷路器類>無熔絲開關",
    "開關與保護元件>斷路器類>漏電斷路器",
    "開關與保護元件>保險絲類>保險絲",
    "開關與保護元件>保險絲類>保險絲座",
    "控制開關與操作元件>按鈕開關",
    "控制開關與操作元件>選擇開關",
    "控制開關與操作元件>指示燈",
    "控制開關與操作元件>微動開關",
    "控制開關與操作元件>限動開關",
    "繼電器與控制模組>一般繼電器",
    "繼電器與控制模組>計時器",
    "繼電器與控制模組>監控保護模組",
    "PLC與自動化控制>PLC",
    "PLC與自動化控制>HMI 人機介面",
    "PLC與自動化控制>工業通訊模組",
    "變頻器與驅動>變頻器",
    "變頻器與驅動>伺服系統",
    "變頻器與驅動>軟啟動器",
    "電源與供電>開關電源",
    "電源與供電>變壓器",
    "電源與供電>UPS / 電池",
    "感測器與儀表>接近開關",
    "感測器與儀表>光電開關",
    "感測器與儀表>溫度感測器",
    "感測器與儀表>儀表",
    "端子與連接材料>端子台",
    "端子與連接材料>壓著端子",
    "端子與連接材料>連接器",
    "端子與連接材料>配線附件",
    "電線電纜>控制電纜",
    "電線電纜>動力電纜",
    "電線電纜>通訊線",
    "配電盤與箱體>箱體",
    "配電盤與箱體>DIN 軌道",
    "配電盤與箱體>母排 / 安裝件",
    "氣動與電磁閥>電磁閥本體",
    "氣動與電磁閥>電磁閥線圈",
    "氣動與電磁閥>氣動元件",
    "工具與耗材>手工具",
    "工具與耗材>電動工具",
    "工具與耗材>耗材",
    "工具與耗材>安裝配件",
]

# ═══════════════════════════════════════════════════════
# 各分類的結構化屬性 key
# ═══════════════════════════════════════════════════════
CATEGORY_ATTR_KEYS = {
    "開關與保護元件>接觸器類>裸接觸器": ["品牌", "系列", "框架型號", "主接點數", "單接點額定電流(A)", "輔助接點配置", "線圈電壓", "額定使用類別", "適用HP", "適用kW"],
    "開關與保護元件>接觸器類>積熱電驛": ["品牌", "系列", "額定電流範圍", "適用HP"],
    "開關與保護元件>接觸器類>電磁開關": ["品牌", "系列", "接觸器框架型號", "線圈電壓", "積熱型號", "積熱電流", "適用HP", "適用kW"],
    "開關與保護元件>接觸器類>接觸器零件": ["零件類型", "適用框架型號", "電壓"],
    "開關與保護元件>斷路器類>無熔絲開關": ["品牌", "系列", "框架型號", "極數", "額定電流", "遮斷容量", "安裝方式"],
    "開關與保護元件>斷路器類>漏電斷路器": ["品牌", "系列", "極數", "額定電流", "漏電靈敏度", "遮斷容量"],
    "控制開關與操作元件>按鈕開關": ["品牌", "系列", "孔徑", "顏色", "接點型式", "自復/保持", "是否照光", "燈壓", "頭部型式"],
    "控制開關與操作元件>選擇開關": ["品牌", "系列", "孔徑", "段數", "接點型式", "長柄/短柄", "是否照光", "燈壓"],
    "控制開關與操作元件>指示燈": ["品牌", "系列", "孔徑", "顏色", "發光方式", "電壓", "是否可換燈泡", "燈泡型號"],
    "繼電器與控制模組>一般繼電器": ["品牌", "型號", "線圈電壓", "接點數", "接點型式", "底座型號"],
    "繼電器與控制模組>計時器": ["品牌", "型號", "電壓", "時間範圍", "功能類型", "接點數"],
    "端子與連接材料>端子台": ["品牌", "型號", "適用線徑", "層數", "軌道規格"],
    "電線電纜>控制電纜": ["品牌", "線徑", "芯數", "遮蔽", "外被材質", "電壓等級", "柔性等級"],
    "電線電纜>動力電纜": ["品牌", "線徑", "芯數", "電壓等級"],
    "電源與供電>開關電源": ["品牌", "型號", "輸入電壓", "輸出電壓", "輸出電流", "瓦數"],
    "電源與供電>變壓器": ["品牌", "型號", "一次側電壓", "二次側電壓", "容量"],
    "變頻器與驅動>變頻器": ["品牌", "型號", "輸入電壓", "輸出相數", "功率", "適用馬達"],
    "PLC與自動化控制>PLC": ["品牌", "系列", "型號", "點數", "IO 類型", "通訊介面"],
    "氣動與電磁閥>電磁閥本體": ["品牌", "系列", "口數位數", "接口尺寸", "作動方式", "配管尺寸"],
    "氣動與電磁閥>電磁閥線圈": ["品牌", "適用閥體型號", "電壓", "功率", "插頭型式"],
}


# ═══════════════════════════════════════════════════════
# System Prompt
# ═══════════════════════════════════════════════════════
SYSTEM_PROMPT = """你是電控材料行的品項資料整理專家。你非常熟悉台灣電料行業的品牌、產品系列、規格命名。

你的任務是把雜亂的品項資料標準化。

輸入：一批品項的原始資料
輸出：JSON array，每筆包含以下欄位：

1. name: 標準化品名，格式「品牌 系列 類型 關鍵規格」
   範例：「士林 S-P11 裸接觸器 3P 20A AC220V」「OMRON MY2N 繼電器 DC24V」
   沒品牌就省略，如「輕便電纜 0.5X12C」

2. brand: 品牌，不確定就留空字串
   常見縮寫對照：SL=士林、TE=東元、OM=OMRON、SE=施耐德、FJ=富士

3. series: 系列/產品線（S-P、MY2N、SC-N2...），沒有就留空

4. model_number: 完整型號，沒有就留空

5. spec: 規格文字（如「3P 20A」「DC24V」「2.0mm² 白色」）

6. category_path: 分類路徑，必須從以下清單中精確選一個，不可自己發明：
""" + "\n".join(f"   - {c}" for c in CATEGORY_PATHS) + """

   判不出分類 → category_path 留空字串，不要猜。

7. item_type: 品項型態，判斷規則：
   - 品名含 "MSO" 或 "電磁開關" → "assembly"
   - 品名含 "線圈" 且分類是接觸器或電磁閥 → "component"
   - 品名含 "底座" "安裝板" "配件" → "accessory"
   - 其他 → "finished"

8. structured_attrs: JSON 物件，根據 category_path 對應的屬性清單，從品名中解析出結構化屬性。
   各分類可用的 key：
""" + "\n".join(
    f"   {cat}: {', '.join(keys)}"
    for cat, keys in CATEGORY_ATTR_KEYS.items()
) + """

   沒有對應分類模板的品項 → structured_attrs 給空物件 {}
   只填能確定的 key，不確定的不要填。

9. aliases: 這個品項可能的口語叫法（逗號分隔）。
   想想現場師傅或客人會怎麼叫這個東西。每筆至少 1~2 個。

10. parse_remark: AI 無法解析的片段，留給人工修正。
    完全能解析 → 留空字串。

11. confidence: 信心分數 0~1
    0.9+  = 很確定（品名清楚、品牌型號明確、分類確定）
    0.7~0.9 = 大致可信（能推斷但有些不確定）
    <0.7  = 不確定（品名模糊、無法判斷分類或品牌）

處理順序：先判分類 → 再判型態 → 再拆規格填 structured_attrs → 最後評信心

規則：
- 品名已經清楚的，直接整理格式，信心給高
- 品名模糊的，盡量猜但降信心
- 完全看不懂的，name 保留原文，信心 0.3 以下
- 不要瞎猜品牌，不確定就留空
- aliases 要實用，想想現場師傅會怎麼講
- structured_attrs 的 key 必須精確匹配上面列出的 key，不可自創
- 解析不了的部分放 parse_remark，不要猜

只回覆 JSON array，不要其他文字。
"""


# ═══════════════════════════════════════════════════════
# CSV 讀取（自動偵測編碼）
# ═══════════════════════════════════════════════════════
def read_raw_csv(path: str) -> list[dict]:
    """讀取 CSV，自動嘗試 utf-8-sig → big5 → cp950。"""
    for encoding in ["utf-8-sig", "big5", "cp950", "utf-8"]:
        try:
            with open(path, "r", encoding=encoding) as f:
                reader = csv.DictReader(f)
                rows = [dict(row) for row in reader]
            if rows:
                print(f"  編碼偵測: {encoding}")
                return rows
        except (UnicodeDecodeError, UnicodeError):
            continue

    print(f"ERROR: 無法讀取 {path}，請確認檔案編碼")
    sys.exit(1)


# ═══════════════════════════════════════════════════════
# AI 呼叫（Claude / Ollama）
# ═══════════════════════════════════════════════════════
_use_ollama = False
_ollama_model = "qwen3.5:9b"


def call_ai(rows_text: str, api_key: str, max_retries: int = 3) -> list[dict]:
    """呼叫 AI（自動選 Ollama 或 Claude）。"""
    if _use_ollama:
        return call_ollama(rows_text, max_retries)
    return call_claude(rows_text, api_key, max_retries)


def call_claude(rows_text: str, api_key: str, max_retries: int = 3) -> list[dict]:
    """呼叫 Claude API，含重試。"""
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)

    for attempt in range(max_retries):
        try:
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=8192,
                system=SYSTEM_PROMPT,
                messages=[
                    {"role": "user", "content": f"請分析以下品項資料：\n\n{rows_text}"},
                ],
            )

            text = response.content[0].text
            return _extract_json(text, attempt, max_retries)

        except json.JSONDecodeError as e:
            print(f"    [WARN] JSON 解析失敗: {e}，重試 ({attempt+1}/{max_retries})")
        except Exception as e:
            print(f"    [WARN] API 呼叫失敗: {e}，等待重試 ({attempt+1}/{max_retries})")
            if attempt < max_retries - 1:
                wait = 2 ** (attempt + 1)
                print(f"    等待 {wait} 秒...")
                time.sleep(wait)

    print("    [ERROR] 多次重試失敗，此批次將標記為 manual")
    return []


def call_ollama(rows_text: str, max_retries: int = 3) -> list[dict]:
    """呼叫本地 Ollama，含重試。"""
    import httpx

    # 關掉 Qwen3 思考模式 + 強調 JSON 輸出
    prompt = "/no_think\n" + SYSTEM_PROMPT + "\n\n重要：只回覆 JSON array，不要任何解釋、不要 markdown code block，直接以 [ 開頭。\n\n請分析以下品項資料：\n\n" + rows_text

    for attempt in range(max_retries):
        try:
            resp = httpx.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": _ollama_model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.1,
                        "num_predict": 8192,
                        "num_ctx": 16384,
                    },
                },
                timeout=300,
            )
            result = resp.json()

            text = result.get("response", "")
            parsed = _extract_json(text, attempt, max_retries)
            if parsed:
                return parsed

        except (json.JSONDecodeError, ValueError) as e:
            print(f"    [WARN] JSON 解析失敗: {e}，重試 ({attempt+1}/{max_retries})")
        except Exception as e:
            print(f"    [WARN] Ollama 呼叫失敗: {e}，重試 ({attempt+1}/{max_retries})")
            if attempt < max_retries - 1:
                time.sleep(2)

    print("    [ERROR] 多次重試失敗，此批次將標記為 manual")
    return []


def _extract_json(text: str, attempt: int, max_retries: int) -> list[dict]:
    """從 AI 回應中提取 JSON array。"""
    # 去掉 Qwen3 思考區塊
    import re
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    # 去掉 markdown code block
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        # 找第一個 [ 和最後一個 ]
        text = "\n".join(lines[1:])
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3]

    start = text.find("[")
    end = text.rfind("]") + 1
    if start >= 0 and end > start:
        return json.loads(text[start:end])

    print(f"    [WARN] 回應無 JSON array，重試 ({attempt+1}/{max_retries})")
    return []


# ═══════════════════════════════════════════════════════
# 處理邏輯
# ═══════════════════════════════════════════════════════
def classify_bucket(confidence: float) -> str:
    if confidence >= 0.85:
        return "auto"
    elif confidence >= 0.6:
        return "review"
    else:
        return "manual"


def process_batch(raw_rows: list[dict], api_key: str, batch_num: int, total_batches: int) -> list[CleanedRow]:
    """處理一批原始資料。"""
    lines = []
    for i, row in enumerate(raw_rows):
        parts = []
        for k, v in row.items():
            if v and str(v).strip():
                parts.append(f"{k}: {str(v).strip()}")
        lines.append(f"{i+1}. {', '.join(parts)}")

    rows_text = "\n".join(lines)
    ai_results = call_ai(rows_text, api_key)

    cleaned = []
    for i, raw in enumerate(raw_rows):
        ai = ai_results[i] if i < len(ai_results) else {}
        confidence = float(ai.get("confidence", 0.3))

        # 原始欄位取值（支援中/英欄位名）
        raw_name = _get(raw, "品名", "name", "product_name", "品項名稱")
        raw_barcode = _get(raw, "條碼", "barcode", "商品條碼")
        raw_supplier = _get(raw, "供應商料號", "supplier_code", "供應商編號")
        raw_internal = _get(raw, "內部編號", "internal_code", "凌越編號", "料號", "品號")
        raw_unit = _get(raw, "單位", "unit") or "個"

        # structured_attrs 處理
        structured_attrs = ai.get("structured_attrs", {})
        if isinstance(structured_attrs, dict):
            structured_attrs_str = json.dumps(structured_attrs, ensure_ascii=False)
        elif isinstance(structured_attrs, str):
            structured_attrs_str = structured_attrs
        else:
            structured_attrs_str = "{}"

        cleaned.append(CleanedRow(
            name=ai.get("name") or raw_name,
            raw_name=raw_name,
            brand=ai.get("brand", _get(raw, "廠牌", "brand", "品牌") or ""),
            series=ai.get("series", ""),
            model_number=ai.get("model_number", _get(raw, "型號", "model_number", "model") or ""),
            spec=ai.get("spec", _get(raw, "規格", "spec", "規格描述") or ""),
            barcode=raw_barcode,
            supplier_code=raw_supplier,
            internal_code=raw_internal,
            unit=raw_unit,
            sell_price=_to_float(_get(raw, "售價", "sell_price", "單價")),
            cost_price=_to_float(_get(raw, "成本", "cost_price", "進價")),
            min_stock=0,
            item_type=ai.get("item_type", "finished"),
            category_path=ai.get("category_path", ""),
            category=ai.get("category_path", ""),  # 相容舊欄位
            structured_attrs=structured_attrs_str,
            aliases=ai.get("aliases", ""),
            parse_remark=ai.get("parse_remark", ""),
            confidence=confidence,
            bucket=classify_bucket(confidence),
        ))

    return cleaned


def _get(row: dict, *keys: str) -> str:
    """從 dict 中嘗試多個 key 取值。"""
    for k in keys:
        v = row.get(k)
        if v and str(v).strip():
            return str(v).strip()
    return ""


def _to_float(val: str) -> float:
    if not val:
        return 0
    try:
        return float(str(val).strip().replace(",", ""))
    except (ValueError, TypeError):
        return 0


# ═══════════════════════════════════════════════════════
# 斷點續傳
# ═══════════════════════════════════════════════════════
PROGRESS_FILE = ".cleaner_progress.json"


def save_progress(output_dir: str, completed_batches: int, all_cleaned: list[CleanedRow]):
    """儲存進度，斷點續傳用。"""
    progress_path = Path(output_dir) / PROGRESS_FILE
    progress_path.parent.mkdir(parents=True, exist_ok=True)

    data = {
        "completed_batches": completed_batches,
        "total_cleaned": len(all_cleaned),
        "timestamp": datetime.now().isoformat(),
        "rows": [asdict(r) for r in all_cleaned],
    }
    with open(progress_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_progress(output_dir: str) -> tuple[int, list[CleanedRow]]:
    """載入進度。回傳 (已完成批次數, 已清洗的資料)。"""
    progress_path = Path(output_dir) / PROGRESS_FILE
    if not progress_path.exists():
        return 0, []

    with open(progress_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    rows = [CleanedRow(**{k: v for k, v in r.items() if k in CleanedRow.__dataclass_fields__}) for r in data.get("rows", [])]
    completed = data.get("completed_batches", 0)
    print(f"  載入進度：已完成 {completed} 批，{len(rows)} 筆")
    return completed, rows


# ═══════════════════════════════════════════════════════
# 輸出
# ═══════════════════════════════════════════════════════
def write_output(cleaned: list[CleanedRow], output_dir: str):
    """分三桶 + 完整版 + 別名表 輸出 CSV。"""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    buckets = {"auto": [], "review": [], "manual": []}
    for row in cleaned:
        buckets[row.bucket].append(row)

    for bucket_name, rows in buckets.items():
        path = output_path / f"{bucket_name}.csv"
        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=EXPORT_FIELDNAMES)
            writer.writeheader()
            for row in rows:
                d = asdict(row)
                writer.writerow({k: d.get(k, "") for k in EXPORT_FIELDNAMES})
        print(f"  {bucket_name}.csv: {len(rows)} 筆")

    # 完整版
    all_path = output_path / "all_cleaned.csv"
    with open(all_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        for row in cleaned:
            writer.writerow(asdict(row))
    print(f"  all_cleaned.csv: {len(cleaned)} 筆")

    # 別名表（給主系統 product_aliases 用）
    aliases_path = output_path / "aliases.csv"
    with open(aliases_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["name", "alias", "alias_type"])
        writer.writeheader()
        for row in cleaned:
            if row.aliases:
                for alias in row.aliases.split(","):
                    alias = alias.strip()
                    if alias and alias != row.name:
                        writer.writerow({
                            "name": row.name,
                            "alias": alias,
                            "alias_type": "common",
                        })
    print(f"  aliases.csv: 別名對應表")

    # 清掉進度檔
    progress_path = output_path / PROGRESS_FILE
    if progress_path.exists():
        progress_path.unlink()
        print(f"  進度檔已清除")


# ═══════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════
def main():
    parser = argparse.ArgumentParser(
        description="凌越資料清洗工具 — 把雜亂品項標準化",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
範例：
  python cleaner.py --input input/raw.csv --output output/
  python cleaner.py --input input/raw.csv --output output/ --sample 50
  python cleaner.py --input input/raw.csv --output output/ --resume
        """,
    )
    parser.add_argument("--input", required=True, help="輸入 CSV 路徑")
    parser.add_argument("--output", default="output/", help="輸出目錄（預設 output/）")
    parser.add_argument("--sample", type=int, default=0, help="只處理前 N 筆（測試用）")
    parser.add_argument("--batch-size", type=int, default=20, help="每批送 AI 的筆數（預設 20）")
    parser.add_argument("--resume", action="store_true", help="從上次中斷處繼續")
    parser.add_argument("--ollama", type=str, nargs="?", const="qwen3.5:9b", default=None,
                        help="用 Ollama 本地模型（預設 qwen3.5:9b），如 --ollama llama3:8b")
    args = parser.parse_args()

    global _use_ollama, _ollama_model
    if args.ollama:
        _use_ollama = True
        _ollama_model = args.ollama
        print(f"使用 Ollama 本地模型: {_ollama_model}")
        api_key = "ollama"  # 不需要 API key
    else:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            print("ERROR: 請設定 ANTHROPIC_API_KEY，或用 --ollama 改用本地模型")
            sys.exit(1)

    # 讀取原始資料
    print(f"\n{'='*50}")
    print(f"  凌越資料清洗工具 v2")
    print(f"{'='*50}\n")
    print(f"讀取: {args.input}")
    raw_rows = read_raw_csv(args.input)
    total_raw = len(raw_rows)
    print(f"共 {total_raw} 筆原始資料")

    if args.sample > 0:
        raw_rows = raw_rows[:args.sample]
        print(f"取樣模式：只處理前 {args.sample} 筆")

    # 斷點續傳
    start_batch = 0
    all_cleaned: list[CleanedRow] = []

    if args.resume:
        start_batch, all_cleaned = load_progress(args.output)

    total_batches = (len(raw_rows) + args.batch_size - 1) // args.batch_size
    start_time = time.time()

    print(f"\n開始處理（批次大小: {args.batch_size}，共 {total_batches} 批）\n")

    for batch_idx in range(start_batch, total_batches):
        start = batch_idx * args.batch_size
        end = min(start + args.batch_size, len(raw_rows))
        batch = raw_rows[start:end]

        elapsed = time.time() - start_time
        if batch_idx > start_batch:
            done = batch_idx - start_batch
            eta = elapsed / done * (total_batches - batch_idx)
            eta_str = f"，預估剩餘 {int(eta//60)}:{int(eta%60):02d}"
        else:
            eta_str = ""

        print(f"[{batch_idx+1}/{total_batches}] 第 {start+1}~{end} 筆{eta_str}")

        cleaned = process_batch(batch, api_key, batch_idx + 1, total_batches)
        all_cleaned.extend(cleaned)

        # 每批存進度
        save_progress(args.output, batch_idx + 1, all_cleaned)

        # 即時統計
        auto_n = sum(1 for r in cleaned if r.bucket == "auto")
        review_n = sum(1 for r in cleaned if r.bucket == "review")
        manual_n = sum(1 for r in cleaned if r.bucket == "manual")
        print(f"    -> auto: {auto_n}, review: {review_n}, manual: {manual_n}")

    # 輸出
    total_time = time.time() - start_time
    print(f"\n{'='*50}")
    print(f"清洗完成！共 {len(all_cleaned)} 筆，耗時 {int(total_time//60)}:{int(total_time%60):02d}")
    print(f"{'='*50}\n")

    print(f"輸出到: {args.output}")
    write_output(all_cleaned, args.output)

    # 最終統計
    auto_count = sum(1 for r in all_cleaned if r.bucket == "auto")
    review_count = sum(1 for r in all_cleaned if r.bucket == "review")
    manual_count = sum(1 for r in all_cleaned if r.bucket == "manual")
    total = len(all_cleaned)

    print(f"\n分桶統計：")
    print(f"  auto  （直接匯入）: {auto_count:>5} 筆 ({auto_count*100//total:>2}%)")
    print(f"  review（快速確認）: {review_count:>5} 筆 ({review_count*100//total:>2}%)")
    print(f"  manual（人工處理）: {manual_count:>5} 筆 ({manual_count*100//total:>2}%)")

    print(f"\n下一步：")
    print(f"  1. python migrate_csv.py  # 匯入 SQLite")
    print(f"  2. python app.py          # 啟動 Web UI 審查")
    print(f"  3. 審查完成後，Web UI 點「匯入主系統」")


if __name__ == "__main__":
    main()
