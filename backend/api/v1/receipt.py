"""出貨單 API — HTTP 轉接層，不含業務邏輯或 SQL。"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from core.dependencies import CurrentUser, require_role
from database import get_session
from application.sales import build_sales_query_service

router = APIRouter()


@router.get("/{sale_id}")
def get_receipt(
    sale_id: UUID,
    session: Session = Depends(get_session),
    _user: CurrentUser = Depends(require_role(["staff", "manager", "owner"])),
):
    """取得出貨單完整資料（給前端預覽或列印用）。"""
    qs = build_sales_query_service(session)

    sale = qs.get_receipt_sale(str(sale_id))
    if not sale:
        raise HTTPException(status_code=404, detail="交易不存在")

    lines = qs.get_receipt_lines(str(sale_id))

    customer = None
    if sale["customer_id"]:
        customer = qs.get_customer_info(str(sale["customer_id"]))

    return {
        "success": True,
        "data": {
            "sale_id": str(sale["sale_id"]),
            "date": str(sale["created_at"])[:10] if sale["created_at"] else "",
            "time": str(sale["created_at"])[11:19] if sale["created_at"] else "",
            "cashier": sale["cashier_name"] or "",
            "payment_method": sale["payment_method"],
            "tax_included": sale["tax_included"],
            "subtotal": float(sale["subtotal"]),
            "tax_amount": float(sale["tax_amount"]),
            "discount_amount": float(sale["discount_amount"]),
            "total": float(sale["total"]),
            "note": sale["note"] or "",
            "customer": {
                "name": customer["name"] if customer else "",
                "phone": customer["phone"] if customer else "",
                "address": customer["address"] if customer else "",
                "payment_terms": customer["payment_terms"] if customer else "cash",
            } if customer else None,
            "lines": [
                {
                    "product_name": r["product_name"],
                    "spec": r["spec"] or "",
                    "quantity": r["quantity"],
                    "unit_price": float(r["unit_price"]),
                    "discount_amount": float(r["discount_amount"]),
                    "line_total": float(r["line_total"]),
                }
                for r in lines
            ],
        },
    }


@router.get("/{sale_id}/text")
def get_receipt_text(
    sale_id: UUID,
    session: Session = Depends(get_session),
    _user: CurrentUser = Depends(require_role(["staff", "manager", "owner"])),
):
    """產生出貨單純文字格式（給針式印表機用）。"""
    data = get_receipt(sale_id, session, _user)["data"]

    W = 40  # 列寬（字元數，針式印表機標準）
    lines = []

    # 公司抬頭
    lines.append("OTTIMO 電控材料行".center(W))
    lines.append("出 貨 單".center(W))
    lines.append("=" * W)

    # 日期 + 編號
    lines.append(f"日期: {data['date']}  {data['time']}")
    lines.append(f"單號: {data['sale_id'][:8]}")
    lines.append(f"收銀: {data['cashier']}")

    # 客戶
    if data.get("customer"):
        c = data["customer"]
        lines.append(f"客戶: {c['name']}")
        if c.get("phone"):
            lines.append(f"電話: {c['phone']}")
        if c.get("address"):
            lines.append(f"地址: {c['address']}")

    lines.append("-" * W)

    # 明細標題
    lines.append(f"{'品名':<16}{'數量':>4}{'單價':>8}{'小計':>8}")
    lines.append("-" * W)

    # 明細
    for item in data["lines"]:
        name = item["product_name"]
        if len(name) > 16:
            name = name[:15] + "…"
        spec = item["spec"]
        qty = item["quantity"]
        price = item["unit_price"]
        total = item["line_total"]

        lines.append(f"{name:<16}{qty:>4}{price:>8.0f}{total:>8.0f}")
        if spec:
            lines.append(f"  {spec}")

    lines.append("-" * W)

    # 金額
    pay_label = {"cash": "現金", "transfer": "轉帳", "monthly_credit": "月結"}.get(data["payment_method"], data["payment_method"])

    if data["tax_included"] and data["tax_amount"] > 0:
        lines.append(f"{'未稅金額:':>24}{data['subtotal']:>12.0f}")
        lines.append(f"{'稅額 (5%):':>24}{data['tax_amount']:>12.0f}")
        lines.append(f"{'含稅合計:':>24}{data['total']:>12.0f}")
    elif data["tax_amount"] > 0:
        lines.append(f"{'小計:':>24}{data['subtotal']:>12.0f}")
        lines.append(f"{'稅額 (5%):':>24}{data['tax_amount']:>12.0f}")
        lines.append(f"{'合計:':>24}{data['total']:>12.0f}")
    else:
        lines.append(f"{'合計:':>24}{data['total']:>12.0f}")

    if data["discount_amount"] > 0:
        lines.append(f"{'折扣:':>24}{-data['discount_amount']:>12.0f}")

    lines.append(f"付款方式: {pay_label}")

    lines.append("=" * W)
    lines.append("")

    return {"success": True, "text": "\n".join(lines)}
