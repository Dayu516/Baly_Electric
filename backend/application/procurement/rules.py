"""Procurement 純業務邏輯 — 無 DB 依賴，可獨立單元測試。

所有 Procurement 模組的純函數集中在這裡，不分散在各 service 的 private method。
"""

from uuid import UUID

from domain.sales.models import SaleLine


def group_by_supplier(items: list[dict]) -> dict[str, list]:
    """按供應商 ID 分組品項。用於一鍵建 PO 和詢價轉 PO。"""
    by_supplier: dict[str, list] = {}
    for item in items:
        sid = str(item["supplier_id"])
        by_supplier.setdefault(sid, []).append(item)
    return by_supplier


def calculate_subtotal(lines: list[dict]) -> float:
    """從報價/銷貨明細計算未稅小計。"""
    return sum(float(l["quantity"]) * float(l["unit_price"]) for l in lines)


def build_sale_lines_from_quotation(sale_id: UUID, lines: list[dict]) -> list[SaleLine]:
    """從報價明細建立 SaleLine domain objects（轉銷貨用）。"""
    result = []
    for l in lines:
        line_total = float(l["quantity"]) * float(l["unit_price"])
        result.append(SaleLine(
            sale_id=sale_id,
            sku_id=l["sku_id"],
            product_name=l["product_name"],
            spec=l["spec"],
            quantity=l["quantity"],
            unit_price=float(l["unit_price"]),
            line_total=line_total,
            ordered_qty=l["quantity"],
            delivered_qty=l["quantity"],
            fulfillment_status="completed",
        ))
    return result


def determine_payment_method(customer_id: UUID | None) -> str:
    """報價轉銷貨時，根據有無客戶決定付款方式。"""
    return "monthly_credit" if customer_id else "cash"
