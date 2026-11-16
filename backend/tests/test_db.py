from __future__ import annotations

import sqlite3

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine

from app.db import models  # noqa: F401
from app.db.base import Base
from app.db.migrations import (
    backup_database,
    current_revision,
    downgrade_database,
    head_revision,
    rotate_backups,
    upgrade_database,
)

EXPECTED_TABLES = {"app_meta", "tasks", "task_events", "system_checks", "network_audit", "conversations",
                   "messages", "alembic_version", "model_evaluations", "memories", "agent_runs", "approvals",
                   # Indeks pencarian memori (FTS5) — tabel bayangan SQLite, sengaja di luar model ORM.
                   "memories_fts", "memories_fts_data", "memories_fts_idx", "memories_fts_docsize",
                   "memories_fts_config", "youtube_channel_snapshots", "youtube_cache", "youtube_quota",
                   "youtube_public_cache", "youtube_watchlist", "content_items", "auth_sessions", "secrets"}


def tables(db_file):
    with sqlite3.connect(db_file) as conn:
        return {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def test_upgrade_creates_all_tables(tmp_path):
    db_file = tmp_path / "zoi.db"
    assert upgrade_database(db_file) is None  # database baru → tidak ada yang perlu di-backup
    assert tables(db_file) == EXPECTED_TABLES
    assert current_revision(db_file) == head_revision()
    assert upgrade_database(db_file) is None  # idempoten


def test_migration_matches_models(tmp_path):
    db_file = tmp_path / "zoi.db"
    upgrade_database(db_file)
    engine = create_engine(f"sqlite:///{db_file}")
    with engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    engine.dispose()
    # FTS5 dikelola SQL mentah di migrasi 0003, bukan lewat model ORM.
    diff = [d for d in diff if not (d[0] == "remove_table" and d[1].name.startswith("memories_fts"))]
    assert diff == [], f"Migrasi tidak sama dengan model: {diff}"


def test_downgrade_is_clean_and_backs_up(tmp_path):
    db_file = tmp_path / "zoi.db"
    upgrade_database(db_file)
    downgrade_database(db_file)
    assert tables(db_file) == {"alembic_version"}
    assert list((tmp_path / "backups").glob("zoi-pre-downgrade-*.db"))


def test_backup_and_rotation(tmp_path):
    db_file = tmp_path / "zoi.db"
    upgrade_database(db_file)
    for _ in range(9):
        backup_database(db_file, "manual")
    rotate_backups(tmp_path / "backups", "zoi-manual-")
    backups = list((tmp_path / "backups").glob("zoi-manual-*.db"))
    assert len(backups) == 7
    assert tables(backups[0]) == EXPECTED_TABLES


def test_newer_unknown_schema_rejected(tmp_path):
    db_file = tmp_path / "zoi.db"
    upgrade_database(db_file)
    with sqlite3.connect(db_file) as conn:
        conn.execute("UPDATE alembic_version SET version_num='9999_dari_masa_depan'")
    with pytest.raises(RuntimeError, match="lebih baru"):
        upgrade_database(db_file)


def test_wal_and_foreign_keys(client):
    ctx = client.app.state.zoi
    with ctx.db.engine.connect() as conn:
        assert conn.exec_driver_sql("PRAGMA journal_mode").scalar() == "wal"
        assert conn.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1
