"""Add attr_options, match_priority, match_type to category_attribute_templates.

Supports:
  - attr_options: JSON array of selectable values (dropdown in UI)
  - match_priority: lower = more important for alternative matching
  - match_type: must / prefer / optional

Revision ID: 010
Revises: 009
Create Date: 2026-04-03
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "010"
down_revision: Union[str, None] = "009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("category_attribute_templates",
        sa.Column("attr_options", sa.Text, nullable=True))       # JSON: ["30mm","25mm","22mm"]
    op.add_column("category_attribute_templates",
        sa.Column("match_priority", sa.Integer, nullable=True))  # 1=最重要, 99=最不重要
    op.add_column("category_attribute_templates",
        sa.Column("match_type", sa.String(20), nullable=True, server_default="prefer"))
        # must=必須一致 / prefer=優先匹配 / optional=有加分


def downgrade() -> None:
    op.drop_column("category_attribute_templates", "match_type")
    op.drop_column("category_attribute_templates", "match_priority")
    op.drop_column("category_attribute_templates", "attr_options")
