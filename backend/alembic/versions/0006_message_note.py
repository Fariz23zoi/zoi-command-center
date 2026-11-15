"""AI cloud — catatan pada pesan (mis. "dijawab cadangan karena …").

Revision ID: 0006_message_note
Revises: 0005_youtube_public
Create Date: 2026-11-15
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0006_message_note"
down_revision = "0005_youtube_public"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("messages") as batch:
        batch.add_column(sa.Column("note", sa.String(600), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("messages") as batch:
        batch.drop_column("note")
