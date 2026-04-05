"""Data Cleaner Web UI — SQLite 版。

Usage:
    cd tools/data-cleaner
    pip install -r requirements.txt
    python migrate_csv.py          # 首次：CSV → SQLite
    python app.py                  # 啟動 Web UI
    # 打開 http://localhost:8501
"""

import csv
import io
import os
from dataclasses import asdict
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File, Request
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse

from cleaner import (
    CleanedRow, FIELDNAMES, EXPORT_FIELDNAMES, CATEGORY_PATHS,
    read_raw_csv, process_batch, classify_bucket,
)
from database import (
    init_db, get_db,
    insert_products, count_products, query_products, get_product,
    update_product, delete_product, batch_update_products, batch_delete_products,
    get_stats, get_distinct_brands, get_distinct_categories, get_distinct_item_types,
    export_products, get_importable_products, mark_imported,
    insert_customers, count_customers, query_customers,
    get_importable_customers, mark_customers_imported,
    PRODUCT_COLS, EXPORT_FIELDNAMES as DB_EXPORT_FIELDNAMES,
)

load_dotenv()
init_db()

app = FastAPI(title="Data Cleaner")

# 清洗進度（僅清洗期間用，非持久化）
_cleaning = {"status": "idle", "progress": 0, "total": 0}


# ═══════════════════════════════════════════════════════
# Pages
# ═══════════════════════════════════════════════════════
@app.get("/", response_class=HTMLResponse)
async def index():
    html_path = Path(__file__).parent / "templates" / "index.html"
    return html_path.read_text(encoding="utf-8")


# ═══════════════════════════════════════════════════════
# 上傳 + 清洗
# ═══════════════════════════════════════════════════════
@app.post("/api/upload")
async def upload_csv(file: UploadFile = File(...)):
    """上傳 CSV 並寫入 SQLite。"""
    content = await file.read()
    for enc in ["utf-8-sig", "big5", "cp950", "utf-8"]:
        try:
            text = content.decode(enc)
            break
        except (UnicodeDecodeError, UnicodeError):
            continue
    else:
        return JSONResponse({"error": "無法解碼檔案"}, status_code=400)

    reader = csv.DictReader(io.StringIO(text))
    raw_rows = [dict(r) for r in reader]
    columns = list(raw_rows[0].keys()) if raw_rows else []

    return {
        "total": len(raw_rows),
        "columns": columns,
        "preview": raw_rows[:5],
        "filename": file.filename,
    }


@app.post("/api/clean")
async def start_cleaning(request: Request):
    """開始 AI 清洗，結果直接寫入 SQLite。"""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return JSONResponse({"error": "未設定 ANTHROPIC_API_KEY"}, status_code=400)

    body = await request.json()
    # 支援直接傳 raw_rows 或從檔案讀取
    raw_rows = body.get("rows", [])
    batch_size = body.get("batch_size", 20)

    if not raw_rows:
        return JSONResponse({"error": "沒有資料可清洗"}, status_code=400)

    _cleaning["status"] = "cleaning"
    _cleaning["total"] = len(raw_rows)
    _cleaning["progress"] = 0

    total_batches = (len(raw_rows) + batch_size - 1) // batch_size
    all_cleaned = []

    for batch_idx in range(total_batches):
        start = batch_idx * batch_size
        end = min(start + batch_size, len(raw_rows))
        batch = raw_rows[start:end]
        cleaned = process_batch(batch, api_key, batch_idx + 1, total_batches)
        all_cleaned.extend([asdict(r) for r in cleaned])
        _cleaning["progress"] = end

    # 寫入 SQLite
    insert_products(all_cleaned)
    _cleaning["status"] = "idle"

    return get_stats()


@app.get("/api/status")
async def get_cleaning_status():
    return {
        "status": _cleaning["status"],
        "progress": _cleaning["progress"],
        "total": _cleaning["total"],
    }


