"""Migrasi Alembic yang aman: backup otomatis sebelum skema diubah."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Engine, create_engine, pool

from alembic import command

BACKEND_DIR = Path(__file__).resolve().parents[2]
ALEMBIC_INI = BACKEND_DIR / "alembic.ini"
BACKUP_DIRNAME = "backups"
KEEP_BACKUPS = 7


def _config(db_file: Path) -> Config:
    cfg = Config(str(ALEMBIC_INI))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_file.as_posix()}")
    return cfg


def head_revision() -> str:
    script = ScriptDirectory.from_config(_config(Path("unused.db")))
    head = script.get_current_head()
    assert head is not None
    return head


def known_revisions() -> set[str]:
    script = ScriptDirectory.from_config(_config(Path("unused.db")))
    return {rev.revision for rev in script.walk_revisions()}


def current_revision(db_file: Path) -> str | None:
    if not db_file.exists():
        return None
    engine = create_engine(f"sqlite:///{db_file.as_posix()}", poolclass=pool.NullPool)
    try:
        with engine.connect() as conn:
            return MigrationContext.configure(conn).get_current_revision()
    finally:
        engine.dispose()


def sqlite_backup(src: Path, dest: Path) -> Path:
    """Salinan konsisten memakai SQLite backup API (aman walau database sedang dibuka — penting di Windows)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(src)) as source, closing(sqlite3.connect(dest)) as target:
        source.backup(target)
        # Salinan berdiri sendiri: satu file utuh, tanpa file -wal pendamping.
        target.execute("PRAGMA journal_mode=DELETE")
    return dest


def rotate_backups(backup_dir: Path, prefix: str, keep: int = KEEP_BACKUPS) -> None:
    files = sorted(backup_dir.glob(f"{prefix}*.db"))
    for old in files[:-keep]:
        old.unlink(missing_ok=True)


def backup_database(db_file: Path, label: str) -> Path | None:
    if not db_file.exists() or db_file.stat().st_size == 0:
        return None
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    prefix = f"zoi-{label}-"
    dest = db_file.parent / BACKUP_DIRNAME / f"{prefix}{stamp}.db"
    sqlite_backup(db_file, dest)
    rotate_backups(dest.parent, prefix)
    return dest


def upgrade_database(db_file: Path) -> Path | None:
    """Naikkan skema ke head. Mengembalikan path backup jika ada perubahan pada database yang sudah ada."""
    head = head_revision()
    current = current_revision(db_file)
    if current == head:
        return None
    if current is not None and current not in known_revisions():
        raise RuntimeError(
            f"Database memakai revisi skema '{current}' yang lebih baru dari aplikasi ini. "
            "Perbarui aplikasi ZOI sebelum membuka data ini."
        )
    backup = backup_database(db_file, f"pre-migrate-{current or 'empty'}") if current is not None else None
    db_file.parent.mkdir(parents=True, exist_ok=True)
    command.upgrade(_config(db_file), "head")
    return backup


def upgrade_engine(engine: Engine) -> bool:
    """Naikkan skema database server (Postgres) ke head. Tanpa backup file: cadangan dibuat lewat unduhan data."""
    head = head_revision()
    with engine.connect() as conn:
        current = MigrationContext.configure(conn).get_current_revision()
    if current == head:
        return False
    if current is not None and current not in known_revisions():
        raise RuntimeError(
            f"Database memakai revisi skema '{current}' yang lebih baru dari aplikasi ini. "
            "Perbarui aplikasi ZOI sebelum membuka data ini."
        )
    cfg = _config(Path("unused.db"))
    with engine.begin() as conn:
        cfg.attributes["connection"] = conn
        command.upgrade(cfg, "head")
    return True


def downgrade_database(db_file: Path, target: str = "base") -> None:
    backup_database(db_file, "pre-downgrade")
    command.downgrade(_config(db_file), target)
