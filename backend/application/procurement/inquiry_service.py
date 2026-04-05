"""InquiryService — 詢價單完整流程 use case。

流程：建立詢價 → 新增品項 → 記錄報價 → 選取比價 → 轉採購單。

依賴：
  - InquiryRepository / LineRepository / QuoteRepository（詢價寫入）
  - PurchaseOrderRepository / LineRepository（轉 PO）
  - SupplierPriceQuoteRepository（全域報價歷史）
  - ProcurementQueryService（查詢）
"""

from datetime import datetime, timezone
from uuid import UUID

from core.errors import ERR_BIZ_001, ERR_BIZ_002
from core.logging import get_logger
from core.results import Result
from domain.procurement.models import (
    PurchaseInquiry,
    PurchaseInquiryLine,
    PurchaseInquiryQuote,
    PurchaseOrder,
    PurchaseOrderLine,
    SupplierPriceQuote,
)
from domain.procurement.repository import (
    InquiryLineRepository,
    InquiryQuoteRepository,
    InquiryRepository,
    PurchaseOrderLineRepository,
    PurchaseOrderRepository,
    SupplierPriceQuoteRepository,
)
from infrastructure.persistence.query_services.procurement_query_service import ProcurementQueryService

logger = get_logger("inquiry")


class InquiryService:
    def __init__(
        self,
        inquiry_repo: InquiryRepository,
        inquiry_line_repo: InquiryLineRepository,
        inquiry_quote_repo: InquiryQuoteRepository,
        supplier_quote_repo: SupplierPriceQuoteRepository,
        po_repo: PurchaseOrderRepository,
        po_line_repo: PurchaseOrderLineRepository,
        query_service: ProcurementQueryService,
    ):
        self._inq_repo = inquiry_repo
        self._line_repo = inquiry_line_repo
        self._quote_repo = inquiry_quote_repo
        self._supplier_quote_repo = supplier_quote_repo
        self._po_repo = po_repo
        self._po_line_repo = po_line_repo
        self._qs = query_service

    # ── 查詢 ──────────────────────────────────────────

    def list_inquiries(self, *, status: str | None, keyword: str | None = None,
                         date_from: str | None = None, date_to: str | None = None,
                         page: int, per_page: int) -> Result:
        offset = (page - 1) * per_page
        rows = self._qs.list_inquiries(status=status, keyword=keyword,
                                        date_from=date_from, date_to=date_to,
                                        offset=offset, limit=per_page)
        data = [
            {
                "inquiry_id": str(r["inquiry_id"]),
                "title": r["title"],
                "status": r["status"],
                "note": r["note"],
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
                "line_count": r["line_count"],
                "quote_count": r["quote_count"],
            }
            for r in rows
        ]
        return Result.ok(data=data)

    def get_inquiry(self, inquiry_id: UUID) -> Result:
        inq = self._inq_repo.get_by_id(inquiry_id)
        if not inq:
            return Result.fail(ERR_BIZ_002, "詢價單不存在")

        lines = self._qs.get_inquiry_lines(str(inquiry_id))
        quotes = self._qs.get_inquiry_quotes(str(inquiry_id))

        quotes_by_line: dict[str, list] = {}
        for q in quotes:
            lid = str(q["line_id"])
            quotes_by_line.setdefault(lid, []).append({
                "quote_id": str(q["quote_id"]),
                "supplier_id": str(q["supplier_id"]),
                "supplier_name": q["supplier_name"],
                "unit_price": float(q["unit_price"]),
                "note": q["note"],
                "is_selected": q["is_selected"],
            })

        data = {
            "inquiry_id": str(inq.inquiry_id),
            "title": inq.title,
            "status": inq.status,
            "note": inq.note,
            "created_at": inq.created_at.isoformat() if inq.created_at else None,
            "lines": [
                {
                    "line_id": str(l["line_id"]),
                    "sku_id": str(l["sku_id"]),
                    "product_name": l["product_name"],
                    "brand": l["brand"],
                    "spec": l["spec"],
                    "unit": l["unit"],
                    "quantity": l["quantity"],
                    "note": l["note"],
                    "quotes": quotes_by_line.get(str(l["line_id"]), []),
                }
                for l in lines
            ],
        }
        return Result.ok(data=data)

    # ── 建單 ──────────────────────────────────────────

    def create_inquiry(
        self, title: str, note: str | None, lines: list[dict], user_id: UUID,
    ) -> Result:
        now = datetime.now(timezone.utc)
        inq = self._inq_repo.save(PurchaseInquiry(
            title=title, status="draft", note=note,
            created_by=user_id, created_at=now, updated_at=now,
        ))

        for line in lines:
            self._line_repo.save(PurchaseInquiryLine(
                inquiry_id=inq.inquiry_id,
                sku_id=UUID(line["sku_id"]),
                quantity=line["quantity"],
                note=line.get("note"),
            ))

        logger.info("inquiry_created", inquiry_id=str(inq.inquiry_id))
        return Result.ok(data={"inquiry_id": str(inq.inquiry_id)}, message="詢價單已建立")

    # ── 新增品項 ──────────────────────────────────────

    def add_line(self, inquiry_id: UUID, sku_id: str, quantity: int, note: str | None) -> Result:
        inq = self._inq_repo.get_by_id(inquiry_id)
        if not inq:
            return Result.fail(ERR_BIZ_002, "詢價單不存在")
        if inq.status not in ("draft", "quoting"):
            return Result.fail(ERR_BIZ_001, "此狀態無法新增品項")

        line = self._line_repo.save(PurchaseInquiryLine(
            inquiry_id=inquiry_id, sku_id=UUID(sku_id), quantity=quantity, note=note,
        ))

        if inq.status == "draft":
            inq.status = "quoting"
            self._inq_repo.save(inq)

        return Result.ok(data={"line_id": str(line.line_id)}, message="品項已加入")

    # ── 記錄報價 ──────────────────────────────────────

    def add_quote(
        self, inquiry_id: UUID, line_id: str, supplier_id: str,
        unit_price: float, note: str | None, user_id: UUID,
    ) -> Result:
        inq = self._inq_repo.get_by_id(inquiry_id)
        if not inq:
            return Result.fail(ERR_BIZ_002, "詢價單不存在")

        now = datetime.now(timezone.utc)
        self._quote_repo.save(PurchaseInquiryQuote(
            inquiry_id=inquiry_id,
            line_id=UUID(line_id),
            supplier_id=UUID(supplier_id),
            unit_price=unit_price,
            note=note,
            created_at=now,
        ))

        # 同時記錄到全域報價歷史
        line = self._line_repo.get_by_id(UUID(line_id))
        if line:
            self._supplier_quote_repo.save(SupplierPriceQuote(
                supplier_id=UUID(supplier_id),
                sku_id=line.sku_id,
                unit_price=unit_price,
                quoted_at=now,
                note=f"詢價單: {inq.title}",
                created_by=user_id,
                created_at=now,
            ))

        if inq.status == "draft":
            inq.status = "quoting"
            self._inq_repo.save(inq)

        logger.info("quote_added", inquiry_id=str(inquiry_id))
        return Result.ok(message="報價已記錄")

    # ── 選取報價 ──────────────────────────────────────

    def select_quotes(self, inquiry_id: UUID, quote_ids: list[str]) -> Result:
        inq = self._inq_repo.get_by_id(inquiry_id)
        if not inq:
            return Result.fail(ERR_BIZ_002, "詢價單不存在")

        self._qs.deselect_all_inquiry_quotes(str(inquiry_id))
        for qid in quote_ids:
            self._qs.select_inquiry_quote(qid, str(inquiry_id))

        inq.status = "decided"
        self._inq_repo.save(inq)
        return Result.ok(message=f"已選取 {len(quote_ids)} 筆報價")

    # ── 轉採購單 ──────────────────────────────────────

    def convert_to_po(self, inquiry_id: UUID) -> Result:
        inq = self._inq_repo.get_by_id(inquiry_id)
        if not inq:
            return Result.fail(ERR_BIZ_002, "詢價單不存在")
        if inq.status not in ("decided", "quoting"):
            return Result.fail(ERR_BIZ_001, f"狀態 {inq.status} 無法轉單")

        selected = self._qs.get_selected_inquiry_quotes(str(inquiry_id))
        if not selected:
            return Result.fail(ERR_BIZ_001, "沒有選取任何報價")

        # 按供應商分組（純邏輯）
        from application.procurement.rules import group_by_supplier
        by_supplier = group_by_supplier(selected)

        po_ids = []
        for supplier_id, supplier_lines in by_supplier.items():
            saved_po = self._po_repo.save(PurchaseOrder(
                supplier_id=UUID(supplier_id),
                status="draft",
                note=f"來自詢價單: {inq.title}",
            ))

            for line in supplier_lines:
                self._po_line_repo.save(PurchaseOrderLine(
                    po_id=saved_po.po_id,
                    sku_id=line["sku_id"],
                    ordered_quantity=line["quantity"],
                    unit_cost=float(line["unit_price"]),
                ))
            po_ids.append(str(saved_po.po_id))

        inq.status = "converted"
        self._inq_repo.save(inq)

        logger.info("inquiry_converted", inquiry_id=str(inquiry_id), po_count=len(po_ids))
        return Result.ok(data={"po_ids": po_ids}, message=f"已轉成 {len(po_ids)} 張採購單")

    # ── 取消 ──────────────────────────────────────────

    def cancel_inquiry(self, inquiry_id: UUID) -> Result:
        inq = self._inq_repo.get_by_id(inquiry_id)
        if not inq:
            return Result.fail(ERR_BIZ_002, "詢價單不存在")
        inq.status = "cancelled"
        self._inq_repo.save(inq)
        logger.info("inquiry_cancelled", inquiry_id=str(inquiry_id))
        return Result.ok(message="詢價單已取消")

    def delete_inquiry(self, inquiry_id: UUID) -> Result:
        inq = self._inq_repo.get_by_id(inquiry_id)
        if not inq:
            return Result.fail(ERR_BIZ_002, "詢價單不存在")
        if inq.status != "cancelled":
            return Result.fail(ERR_BIZ_001, "只有已取消的詢價單可以刪除")
        self._inq_repo.delete(inquiry_id)
        logger.info("inquiry_deleted", inquiry_id=str(inquiry_id))
        return Result.ok(message="詢價單已刪除")


