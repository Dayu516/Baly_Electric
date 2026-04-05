"""017: Use Case 層支援欄位

- purchase_receipts.idempotency_key（PO Receive 冪等 + 同日覆蓋）
- products.source_batch_id（Import 批次追蹤）
- skus.source_batch_id（Import 批次追蹤）
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


def upgrade():
    # ── PO Receive idempotency ─────────────────────────────
    op.add_column("purchase_receipts", sa.Column("idempotency_key", sa.String(100), nullable=True))
    op.create_index("ix_receipts_po_idempotency", "purchase_receipts", ["po_id", "idempotency_key"])

    # ── Product Import batch tracking ──────────────────────
    op.add_column("products", sa.Column("source_batch_id", UUID(as_uuid=True), nullable=True))
    op.add_column("skus", sa.Column("source_batch_id", UUID(as_uuid=True), nullable=True))
    op.create_index("ix_products_source_batch", "products", ["source_batch_id"])
    op.create_index("ix_skus_source_batch", "skus", ["source_batch_id"])


def downgrade():
    op.drop_index("ix_skus_source_batch")
    op.drop_index("ix_products_source_batch")
    op.drop_column("skus", "source_batch_id")
    op.drop_column("products", "source_batch_id")
    op.drop_index("ix_receipts_po_idempotency")
    op.drop_column("purchase_receipts", "idempotency_key")