@app.post("/api/load-results")
async def load_existing_results():
    """載入 output/all_cleaned.csv 到 SQLite（如果 DB 是空的）。"""
    existing = count_products()
    if existing > 0:
        return get_stats()

    results_path = Path("output/all_cleaned.csv")
    if not results_path.exists():
        return JSONResponse({"error": "output/all_cleaned.csv 不存在且資料庫為空"}, status_code=404)

    with open(results_path, "r", encoding="utf-8-sig") as f:
        rows = [dict(r) for r in csv.DictReader(f)]

    for row in rows:
        for col in ["sell_price", "cost_price", "confidence"]:
            try:
                row[col] = float(row.get(col, 0) or 0)
            except (ValueError, TypeError):
                row[col] = 0

    insert_products(rows)
    return get_stats()


# ═══════════════════════════════════════════════════════
# 品項 CRUD（Phase 1 SQLite + Phase 2 搜尋/排序/篩選）
# ═══════════════════════════════════════════════════════
@app.get("/api/stats")
async def api_stats():
    """取得分桶統計 + 審查進度。"""
    return get_stats()


@app.get("/api/items")
async def get_items(
    bucket: str = "all",
    page: int = 1,
    per_page: int = 50,
    search: str = "",
    brand: str = "",
    category: str = "",
    item_type: str = "",
    sort_by: str = "id",
    sort_dir: str = "asc",
):
    """取得品項（分頁 + 搜尋 + 排序 + 篩選）。"""
    total = count_products(bucket=bucket, search=search, brand=brand, category=category, item_type=item_type)
    items = query_products(
        bucket=bucket, page=page, per_page=per_page,
        search=search, brand=brand, category=category, item_type=item_type,
        sort_by=sort_by, sort_dir=sort_dir,
    )
    total_pages = max(1, (total + per_page - 1) // per_page)
    return {"items": items, "total": total, "page": page, "per_page": per_page, "total_pages": total_pages}


@app.put("/api/items/{item_id}")
async def api_update_item(item_id: int, request: Request):
    """更新單筆品項。"""
    body = await request.json()

    # 手動確認的自動提升 bucket
    if body.get("confirmed"):
        body["bucket"] = "auto"
        body["confirmed"] = 1
        existing = get_product(item_id)
        if existing and float(existing.get("confidence", 0)) < 0.95:
            body["confidence"] = 0.95

    update_product(item_id, body)
    item = get_product(item_id)
    return {"ok": True, "item": item}


@app.delete("/api/items/{item_id}")
async def api_delete_item(item_id: int):
    ok = delete_product(item_id)
    return {"ok": ok}


@app.post("/api/batch-update")
async def api_batch_update(request: Request):
    body = await request.json()
    ids = body.get("ids", [])
    updates = body.get("updates", {})
    count = batch_update_products(ids, updates)
    return {"ok": True, "updated": count}


@app.post("/api/batch-delete")
async def api_batch_delete(request: Request):
    body = await request.json()
    ids = body.get("ids", [])
    count = batch_delete_products(ids)
    return {"ok": True, "deleted": count}


# ═══════════════════════════════════════════════════════
# 品牌 + 分類
# ═══════════════════════════════════════════════════════
@app.get("/api/brands")
async def list_brands():
    return {"brands": get_distinct_brands()}


@app.get("/api/categories-local")
async def list_local_categories():
    """從 SQLite 取得已有的分類清單。"""
    return {"categories": get_distinct_categories()}


@app.get("/api/category-paths")
async def list_category_paths():
    """取得完整分類路徑對照表。"""
    return {"paths": CATEGORY_PATHS}


@app.get("/api/item-types")
async def list_item_types():
    return {"types": get_distinct_item_types()}


_categories_cache: list[dict] = []

@app.get("/api/categories")
async def list_categories():
    """從主系統拉分類樹。"""
    if not _categories_cache:
        try:
            import httpx
            c = httpx.Client(timeout=5)
            r = c.post("http://localhost:8000/api/v1/auth/login", json={"username": "1", "password": "1"})
            token = r.json()["access_token"]
            r = c.get("http://localhost:8000/api/v1/products/categories/tree",
                       headers={"Authorization": f"Bearer {token}"})
            _categories_cache.extend(r.json()["data"])
        except Exception:
            # 主系統不在線，用本地分類
            cats = get_distinct_categories()
            return {"data": [], "local_categories": cats}
    return {"data": _categories_cache}


# ═══════════════════════════════════════════════════════
# 匯出
# ═══════════════════════════════════════════════════════
@app.get("/api/export")
async def api_export_csv(bucket: str = "auto"):
    items = export_products(bucket)
    output = io.StringIO()
    fieldnames = EXPORT_FIELDNAMES
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for item in items:
        writer.writerow({k: item.get(k, "") for k in fieldnames})
    output.seek(0)
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8-sig")),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={bucket}_cleaned.csv"},
    )


