"""add supplier messages, replies, and chase follow-up days

Revision ID: b2c3d4e5f6a8
Revises: a1b2c3d4e5f7
Create Date: 2026-10-07 03:45:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b2c3d4e5f6a8"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("autonomy_rules") as batch:
        batch.add_column(
            sa.Column(
                "chase_followup_days",
                sa.Integer(),
                nullable=False,
                server_default="3",
            )
        )

    with op.batch_alter_table("exceptions") as batch:
        batch.drop_constraint("exception_type_known", type_="check")
        batch.create_check_constraint(
            "exception_type_known",
            "exception_type IN ('stockout_risk', 'overstock', 'demand_spike', "
            "'demand_drop', 'supplier_delay', 'data_anomaly', 'chase_no_reply')",
        )

    op.create_table(
        "supplier_messages",
        sa.Column("id", sa.CHAR(length=36), nullable=False),
        sa.Column("business_id", sa.CHAR(length=36), nullable=False),
        sa.Column("supplier_id", sa.CHAR(length=36), nullable=False),
        sa.Column("po_id", sa.CHAR(length=36), nullable=True),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("subject", sa.String(length=240), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_by", sa.CHAR(length=36), nullable=False),
        sa.Column("approved_by", sa.CHAR(length=36), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("thread_id", sa.CHAR(length=36), nullable=False),
        sa.Column("facts", sa.JSON(), nullable=False),
        sa.Column("suggestion_id", sa.CHAR(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "kind IN ('order', 'chase', 'expedite', 'delay-notice')",
            name="supplier_message_kind_known",
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'approved', 'sent', 'failed', 'rejected')",
            name="supplier_message_status_known",
        ),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["supplier_id"], ["suppliers.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["po_id"], ["purchase_orders.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["approved_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["suggestion_id"], ["agent_suggestions.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_supplier_messages_business_id", "supplier_messages", ["business_id"])
    op.create_index("ix_supplier_messages_thread_id", "supplier_messages", ["thread_id"])

    op.create_table(
        "supplier_replies",
        sa.Column("id", sa.CHAR(length=36), nullable=False),
        sa.Column("business_id", sa.CHAR(length=36), nullable=False),
        sa.Column("message_id", sa.CHAR(length=36), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("parsed", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["message_id"], ["supplier_messages.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_supplier_replies_message_id", "supplier_replies", ["message_id"])


def downgrade() -> None:
    op.drop_index("ix_supplier_replies_message_id", table_name="supplier_replies")
    op.drop_table("supplier_replies")
    op.drop_index("ix_supplier_messages_thread_id", table_name="supplier_messages")
    op.drop_index("ix_supplier_messages_business_id", table_name="supplier_messages")
    op.drop_table("supplier_messages")
    with op.batch_alter_table("exceptions") as batch:
        batch.drop_constraint("exception_type_known", type_="check")
        batch.create_check_constraint(
            "exception_type_known",
            "exception_type IN ('stockout_risk', 'overstock', 'demand_spike', "
            "'demand_drop', 'supplier_delay', 'data_anomaly')",
        )
    with op.batch_alter_table("autonomy_rules") as batch:
        batch.drop_column("chase_followup_days")
