"""Phase 6A — YouTube: statistik channel sendiri, cache respons, hitungan kuota.

Revision ID: 0004_youtube
Revises: 0003_agent_memory
Create Date: 2026-11-15
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0004_youtube"
down_revision = "0003_agent_memory"
branch_labels = None
depends_on = None

TS = sa.String(32)


def upgrade() -> None:
    op.create_table(
        "youtube_channel_snapshots",
        sa.Column("day", sa.String(10), primary_key=True),
        sa.Column("channel_id", sa.String(64), nullable=False),
        sa.Column("fetched_at", TS, nullable=False),
        sa.Column("view_count", sa.Integer(), nullable=True),
        sa.Column("subscriber_count", sa.Integer(), nullable=True),
        sa.Column("hidden_subscribers", sa.Boolean(), nullable=False),
        sa.Column("video_count", sa.Integer(), nullable=True),
    )
    op.create_table(
        "youtube_cache",
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("fetched_at", TS, nullable=False),
    )
    op.create_table(
        "youtube_quota",
        sa.Column("day", sa.String(10), primary_key=True),
        sa.Column("units", sa.Integer(), nullable=False),
        sa.Column("search_calls", sa.Integer(), nullable=False),
        sa.Column("analytics_calls", sa.Integer(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("youtube_quota")
    op.drop_table("youtube_cache")
    op.drop_table("youtube_channel_snapshots")
