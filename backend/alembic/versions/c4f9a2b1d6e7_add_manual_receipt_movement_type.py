"""add manual receipt movement type

Revision ID: c4f9a2b1d6e7
Revises: b3e8f1a2c4d5
Create Date: 2026-10-01 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op

revision: str = "c4f9a2b1d6e7"
down_revision: Union[str, Sequence[str], None] = "b3e8f1a2c4d5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("stock_movements", schema=None) as batch_op:
        batch_op.drop_constraint("movement_type_known", type_="check")
        batch_op.create_check_constraint(
            "movement_type_known",
            "movement_type IN ('receipt', 'purchase_receipt', 'sale', 'adjustment', 'transfer')",
        )
        batch_op.create_check_constraint(
            "manual_receipt_quantity_positive",
            "movement_type != 'receipt' OR quantity > 0",
        )


def downgrade() -> None:
    with op.batch_alter_table("stock_movements", schema=None) as batch_op:
        batch_op.drop_constraint("manual_receipt_quantity_positive", type_="check")
        batch_op.drop_constraint("movement_type_known", type_="check")
        batch_op.create_check_constraint(
            "movement_type_known",
            "movement_type IN ('purchase_receipt', 'sale', 'adjustment', 'transfer')",
        )
