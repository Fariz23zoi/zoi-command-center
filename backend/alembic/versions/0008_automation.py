"""Phase 8: otomatisasi terjadwal, riwayat jalan, dan notifikasi di dalam ZOI.

Revision ID: 0008_automation
Revises: 0007_online
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0008_automation"
down_revision = "0007_online"
branch_labels = None
depends_on = None

TS = sa.String(length=32)


def upgrade() -> None:
    op.create_table(
        "automations",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("schedule_json", sa.Text(), nullable=False),
        sa.Column("params_json", sa.Text(), nullable=False),
        sa.Column("next_due_at", TS, nullable=True),
        sa.Column("last_run_at", TS, nullable=True),
        sa.Column("created_at", TS, nullable=False),
    )
    op.create_table(
        "automation_runs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("automation_id", sa.String(length=36),
                  sa.ForeignKey("automations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("task_id", sa.String(length=36), nullable=True),
        sa.Column("trigger", sa.String(length=16), nullable=False),
        sa.Column("late", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("result_json", sa.Text(), nullable=False),
        sa.Column("started_at", TS, nullable=False),
        sa.Column("finished_at", TS, nullable=True),
    )
    op.create_table(
        "notifications",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("link", sa.String(length=200), nullable=True),
        sa.Column("created_at", TS, nullable=False),
        sa.Column("read_at", TS, nullable=True),
    )

    op.create_index("ix_automations_kind", "automations", ["kind"])
    op.create_index("ix_automations_next_due_at", "automations", ["next_due_at"])
    op.create_index("ix_automation_runs_automation_id", "automation_runs", ["automation_id"])
    op.create_index("ix_automation_runs_started_at", "automation_runs", ["started_at"])
    op.create_index("ix_notifications_created_at", "notifications", ["created_at"])


def downgrade() -> None:
    op.drop_table("notifications")
    op.drop_table("automation_runs")
    op.drop_table("automations")
