"""Sale repository 實作。"""

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from domain.sales.models import (
    CustomerPickupNotification,
    Sale,
    SaleLine,
    SaleLineFulfillment,
)
from domain.sales.repository import (
    CustomerPickupNotificationRepository,
    CustomerPriceHistoryRepository,
    SaleLineFulfillmentRepository,
    SaleLineRepository,
    SaleRepository,
)
from infrastructure.persistence.orm_models import (
    CustomerPickupNotificationORM,
    SaleLineFulfillmentORM,
    SaleLineORM,
    SaleORM,
)


class SqlSaleRepository(SaleRepository):
    def __init__(self, session: Session):
        self._session = session

    def get_by_id(self, sale_id: UUID) -> Optional[Sale]:
        orm = self._session.get(SaleORM, sale_id)
        return self._to_domain(orm) if orm else None

    def save(self, sale: Sale) -> Sale:
        existing = self._session.get(SaleORM, sale.sale_id)
        if existing:
            existing.status = sale.status
            existing.receipt_printed = sale.receipt_printed
            existing.note = sale.note
            existing.has_backorder = sale.has_backorder
            self._session.flush()
            return self._to_domain(existing)

        orm = SaleORM(
            sale_id=sale.sale_id,
            customer_id=sale.customer_id,
            cashier_id=sale.cashier_id,
            status=sale.status,
            payment_method=sale.payment_method,
            tax_included=sale.tax_included,
            subtotal=sale.subtotal,
            tax_amount=sale.tax_amount,
            discount_amount=sale.discount_amount,
            total=sale.total,
            receipt_printed=sale.receipt_printed,
            note=sale.note,
            client_tx_id=sale.client_tx_id,
        )
        self._session.add(orm)
        self._session.flush()
        return self._to_domain(orm)

    def save_lines(self, lines: list[SaleLine]) -> None:
        for line in lines:
            orm = SaleLineORM(
                sale_line_id=line.sale_line_id,
                sale_id=line.sale_id,
                sku_id=line.sku_id,
                product_name=line.product_name,
                spec=line.spec,
                quantity=line.quantity,
                unit_price=line.unit_price,
                discount_amount=line.discount_amount,
                line_total=line.line_total,
                # 履約欄位：正常 POS = 全部交付
                ordered_qty=line.ordered_qty or line.quantity,
                delivered_qty=line.delivered_qty if line.delivered_qty else line.quantity,
                fulfillment_status=line.fulfillment_status or "completed",
            )
            self._session.add(orm)
        self._session.flush()

    def get_by_client_tx_id(self, client_tx_id: str) -> Optional[Sale]:
        orm = self._session.query(SaleORM).filter(SaleORM.client_tx_id == client_tx_id).first()
        return self._to_domain(orm) if orm else None

    def delete_with_children(self, sale_id: UUID) -> None:
        """刪除 sale 及其所有子表資料。"""
        sid = str(sale_id)
        self._session.execute(text("DELETE FROM sale_line_fulfillments WHERE sale_id = :sid"), {"sid": sid})
        self._session.execute(text("DELETE FROM customer_pickup_notifications WHERE sale_id = :sid"), {"sid": sid})
        self._session.execute(text("DELETE FROM sale_lines WHERE sale_id = :sid"), {"sid": sid})
        self._session.execute(text("DELETE FROM sales WHERE sale_id = :sid"), {"sid": sid})
        self._session.flush()

    @staticmethod
    def _to_domain(orm: SaleORM) -> Sale:
        return Sale(
            sale_id=orm.sale_id,
            customer_id=orm.customer_id,
            cashier_id=orm.cashier_id,
            status=orm.status,
            payment_method=orm.payment_method,
            tax_included=orm.tax_included,
            subtotal=float(orm.subtotal),
            tax_amount=float(orm.tax_amount),
            discount_amount=float(orm.discount_amount),
            total=float(orm.total),
            receipt_printed=orm.receipt_printed,
            note=orm.note,
            client_tx_id=orm.client_tx_id,
            has_backorder=orm.has_backorder,
            created_at=orm.created_at,
        )


