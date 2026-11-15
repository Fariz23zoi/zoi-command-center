"""Mode online: sesi login dan rahasia terenkripsi di database.

Revision ID: 0007_online
Revises: 0006_message_note
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0007_online"
down_revision = "0006_message_note"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "auth_sessions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("token_hash", sa.String(length=64), nullable=False, unique=True),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.Column("expires_at", sa.String(length=32), nullable=False),
    )
    op.create_table(
        "secrets",
        sa.Column("name", sa.String(length=64), primary_key=True),
        sa.Column("value_encrypted", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.String(length=32), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("secrets")
    op.drop_table("auth_sessions")
