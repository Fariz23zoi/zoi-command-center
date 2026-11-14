"""Phase 3 — AI lokal: proses berpikir model di pesan, tabel hasil uji model.

Revision ID: 0002_local_ai
Revises: 0001_foundation
Create Date: 2026-11-14
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0002_local_ai"
down_revision = "0001_foundation"
branch_labels = None
depends_on = None

TS = sa.String(32)


def upgrade() -> None:
    op.add_column("messages", sa.Column("thinking", sa.Text(), nullable=True))
    op.create_table(
        "model_evaluations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("model", sa.String(120), nullable=False),
        sa.Column("machine", sa.String(120), nullable=False),
        sa.Column("ollama_version", sa.String(32), nullable=True),
        sa.Column("prompts_version", sa.Integer(), nullable=False),
        sa.Column("started_at", TS, nullable=False),
        sa.Column("finished_at", TS, nullable=False),
        sa.Column("summary_json", sa.Text(), nullable=False),
        sa.Column("results_json", sa.Text(), nullable=False),
        sa.Column("ratings_json", sa.Text(), nullable=False),
    )
    op.create_index("ix_model_evaluations_model", "model_evaluations", ["model"])
    op.create_index("ix_model_evaluations_finished_at", "model_evaluations", ["finished_at"])


def downgrade() -> None:
    op.drop_index("ix_model_evaluations_finished_at", table_name="model_evaluations")
    op.drop_index("ix_model_evaluations_model", table_name="model_evaluations")
    op.drop_table("model_evaluations")
    with op.batch_alter_table("messages") as batch:
        batch.drop_column("thinking")