class SqlSaleLineRepository(SaleLineRepository):
    def __init__(self, session: Session):
        self._session = session

    def get_by_id(self, sale_line_id: UUID) -> Optional[SaleLine]:
        orm = self._session.get(SaleLineORM, sale_line_id)
        return self._to_domain(orm) if orm else None

    def save(self, line: SaleLine) -> SaleLine:
        existing = self._session.get(SaleLineORM, line.sale_line_id)
        if existing:
            existing.delivered_qty = line.delivered_qty
            existing.backorder_qty = line.backorder_qty
            existing.backorder_ordered_qty = line.backorder_ordered_qty
            existing.backorder_arrived_qty = line.backorder_arrived_qty
            existing.backorder_delivered_qty = line.backorder_delivered_qty
            existing.fulfillment_status = line.fulfillment_status
            existing.backorder_status = line.backorder_status
            existing.reserved_customer_note = line.reserved_customer_note
            existing.notified_at = line.notified_at
            existing.notify_count = line.notify_count
            existing.last_notify_channel = line.last_notify_channel
            existing.pickup_completed_at = line.pickup_completed_at
            existing.closed_at = line.closed_at
            self._session.flush()
            return self._to_domain(existing)

        orm = SaleLineORM(
            sale_line_id=line.sale_line_id,
            sale_id=line.sale_id,
            sku_id=line.sku_id,
            product_name=line.product_name,
            spec=line.spec,
            quantity=line.quantity,
            unit_price=line.unit_price,
            discount_amount=line.discount_amount,
            line_total=line.line_total,
            ordered_qty=line.ordered_qty or line.quantity,
            delivered_qty=line.delivered_qty,
            backorder_qty=line.backorder_qty,
            backorder_ordered_qty=line.backorder_ordered_qty,
            backorder_arrived_qty=line.backorder_arrived_qty,
            backorder_delivered_qty=line.backorder_delivered_qty,
            fulfillment_status=line.fulfillment_status,
            backorder_status=line.backorder_status,
            reserved_customer_note=line.reserved_customer_note,
            notified_at=line.notified_at,
            notify_count=line.notify_count,
            last_notify_channel=line.last_notify_channel,
            pickup_completed_at=line.pickup_completed_at,
            closed_at=line.closed_at,
        )
        self._session.add(orm)
        self._session.flush()
        return self._to_domain(orm)

    def list_by_sale_id(self, sale_id: UUID) -> list[SaleLine]:
        orms = self._session.query(SaleLineORM).filter(SaleLineORM.sale_id == sale_id).all()
        return [self._to_domain(o) for o in orms]

    @staticmethod
    def _to_domain(orm: SaleLineORM) -> SaleLine:
        return SaleLine(
            sale_line_id=orm.sale_line_id,
            sale_id=orm.sale_id,
            sku_id=orm.sku_id,
            product_name=orm.product_name,
            spec=orm.spec,
            quantity=orm.quantity,
            unit_price=float(orm.unit_price),
            discount_amount=float(orm.discount_amount),
            line_total=float(orm.line_total),
            ordered_qty=orm.ordered_qty,
            delivered_qty=orm.delivered_qty,
            backorder_qty=orm.backorder_qty,
            backorder_ordered_qty=orm.backorder_ordered_qty,
            backorder_arrived_qty=orm.backorder_arrived_qty,
            backorder_delivered_qty=orm.backorder_delivered_qty,
            fulfillment_status=orm.fulfillment_status,
            backorder_status=orm.backorder_status,
            reserved_customer_note=orm.reserved_customer_note,
            notified_at=orm.notified_at,
            notify_count=orm.notify_count,
            last_notify_channel=orm.last_notify_channel,
            pickup_completed_at=orm.pickup_completed_at,
            closed_at=orm.closed_at,
        )


