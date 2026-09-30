"""add autonomy_rules

Revision ID: d5e6f7a8b9c0
Revises: c4f9a2b1d6e7
Create Date: 2026-10-01 12:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d5e6f7a8b9c0"
down_revision: Union[str, Sequence[str], None] = "c4f9a2b1d6e7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "autonomy_rules",
        sa.Column("id", sa.CHAR(length=36), nullable=False),
        sa.Column("business_id", sa.CHAR(length=36), nullable=False),
        sa.Column("auto_approve_below_amount", sa.Numeric(precision=18, scale=4), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("business_id", name="uq_autonomy_rules_business_id"),
    )


def downgrade() -> None:
    op.drop_table("autonomy_rules")
