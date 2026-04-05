"""Sales 純邏輯 — 不碰 DB，可獨立 unit test。

所有狀態推導、金額計算集中在這裡。
"""

import uuid

from domain.sales.models import Sale, SaleLine
from application.sales.schemas import CartItem


# ── 履約狀態推導 ─────────────────────────────────────────


def derive_fulfillment_status(line: SaleLine) -> str:
    """從 qty 欄位推導 fulfillment_status。"""
    qty = line.ordered_qty or line.quantity
    delivered = line.delivered_qty
    backorder = line.backorder_qty
    bo_delivered = line.backorder_delivered_qty

    if qty == 0:
        return "cancelled"

    # 全部交完（含補交）
    total_delivered = delivered + bo_delivered
    if total_delivered >= qty:
        return "completed"

    # 沒有欠貨
    if backorder == 0:
        if delivered >= qty:
            return "fully_delivered"
        elif delivered > 0:
            return "partially_delivered"
        return "pending"

    # 有欠貨
    bo_arrived = line.backorder_arrived_qty
    bo_ordered = line.backorder_ordered_qty

    if bo_delivered > 0 and bo_delivered < backorder:
        return "partially_picked_up"
    if bo_arrived >= backorder:
        return "ready_for_pickup"
    if bo_arrived > 0:
        return "waiting_arrival"  # 部分到，部分還在等
    if bo_ordered > 0:
        return "waiting_arrival"
    if delivered > 0:
        return "partially_backordered"
    return "backordered"


def derive_backorder_status(line: SaleLine) -> str | None:
    """從 qty 欄位推導 backorder_status。無欠貨回 None。"""
    if line.backorder_qty == 0:
        return None

    bo_qty = line.backorder_qty
    bo_ordered = line.backorder_ordered_qty
    bo_arrived = line.backorder_arrived_qty
    bo_delivered = line.backorder_delivered_qty

    if bo_delivered >= bo_qty:
        return "delivered"
    if bo_delivered > 0:
        return "partial_delivered"
    if bo_arrived >= bo_qty:
        return "arrived"
    if bo_arrived > 0:
        return "partial_arrived"
    if bo_ordered > 0:
        return "ordered"
    return "pending"


def update_line_statuses(line: SaleLine) -> SaleLine:
    """一次推導兩個狀態，回傳同一個 line（in-place 更新）。"""
    line.fulfillment_status = derive_fulfillment_status(line)
    line.backorder_status = derive_backorder_status(line)
    return line


def derive_has_backorder(lines: list[SaleLine]) -> bool:
    """從所有 line 推導 sale.has_backorder。"""
    return any(
        line.backorder_qty > line.backorder_delivered_qty
        for line in lines
        if line.backorder_qty > 0
    )


# ── 金額計算 ─────────────────────────────────────────────


def calculate_line_total(unit_price: float, quantity: int, discount_amount: float) -> float:
    """單行明細金額。"""
    return unit_price * quantity - discount_amount


def calculate_tax(after_discount: float, tax_mode: str) -> tuple[float, float, float, bool]:
    """根據 tax_mode 計算稅額。

    Returns:
        (subtotal, tax_amount, total, tax_included)
    """
    if tax_mode == "included":
        subtotal = round(after_discount / 1.05, 2)
        tax_amount = round(after_discount - subtotal, 2)
        total = after_discount
        tax_included = True
    elif tax_mode == "extra":
        subtotal = after_discount
        tax_amount = round(after_discount * 0.05, 2)
        total = subtotal + tax_amount
        tax_included = True
    else:
        subtotal = after_discount
        tax_amount = 0
        total = after_discount
        tax_included = False
    return subtotal, tax_amount, total, tax_included


def build_sale_lines(sale_id: uuid.UUID, items: list[CartItem]) -> list[SaleLine]:
    """CartItem 列表轉 SaleLine domain objects。"""
    lines = []
    for item in items:
        line_total = calculate_line_total(item.unit_price, item.quantity, item.discount_amount)
        lines.append(SaleLine(
            sale_id=sale_id,
            sku_id=item.sku_id,
            product_name=item.product_name,
            spec=item.spec,
            quantity=item.quantity,
            unit_price=item.unit_price,
            discount_amount=item.discount_amount,
            line_total=line_total,
        ))
    return lines
