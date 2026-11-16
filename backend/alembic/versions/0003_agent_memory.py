"""Phase 5 — agen & memori: memories (+ FTS5), agent_runs, approvals, messages.agent_run_id.

Revision ID: 0003_agent_memory
Revises: 0002_local_ai
Create Date: 2026-11-14
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0003_agent_memory"
down_revision = "0002_local_ai"
branch_labels = None
depends_on = None

TS = sa.String(32)

FTS = [
    # Tabel FTS5 "external content": isi tetap di `memories`, FTS hanya indeks. Trigger menjaga keduanya sinkron.
    "CREATE VIRTUAL TABLE memories_fts USING fts5(content, content='memories', content_rowid='rowid', "
    "tokenize='unicode61 remove_diacritics 2')",
    "CREATE TRIGGER memories_ai AFTER INSERT ON memories BEGIN "
    "INSERT INTO memories_fts(rowid, content) VALUES (new.rowid, new.content); END",
    "CREATE TRIGGER memories_ad AFTER DELETE ON memories BEGIN "
    "INSERT INTO memories_fts(memories_fts, rowid, content) VALUES ('delete', old.rowid, old.content); END",
    "CREATE TRIGGER memories_au AFTER UPDATE OF content ON memories BEGIN "
    "INSERT INTO memories_fts(memories_fts, rowid, content) VALUES ('delete', old.rowid, old.content); "
    "INSERT INTO memories_fts(rowid, content) VALUES (new.rowid, new.content); END",
]


def upgrade() -> None:
    op.create_table(
        "memories",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("source", sa.String(16), nullable=False),
        sa.Column("is_mock", sa.Boolean(), nullable=False),
        sa.Column("created_at", TS, nullable=False),
        sa.Column("updated_at", TS, nullable=False),
    )
    op.create_index("ix_memories_updated_at", "memories", ["updated_at"])
    for statement in FTS:
        op.execute(statement)

    op.create_table(
        "agent_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("conversation_id", sa.String(36), nullable=True),
        sa.Column("request", sa.Text(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("plan_json", sa.Text(), nullable=True),
        sa.Column("errors_json", sa.Text(), nullable=False),
        sa.Column("results_json", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("warnings_json", sa.Text(), nullable=False),
        sa.Column("task_id", sa.String(36), nullable=True),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("is_mock", sa.Boolean(), nullable=False),
        sa.Column("created_at", TS, nullable=False),
        sa.Column("updated_at", TS, nullable=False),
    )
    op.create_index("ix_agent_runs_conversation_id", "agent_runs", ["conversation_id"])
    op.create_index("ix_agent_runs_status", "agent_runs", ["status"])
    op.create_index("ix_agent_runs_created_at", "agent_runs", ["created_at"])

    op.create_table(
        "approvals",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("run_id", sa.String(36), nullable=False),
        sa.Column("step_index", sa.Integer(), nullable=False),
        sa.Column("tool", sa.String(64), nullable=False),
        sa.Column("args_json", sa.Text(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("is_mock", sa.Boolean(), nullable=False),
        sa.Column("created_at", TS, nullable=False),
        sa.Column("decided_at", TS, nullable=True),
    )
    op.create_index("ix_approvals_run_id", "approvals", ["run_id"])
    op.create_index("ix_approvals_status", "approvals", ["status"])
    op.create_index("ix_approvals_created_at", "approvals", ["created_at"])

    op.add_column("messages", sa.Column("agent_run_id", sa.String(36), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("messages") as batch:
        batch.drop_column("agent_run_id")
    for name in ("approvals", "agent_runs"):
        for index in [i["name"] for i in sa.inspect(op.get_bind()).get_indexes(name)]:
            op.drop_index(index, table_name=name)
        op.drop_table(name)
    for trigger in ("memories_au", "memories_ad", "memories_ai"):
        op.execute(f"DROP TRIGGER IF EXISTS {trigger}")
    op.execute("DROP TABLE IF EXISTS memories_fts")
    op.drop_index("ix_memories_updated_at", table_name="memories")
    op.drop_table("memories")
