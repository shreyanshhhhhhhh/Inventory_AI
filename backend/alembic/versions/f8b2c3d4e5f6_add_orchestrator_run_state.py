"""add orchestrator run state and chat messages

Revision ID: f8b2c3d4e5f6
Revises: e7a1b2c3d4e5
Create Date: 2026-10-06 17:30:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f8b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "e7a1b2c3d4e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("agent_runs") as batch:
        batch.add_column(sa.Column("input_text", sa.Text(), nullable=True))
        batch.add_column(sa.Column("plan_data", sa.JSON(), nullable=True))
        batch.add_column(sa.Column("state_data", sa.JSON(), nullable=True))
        batch.add_column(sa.Column("events_data", sa.JSON(), nullable=True))
        batch.add_column(
            sa.Column("cancel_requested", sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch.drop_constraint("agent_run_status_known", type_="check")
        batch.create_check_constraint(
            "agent_run_status_known",
            "status IN ('running', 'awaiting_approval', 'completed', 'failed', 'cancelled')",
        )
    op.create_index("ix_agent_runs_actor_status", "agent_runs", ["actor_user_id", "status"])

    op.create_table(
        "chat_messages",
        sa.Column("id", sa.CHAR(length=36), nullable=False),
        sa.Column("business_id", sa.CHAR(length=36), nullable=False),
        sa.Column("user_id", sa.CHAR(length=36), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("run_id", sa.CHAR(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("role IN ('user', 'assistant', 'system')", name="chat_message_role_known"),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["run_id"], ["agent_runs.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_chat_messages_user_created",
        "chat_messages",
        ["business_id", "user_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_chat_messages_user_created", table_name="chat_messages")
    op.drop_table("chat_messages")
    op.drop_index("ix_agent_runs_actor_status", table_name="agent_runs")
    with op.batch_alter_table("agent_runs") as batch:
        batch.drop_constraint("agent_run_status_known", type_="check")
        batch.create_check_constraint(
            "agent_run_status_known",
            "status IN ('running', 'completed', 'failed')",
        )
        batch.drop_column("cancel_requested")
        batch.drop_column("events_data")
        batch.drop_column("state_data")
        batch.drop_column("plan_data")
        batch.drop_column("input_text")
