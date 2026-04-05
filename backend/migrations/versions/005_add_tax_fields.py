"""Add tax_included and tax_amount to sales.

Revision ID: 005
Revises: 004
Create Date: 2026-04-02
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("sales", sa.Column("tax_included", sa.Boolean, nullable=False, server_default="false"))
    op.add_column("sales", sa.Column("tax_amount", sa.Numeric(12, 2), nullable=False, server_default="0"))


def downgrade() -> None:
    op.drop_column("sales", "tax_amount")
    op.drop_column("sales", "tax_included")