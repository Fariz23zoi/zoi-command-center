"""Phase 6B — data publik YouTube (≤30 hari), daftar pantauan, draf ide & naskah.

Revision ID: 0005_youtube_public
Revises: 0004_youtube
Create Date: 2026-11-15
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0005_youtube_public"
down_revision = "0004_youtube"
branch_labels = None
depends_on = None

TS = sa.String(32)


def upgrade() -> None:
    op.create_table(
        "youtube_public_cache",
        sa.Column("key", sa.String(120), primary_key=True),
        sa.Column("kind", sa.String(24), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("fetched_at", TS, nullable=False),
    )
    op.create_index("ix_youtube_public_cache_kind", "youtube_public_cache", ["kind"])
    op.create_index("ix_youtube_public_cache_fetched_at", "youtube_public_cache", ["fetched_at"])
    op.create_table(
        "youtube_watchlist",
        sa.Column("channel_id", sa.String(64), primary_key=True),
        sa.Column("note", sa.String(200), nullable=False),
        sa.Column("added_at", TS, nullable=False),
    )
    op.create_table(
        "content_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("request_json", sa.Text(), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("is_mock", sa.Boolean(), nullable=False),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("model", sa.String(128), nullable=True),
        sa.Column("created_at", TS, nullable=False),
    )
    op.create_index("ix_content_items_kind", "content_items", ["kind"])
    op.create_index("ix_content_items_created_at", "content_items", ["created_at"])


def downgrade() -> None:
    op.drop_table("content_items")
    op.drop_table("youtube_watchlist")
    op.drop_table("youtube_public_cache")
