"""add exceptions table and exception scan autonomy fields

Revision ID: a1b2c3d4e5f7
Revises: f8b2c3d4e5f6
Create Date: 2026-10-06 18:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f7"
down_revision: Union[str, Sequence[str], None] = "f8b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("autonomy_rules") as batch:
        batch.add_column(
            sa.Column(
                "exception_scan_enabled",
                sa.Boolean(),
                nullable=False,
                server_default=sa.true(),
            )
        )
        batch.add_column(
            sa.Column(
                "exception_scan_hour_utc",
                sa.Integer(),
                nullable=False,
                server_default="2",
            )
        )
        batch.add_column(sa.Column("exception_scan_last_run_on", sa.Date(), nullable=True))

    op.create_table(
        "exceptions",
        sa.Column("id", sa.CHAR(length=36), nullable=False),
        sa.Column("business_id", sa.CHAR(length=36), nullable=False),
        sa.Column("exception_type", sa.String(length=40), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("entity_type", sa.String(length=80), nullable=False),
        sa.Column("entity_id", sa.CHAR(length=36), nullable=False),
        sa.Column("dedupe_key", sa.String(length=240), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("recommended_action", sa.String(length=40), nullable=True),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("suggestion_id", sa.CHAR(length=36), nullable=True),
        sa.Column("run_id", sa.CHAR(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "exception_type IN ('stockout_risk', 'overstock', 'demand_spike', "
            "'demand_drop', 'supplier_delay', 'data_anomaly')",
            name="exception_type_known",
        ),
        sa.CheckConstraint(
            "severity IN ('low', 'medium', 'high', 'critical')",
            name="exception_severity_known",
        ),
        sa.CheckConstraint(
            "status IN ('open', 'resolved', 'ignored')",
            name="exception_status_known",
        ),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["suggestion_id"], ["agent_suggestions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["run_id"], ["agent_runs.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_exceptions_business_id", "exceptions", ["business_id"])
    op.create_index(
        "uq_exceptions_open_dedupe",
        "exceptions",
        ["business_id", "dedupe_key"],
        unique=True,
        sqlite_where=sa.text("status = 'open'"),
        postgresql_where=sa.text("status = 'open'"),
    )


def downgrade() -> None:
    op.drop_index("uq_exceptions_open_dedupe", table_name="exceptions")
    op.drop_index("ix_exceptions_business_id", table_name="exceptions")
    op.drop_table("exceptions")
    with op.batch_alter_table("autonomy_rules") as batch:
        batch.drop_column("exception_scan_last_run_on")
        batch.drop_column("exception_scan_hour_utc")
        batch.drop_column("exception_scan_enabled")
