"""016: 客戶 + 報價單欄位擴充 — 一次到位

客戶：基本識別 + 聯絡資訊 + 交易條件 + 業務管理
報價單：商業條件 + 轉單準備
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


def upgrade():
    # ═══════════════════════════════════════════════════════
    # 1. customers 擴充
    # ═══════════════════════════════════════════════════════

    # A. 基本識別
    op.add_column("customers", sa.Column("short_name", sa.String(100), nullable=True))       # 簡稱/慣用稱呼
    op.add_column("customers", sa.Column("tax_id", sa.String(20), nullable=True))             # 統一編號
    op.add_column("customers", sa.Column("customer_type", sa.String(30), nullable=False, server_default="general"))
    # general / company / dealer / vip / project
    op.add_column("customers", sa.Column("customer_code", sa.String(30), nullable=True))      # 系統自動或手動編號

    # B. 聯絡資訊
    op.add_column("customers", sa.Column("contact_person", sa.String(100), nullable=True))    # 聯絡人
    op.add_column("customers", sa.Column("mobile", sa.String(30), nullable=True))             # 手機
    op.add_column("customers", sa.Column("email", sa.String(200), nullable=True))
    op.add_column("customers", sa.Column("line_id", sa.String(100), nullable=True))           # LINE
    op.add_column("customers", sa.Column("shipping_address", sa.Text, nullable=True))         # 送貨地址

    # C. 交易條件
    op.add_column("customers", sa.Column("price_level", sa.String(30), nullable=False, server_default="retail"))
    # retail / wholesale / dealer / project / vip
    op.add_column("customers", sa.Column("payment_days", sa.Integer, nullable=True))          # 帳期天數（30/45/60）
    op.add_column("customers", sa.Column("allow_debt", sa.Boolean, nullable=False, server_default="true"))
    op.add_column("customers", sa.Column("invoice_type", sa.String(20), nullable=True))       # 二聯/三聯/免開
    op.add_column("customers", sa.Column("invoice_title", sa.String(200), nullable=True))     # 發票抬頭
    op.add_column("customers", sa.Column("invoice_address", sa.Text, nullable=True))          # 發票地址
    op.add_column("customers", sa.Column("invoice_delivery", sa.String(20), nullable=True))   # 寄送方式（email/mail/pickup）

    # D. 業務管理
    op.add_column("customers", sa.Column("sales_rep", sa.String(100), nullable=True))         # 業務負責人
    op.add_column("customers", sa.Column("source", sa.String(50), nullable=True))             # 來源（舊客戶/介紹/網路/展會/路過）
    op.add_column("customers", sa.Column("customer_level", sa.String(10), nullable=True))     # A/B/C
    op.add_column("customers", sa.Column("cooperation_status", sa.String(20), nullable=False, server_default="active"))
    # potential / active / suspended
    op.add_column("customers", sa.Column("tags", sa.Text, nullable=True))                     # JSON array: ["食品廠","比價型"]

    op.create_index("ix_customers_tax_id", "customers", ["tax_id"])
    op.create_index("ix_customers_customer_type", "customers", ["customer_type"])
    op.create_index("ix_customers_price_level", "customers", ["price_level"])

    # ═══════════════════════════════════════════════════════
    # 2. sales_quotations 擴充
    # ═══════════════════════════════════════════════════════

    # A. 報價主資訊
    op.add_column("sales_quotations", sa.Column("quotation_number", sa.String(30), nullable=True))  # 報價單號
    op.add_column("sales_quotations", sa.Column("quotation_date", sa.DateTime(timezone=True), nullable=True))
    op.add_column("sales_quotations", sa.Column("contact_person", sa.String(100), nullable=True))
    op.add_column("sales_quotations", sa.Column("quotation_type", sa.String(30), nullable=False, server_default="general"))
    # general / project / inquiry_reply / special_order
    op.add_column("sales_quotations", sa.Column("project_name", sa.String(200), nullable=True))

    # B. 商業條件
    op.add_column("sales_quotations", sa.Column("tax_mode", sa.String(20), nullable=False, server_default="excluded"))
    # included / excluded / exempt
    op.add_column("sales_quotations", sa.Column("payment_terms_text", sa.String(200), nullable=True))  # 付款條件文字
    op.add_column("sales_quotations", sa.Column("delivery_days", sa.Integer, nullable=True))           # 交期（天）
    op.add_column("sales_quotations", sa.Column("delivery_terms", sa.String(200), nullable=True))      # 交期文字
    op.add_column("sales_quotations", sa.Column("shipping_terms", sa.String(200), nullable=True))      # 運費條件
    op.add_column("sales_quotations", sa.Column("warranty_terms", sa.String(200), nullable=True))      # 保固說明
    op.add_column("sales_quotations", sa.Column("special_terms", sa.Text, nullable=True))              # 特殊條款
    op.add_column("sales_quotations", sa.Column("valid_days", sa.Integer, nullable=True))              # 報價有效天數
    op.add_column("sales_quotations", sa.Column("currency", sa.String(10), nullable=False, server_default="TWD"))
    op.add_column("sales_quotations", sa.Column("includes_installation", sa.Boolean, nullable=False, server_default="false"))

    # C. 轉單準備
    op.add_column("sales_quotations", sa.Column("expected_close_date", sa.DateTime(timezone=True), nullable=True))
    op.add_column("sales_quotations", sa.Column("win_probability", sa.Integer, nullable=True))  # 0~100
    op.add_column("sales_quotations", sa.Column("source_inquiry_id", UUID(as_uuid=True), nullable=True))
    op.add_column("sales_quotations", sa.Column("internal_note", sa.Text, nullable=True))       # 內部備註（不給客戶看）
    op.add_column("sales_quotations", sa.Column("converted_sale_id", UUID(as_uuid=True), nullable=True))

    op.create_index("ix_quotations_type", "sales_quotations", ["quotation_type"])
    op.create_index("ix_quotations_number", "sales_quotations", ["quotation_number"])


def downgrade():
    # quotations
    for col in ["quotation_number", "quotation_date", "contact_person", "quotation_type",
                 "project_name", "tax_mode", "payment_terms_text", "delivery_days",
                 "delivery_terms", "shipping_terms", "warranty_terms", "special_terms",
                 "valid_days", "currency", "includes_installation",
                 "expected_close_date", "win_probability", "source_inquiry_id",
                 "internal_note", "converted_sale_id"]:
        op.drop_column("sales_quotations", col)

    # customers
    for col in ["short_name", "tax_id", "customer_type", "customer_code",
                 "contact_person", "mobile", "email", "line_id", "shipping_address",
                 "price_level", "payment_days", "allow_debt",
                 "invoice_type", "invoice_title", "invoice_address", "invoice_delivery",
                 "sales_rep", "source", "customer_level", "cooperation_status", "tags"]:
        op.drop_column("customers", col)
