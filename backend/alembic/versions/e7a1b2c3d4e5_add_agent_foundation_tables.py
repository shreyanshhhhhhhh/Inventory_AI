"""add agent foundation tables

Revision ID: e7a1b2c3d4e5
Revises: d5e6f7a8b9c0
Create Date: 2026-10-06 12:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e7a1b2c3d4e5"
down_revision: Union[str, Sequence[str], None] = "d5e6f7a8b9c0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agent_runs",
        sa.Column("id", sa.CHAR(length=36), nullable=False),
        sa.Column("business_id", sa.CHAR(length=36), nullable=False),
        sa.Column("agent_name", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("prompt_name", sa.String(length=80), nullable=True),
        sa.Column("prompt_version", sa.String(length=32), nullable=True),
        sa.Column("actor_user_id", sa.CHAR(length=36), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "status IN ('running', 'completed', 'failed')",
            name="agent_run_status_known",
        ),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_runs_business_id", "agent_runs", ["business_id"])

    op.create_table(
        "agent_steps",
        sa.Column("id", sa.CHAR(length=36), nullable=False),
        sa.Column("run_id", sa.CHAR(length=36), nullable=False),
        sa.Column("business_id", sa.CHAR(length=36), nullable=False),
        sa.Column("step_kind", sa.String(length=20), nullable=False),
        sa.Column("tool_name", sa.String(length=80), nullable=True),
        sa.Column("prompt_name", sa.String(length=80), nullable=True),
        sa.Column("prompt_version", sa.String(length=32), nullable=True),
        sa.Column("input_data", sa.JSON(), nullable=True),
        sa.Column("output_data", sa.JSON(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("tokens_in", sa.Integer(), nullable=True),
        sa.Column("tokens_out", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("step_kind IN ('llm', 'tool')", name="agent_step_kind_known"),
        sa.ForeignKeyConstraint(["run_id"], ["agent_runs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_steps_run_id", "agent_steps", ["run_id"])
    op.create_index("ix_agent_steps_business_id", "agent_steps", ["business_id"])

    op.create_table(
        "agent_suggestions",
        sa.Column("id", sa.CHAR(length=36), nullable=False),
        sa.Column("business_id", sa.CHAR(length=36), nullable=False),
        sa.Column("run_id", sa.CHAR(length=36), nullable=False),
        sa.Column("suggestion_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "suggestion_type IN ('generic', 'draft_po', 'draft_email')",
            name="agent_suggestion_type_known",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'dismissed')",
            name="agent_suggestion_status_known",
        ),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["run_id"], ["agent_runs.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_suggestions_business_id", "agent_suggestions", ["business_id"])
    op.create_index("ix_agent_suggestions_run_id", "agent_suggestions", ["run_id"])

    op.create_table(
        "llm_usage_counters",
        sa.Column("id", sa.CHAR(length=36), nullable=False),
        sa.Column("business_id", sa.CHAR(length=36), nullable=False),
        sa.Column("usage_date", sa.Date(), nullable=False),
        sa.Column("request_count", sa.Integer(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("business_id", "usage_date", name="uq_llm_usage_business_id_usage_date"),
    )


def downgrade() -> None:
    op.drop_table("llm_usage_counters")
    op.drop_index("ix_agent_suggestions_run_id", table_name="agent_suggestions")
    op.drop_index("ix_agent_suggestions_business_id", table_name="agent_suggestions")
    op.drop_table("agent_suggestions")
    op.drop_index("ix_agent_steps_business_id", table_name="agent_steps")
    op.drop_index("ix_agent_steps_run_id", table_name="agent_steps")
    op.drop_table("agent_steps")
    op.drop_index("ix_agent_runs_business_id", table_name="agent_runs")
    op.drop_table("agent_runs")
