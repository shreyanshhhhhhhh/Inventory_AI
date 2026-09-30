"""add supplier lead_time_days

Revision ID: b3e8f1a2c4d5
Revises: a2dc70ad62cc
Create Date: 2026-09-30 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b3e8f1a2c4d5"
down_revision: Union[str, Sequence[str], None] = "a2dc70ad62cc"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("suppliers", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("lead_time_days", sa.Integer(), nullable=False, server_default="0")
        )
        batch_op.create_check_constraint(
            "ck_suppliers_lead_time_nonnegative",
            "lead_time_days >= 0",
        )


def downgrade() -> None:
    with op.batch_alter_table("suppliers", schema=None) as batch_op:
        batch_op.drop_constraint("ck_suppliers_lead_time_nonnegative", type_="check")
        batch_op.drop_column("lead_time_days")
