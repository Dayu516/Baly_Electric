"""客戶資料清洗 — 規則式，不需要 AI。

Usage:
    python clean_customers.py --input input/lingyue_customers.csv --output output/customers_cleaned.csv
"""

import argparse
import csv
import re
import sys
from pathlib import Path


def clean_name(name: str) -> tuple[str, str]:
    """清洗客戶名稱。回傳 (清洗後名稱, 從名稱中提取的統編)。"""
    if not name:
        return "", ""

    name = name.strip()
    # 全形轉半形
    name = name.replace("\u3000", " ").replace("（", "(").replace("）", ")")

    # 從名稱尾巴提取統編（8位數字）
    extracted_unino = ""
    match = re.search(r'(\d{8})\s*$', name)
    if match:
        extracted_unino = match.group(1)
        name = name[:match.start()].strip()

    # (股) → 股份有限公司 的簡寫，保留
    return name, extracted_unino


def clean_phone(phone: str) -> tuple[str, str]:
    """分離多支電話。回傳 (主電話, 手機)。"""
    if not phone:
        return "", ""

    phone = phone.strip()
    # 常見分隔：空白、/、,
    parts = re.split(r'[\s/,]+', phone)

    main_phone = ""
    mobile = ""

    for p in parts:
        p = p.strip()
        if not p:
            continue
        # 手機：09 開頭
        if p.startswith("09") and len(p) >= 10:
            if not mobile:
                mobile = p
        else:
            if not main_phone:
                main_phone = p

    return main_phone, mobile


def clean_address(addr: str) -> str:
    """清洗地址。"""
    if not addr:
        return ""

    addr = addr.strip()
    # 移除開頭的郵遞區號（3位數字）
    addr = re.sub(r'^\d{3}', '', addr).strip()
    # 移除換行
    addr = addr.replace("\n", "").replace("\r", "")
    # 台 → 臺 統一（或反過來，看習慣）
    # 保留原樣比較好，不強制統一
    return addr


def detect_customer_type(name: str, unino: str) -> str:
    """判斷客戶類型。"""
    if unino:
        return "company"
    company_keywords = ["公司", "企業", "股份", "有限", "行", "工程", "工廠", "實業", "科技"]
    for kw in company_keywords:
        if kw in name:
            return "company"
    return "individual"


def detect_payment_terms(pay_code: str) -> str:
    """凌越付款方式代碼轉換。"""
    # 凌越常見：1=月結, 2=現金, 其他看系統設定
    # 先用保守預設，之後再確認
    return "monthly_credit" if pay_code == "1" else "cash"


def main():
    parser = argparse.ArgumentParser(description="客戶資料清洗")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", default="output/customers_cleaned.csv")
    args = parser.parse_args()

    # 讀取
    rows = []
    for enc in ["utf-8-sig", "big5", "cp950"]:
        try:
            with open(args.input, "r", encoding=enc) as f:
                rows = list(csv.DictReader(f))
            break
        except (UnicodeDecodeError, UnicodeError):
            continue

    if not rows:
        print("ERROR: 無法讀取檔案")
        sys.exit(1)

    print(f"讀取 {len(rows)} 筆客戶資料")

    # 清洗
    cleaned = []
    dupes = {}  # 用名稱去重

    for row in rows:
        raw_name = (row.get("客戶名稱") or row.get("name") or "").strip()
        if not raw_name or raw_name == "=":
            continue

        name, extracted_unino = clean_name(raw_name)
        unino = (row.get("統編") or row.get("unino") or extracted_unino or "").strip()
        if not unino and extracted_unino:
            unino = extracted_unino

        short_name = (row.get("簡稱") or row.get("short_name") or "").strip()
        address = clean_address(row.get("地址") or row.get("address") or "")

        raw_phone = (row.get("電話") or row.get("phone") or "").strip()
        phone, mobile = clean_phone(raw_phone)

        fax = (row.get("傳真") or row.get("fax") or "").strip()
        contact = (row.get("聯絡人") or row.get("contact") or "").strip()
        pay_code = (row.get("付款方式") or row.get("payment") or "").strip()
        credit_limit = row.get("信用額度") or row.get("credit_limit") or "0"
        note = (row.get("備註") or row.get("note") or "").strip()
        internal_code = (row.get("客戶編號") or row.get("customer_id") or "").strip()

        customer_type = detect_customer_type(name, unino)
        payment_terms = detect_payment_terms(pay_code)

        # 去重檢查
        dedup_key = name.replace(" ", "")
        if dedup_key in dupes:
            dupes[dedup_key]["note"] += f" [重複: {internal_code}]"
            continue

        record = {
            "name": name,
            "raw_name": raw_name,
            "short_name": short_name,
            "customer_type": customer_type,
            "phone": phone,
            "mobile": mobile,
            "fax": fax,
            "address": address,
            "unino": unino,
            "contact": contact,
            "payment_terms": payment_terms,
            "credit_limit": credit_limit,
            "internal_code": internal_code,
            "note": note,
        }
        cleaned.append(record)
        dupes[dedup_key] = record

    # 輸出
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["name", "raw_name", "short_name", "customer_type", "phone", "mobile",
                  "fax", "address", "unino", "contact", "payment_terms", "credit_limit",
                  "internal_code", "note"]

    with open(args.output, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in cleaned:
            writer.writerow(r)

    companies = sum(1 for r in cleaned if r["customer_type"] == "company")
    individuals = sum(1 for r in cleaned if r["customer_type"] == "individual")
    monthly = sum(1 for r in cleaned if r["payment_terms"] == "monthly_credit")
    dupe_count = len(rows) - len(cleaned)

    print(f"\n清洗完成：")
    print(f"  總筆數：{len(cleaned)} 筆（去重 {dupe_count} 筆）")
    print(f"  公司：{companies}  個人：{individuals}")
    print(f"  月結：{monthly}  現金：{len(cleaned) - monthly}")
    print(f"  輸出：{args.output}")


if __name__ == "__main__":
    main()