@app.get("/api/export-aliases")
async def api_export_aliases():
    items = export_products("all")
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=["name", "alias", "alias_type"])
    writer.writeheader()
    for item in items:
        aliases_str = item.get("aliases", "")
        if aliases_str:
            for alias in aliases_str.split(","):
                alias = alias.strip()
                if alias and alias != item.get("name", ""):
                    writer.writerow({"name": item["name"], "alias": alias, "alias_type": "common"})
    output.seek(0)
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8-sig")),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=aliases.csv"},
    )


# ═══════════════════════════════════════════════════════
# Phase 3: 匯入主系統
# ═══════════════════════════════════════════════════════
MAIN_SYSTEM_URL = "http://localhost:8000"


async def _get_main_token() -> str | None:
    """從主系統取得 JWT token。"""
    try:
        import httpx
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(
                f"{MAIN_SYSTEM_URL}/api/v1/auth/login",
                json={"username": "1", "password": "1"},
            )
            if r.status_code == 200:
                return r.json().get("access_token")
    except Exception:
        pass
    return None


@app.get("/api/import-preview")
async def import_preview(target: str = "products"):
    """預覽匯入（顯示將匯入幾筆、跳過幾筆）。"""
    if target == "products":
        # 可匯入 = auto bucket + 未匯入
        auto_items = get_importable_products("auto")
        stats = get_stats()
        return {
            "target": "products",
            "ready": len(auto_items),
            "already_imported": stats["imported"],
            "total": stats["total"],
            "review_pending": stats["review"],
            "manual_pending": stats["manual"],
        }
    elif target == "customers":
        customers = get_importable_customers()
        total = count_customers()
        return {
            "target": "customers",
            "ready": len(customers),
            "already_imported": total - len(customers),
            "total": total,
        }
    return JSONResponse({"error": "target must be products or customers"}, status_code=400)


@app.post("/api/import-to-main")
async def import_to_main(request: Request):
    """匯入品項到主系統。"""
    body = await request.json()
    target = body.get("target", "products")
    bucket = body.get("bucket", "auto")

    token = await _get_main_token()
    if not token:
        return JSONResponse({"error": "無法連接主系統或登入失敗"}, status_code=502)

    if target == "products":
        items = get_importable_products(bucket)
        if not items:
            return {"ok": True, "imported": 0, "message": "沒有可匯入的品項"}

        # 產生 CSV 內容（用匯出欄位格式）
        output = io.StringIO()
        fieldnames = EXPORT_FIELDNAMES
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        for item in items:
            writer.writerow({k: item.get(k, "") for k in fieldnames})
        csv_bytes = output.getvalue().encode("utf-8-sig")

        # 呼叫主系統 import API
        try:
            import httpx
            async with httpx.AsyncClient(timeout=60) as client:
                r = await client.post(
                    f"{MAIN_SYSTEM_URL}/api/v1/import",
                    headers={"Authorization": f"Bearer {token}"},
                    files={"file": ("import.csv", csv_bytes, "text/csv")},
                )
                result = r.json()
        except Exception as e:
            return JSONResponse({"error": f"匯入失敗: {e}"}, status_code=502)

        if result.get("success"):
            imported_ids = [item["id"] for item in items]
            mark_imported(imported_ids)
            return {
                "ok": True,
                "imported": result["data"]["imported"],
                "skipped": result["data"]["skipped_duplicate"],
                "errors": result["data"].get("errors", []),
            }
        else:
            return JSONResponse({"error": result.get("message", "匯入失敗")}, status_code=400)

    elif target == "customers":
        # 客戶目前主系統沒有 bulk import API，用逐筆方式
        customers = get_importable_customers()
        if not customers:
            return {"ok": True, "imported": 0, "message": "沒有可匯入的客戶"}

        imported_count = 0
        errors = []
        try:
            import httpx
            async with httpx.AsyncClient(timeout=60) as client:
                for cust in customers:
                    try:
                        r = await client.post(
                            f"{MAIN_SYSTEM_URL}/api/v1/customers",
                            headers={
                                "Authorization": f"Bearer {token}",
                                "Content-Type": "application/json",
                            },
                            json={
                                "name": cust["name"],
                                "short_name": cust.get("short_name", ""),
                                "customer_type": cust.get("customer_type", "company"),
                                "phone": cust.get("phone", ""),
                                "mobile": cust.get("mobile", ""),
                                "fax": cust.get("fax", ""),
                                "address": cust.get("address", ""),
                                "tax_id": cust.get("unino", ""),
                                "contact_person": cust.get("contact", ""),
                                "payment_terms": cust.get("payment_terms", "cash"),
                                "credit_limit": float(cust.get("credit_limit", 0) or 0),
                                "note": cust.get("note", ""),
                            },
                        )
                        if r.status_code in (200, 201):
                            imported_count += 1
                        else:
                            errors.append(f"{cust['name']}: {r.text[:100]}")
                    except Exception as e:
                        errors.append(f"{cust['name']}: {e}")
        except Exception as e:
            return JSONResponse({"error": f"客戶匯入失敗: {e}"}, status_code=502)

        if imported_count > 0:
            mark_customers_imported([c["id"] for c in customers[:imported_count]])

        return {
            "ok": True,
            "imported": imported_count,
            "errors": errors[:20],
        }

    return JSONResponse({"error": "target must be products or customers"}, status_code=400)


