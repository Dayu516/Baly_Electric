"""Add company_info and system_parameters tables.

Revision ID: 007
Revises: 006
Create Date: 2026-04-03
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 公司資料（單列表，只有一筆）
    op.create_table(
        "company_info",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=False, server_default="1"),
        sa.Column("name", sa.String(200), nullable=False, server_default=""),
        sa.Column("short_name", sa.String(100), nullable=True),
        sa.Column("tax_id", sa.String(20), nullable=True),          # 統一編號
        sa.Column("phone", sa.String(30), nullable=True),
        sa.Column("fax", sa.String(30), nullable=True),
        sa.Column("address", sa.Text, nullable=True),
        sa.Column("owner_name", sa.String(100), nullable=True),     # 負責人
        sa.Column("note", sa.Text, nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # 系統參數（key-value 表）
    op.create_table(
        "system_parameters",
        sa.Column("key", sa.String(50), primary_key=True),
        sa.Column("value", sa.String(500), nullable=False, server_default=""),
        sa.Column("description", sa.String(200), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # 預設系統參數
    op.execute("""
        INSERT INTO system_parameters (key, value, description) VALUES
        ('default_tax_rate', '0.05', '預設稅率（5%）'),
        ('decimal_places', '0', '金額小數位數'),
        ('receipt_copies', '2', '出貨單列印份數'),
        ('receipt_title', '', '出貨單抬頭（空白時用公司名稱）')
    """)

    # 預設公司資料（空白，待填入）
    op.execute("INSERT INTO company_info (id) VALUES (1)")


def downgrade() -> None:
    op.drop_table("system_parameters")
    op.drop_table("company_info")