class SqlSaleLineFulfillmentRepository(SaleLineFulfillmentRepository):
    def __init__(self, session: Session):
        self._session = session

    def save(self, fulfillment: SaleLineFulfillment) -> SaleLineFulfillment:
        existing = self._session.get(SaleLineFulfillmentORM, fulfillment.fulfillment_id)
        if existing:
            existing.arrived_qty = fulfillment.arrived_qty
            existing.delivered_qty = fulfillment.delivered_qty
            existing.status = fulfillment.status
            existing.note = fulfillment.note
            self._session.flush()
            return self._to_domain(existing)

        orm = SaleLineFulfillmentORM(
            fulfillment_id=fulfillment.fulfillment_id,
            sale_id=fulfillment.sale_id,
            sale_line_id=fulfillment.sale_line_id,
            source_type=fulfillment.source_type,
            source_doc_id=fulfillment.source_doc_id,
            source_line_id=fulfillment.source_line_id,
            allocated_qty=fulfillment.allocated_qty,
            arrived_qty=fulfillment.arrived_qty,
            delivered_qty=fulfillment.delivered_qty,
            status=fulfillment.status,
            note=fulfillment.note,
        )
        self._session.add(orm)
        self._session.flush()
        return self._to_domain(orm)

    def list_by_sale_line_id(self, sale_line_id: UUID) -> list[SaleLineFulfillment]:
        orms = (
            self._session.query(SaleLineFulfillmentORM)
            .filter(SaleLineFulfillmentORM.sale_line_id == sale_line_id)
            .all()
        )
        return [self._to_domain(o) for o in orms]

    def list_by_sale_line_and_source(
        self, sale_line_id: UUID, source_doc_id: UUID,
    ) -> list[SaleLineFulfillment]:
        orms = (
            self._session.query(SaleLineFulfillmentORM)
            .filter(
                SaleLineFulfillmentORM.sale_line_id == sale_line_id,
                SaleLineFulfillmentORM.source_doc_id == source_doc_id,
            )
            .all()
        )
        return [self._to_domain(o) for o in orms]

    @staticmethod
    def _to_domain(orm: SaleLineFulfillmentORM) -> SaleLineFulfillment:
        return SaleLineFulfillment(
            fulfillment_id=orm.fulfillment_id,
            sale_id=orm.sale_id,
            sale_line_id=orm.sale_line_id,
            source_type=orm.source_type,
            source_doc_id=orm.source_doc_id,
            source_line_id=orm.source_line_id,
            allocated_qty=orm.allocated_qty,
            arrived_qty=orm.arrived_qty,
            delivered_qty=orm.delivered_qty,
            status=orm.status,
            note=orm.note,
        )


class SqlCustomerPickupNotificationRepository(CustomerPickupNotificationRepository):
    def __init__(self, session: Session):
        self._session = session

    def save(self, notification: CustomerPickupNotification) -> CustomerPickupNotification:
        orm = CustomerPickupNotificationORM(
            notification_id=notification.notification_id,
            customer_id=notification.customer_id,
            sale_id=notification.sale_id,
            sale_line_id=notification.sale_line_id,
            channel=notification.channel,
            message_snapshot=notification.message_snapshot,
            status=notification.status,
            sent_by=notification.sent_by,
            sent_at=notification.sent_at,
            remark=notification.remark,
        )
        self._session.add(orm)
        self._session.flush()
        return notification


class SqlCustomerPriceHistoryRepository(CustomerPriceHistoryRepository):
    def __init__(self, session: Session):
        self._session = session

    def upsert(
        self, customer_id: UUID, sku_id: UUID,
        price: float, cost: float | None,
        sold_at, sale_id: UUID,
    ) -> None:
        self._session.execute(text("""
            INSERT INTO customer_price_history (id, customer_id, sku_id, last_price, last_cost, last_sold_at, sale_id, created_at, updated_at)
            VALUES (gen_random_uuid(), :customer_id, :sku_id, :price, :cost, :sold_at, :sale_id, NOW(), NOW())
            ON CONFLICT (customer_id, sku_id)
            DO UPDATE SET last_price = :price, last_cost = :cost, last_sold_at = :sold_at, sale_id = :sale_id, updated_at = NOW()
        """), {
            "customer_id": str(customer_id),
            "sku_id": str(sku_id),
            "price": price,
            "cost": cost,
            "sold_at": sold_at,
            "sale_id": str(sale_id),
        })