@app.post("/api/import-aliases")
async def import_aliases_to_main(request: Request):
    """匯入別名到主系統。"""
    token = await _get_main_token()
    if not token:
        return JSONResponse({"error": "無法連接主系統"}, status_code=502)

    items = export_products("all")
    imported_count = 0
    errors = []

    try:
        import httpx
        async with httpx.AsyncClient(timeout=120) as client:
            # 先取得主系統的品項列表來對應 product_id
            r = await client.get(
                f"{MAIN_SYSTEM_URL}/api/v1/products?per_page=10000",
                headers={"Authorization": f"Bearer {token}"},
            )
            if r.status_code != 200:
                return JSONResponse({"error": "無法取得主系統品項列表"}, status_code=502)

            products_data = r.json().get("data", {}).get("items", [])
            name_to_id = {p["name"]: p["product_id"] for p in products_data}

            for item in items:
                product_id = name_to_id.get(item.get("name"))
                if not product_id:
                    continue
                aliases_str = item.get("aliases", "")
                if not aliases_str:
                    continue
                for alias in aliases_str.split(","):
                    alias = alias.strip()
                    if not alias or alias == item.get("name"):
                        continue
                    try:
                        r = await client.post(
                            f"{MAIN_SYSTEM_URL}/api/v1/aliases/{product_id}",
                            headers={
                                "Authorization": f"Bearer {token}",
                                "Content-Type": "application/json",
                            },
                            json={"alias": alias, "alias_type": "common"},
                        )
                        if r.status_code in (200, 201):
                            imported_count += 1
                    except Exception as e:
                        errors.append(f"{alias}: {e}")
    except Exception as e:
        return JSONResponse({"error": f"別名匯入失敗: {e}"}, status_code=502)

    return {"ok": True, "imported": imported_count, "errors": errors[:20]}


# ═══════════════════════════════════════════════════════
# 客戶查詢
# ═══════════════════════════════════════════════════════
@app.get("/api/customers")
async def api_customers(page: int = 1, per_page: int = 50, search: str = ""):
    total = count_customers()
    items = query_customers(page=page, per_page=per_page, search=search)
    total_pages = max(1, (total + per_page - 1) // per_page)
    return {"items": items, "total": total, "page": page, "total_pages": total_pages}


# ═══════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════
if __name__ == "__main__":
    import uvicorn
    print("\n" + "=" * 50)
    print("  Data Cleaner Web UI (SQLite)")
    print("  打開瀏覽器：http://localhost:8501")
    print("=" * 50 + "\n")
    uvicorn.run(app, host="127.0.0.1", port=8501)
