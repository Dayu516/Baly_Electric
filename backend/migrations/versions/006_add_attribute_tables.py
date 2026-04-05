"""Add category_attribute_templates and product_attributes tables.

Revision ID: 006
Revises: 005
Create Date: 2026-04-03
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "category_attribute_templates",
        sa.Column("template_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("category_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("attr_key", sa.String(50), nullable=False),
        sa.Column("attr_unit", sa.String(20), nullable=True),
        sa.Column("is_required", sa.Boolean, server_default="false"),
        sa.Column("sort_order", sa.Integer, server_default="0"),
    )

    op.create_table(
        "product_attributes",
        sa.Column("attr_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("product_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("attr_key", sa.String(50), nullable=False),
        sa.Column("attr_value", sa.String(200), nullable=False),
        sa.Column("attr_unit", sa.String(20), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("product_attributes")
    op.drop_table("category_attribute_templates")