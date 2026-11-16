"""Ekspor/impor seluruh data ZOI sebagai satu file ZIP berverifikasi.

Isi arsip:
  manifest.json  — format, versi aplikasi, revisi skema, jumlah baris per tabel, SHA-256 tiap file
  zoi.db         — salinan konsisten database (SQLite backup API)
  files/...      — file data lain di ZOI_DATA_DIR (media, paket produksi) — path relatif
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import sqlite3
import tempfile
import zipfile
from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

from app import __version__
from app.db.migrations import (
    backup_database,
    current_revision,
    known_revisions,
    sqlite_backup,
    upgrade_database,
)
from app.db.session import DB_FILENAME

FORMAT = "zoi.backup/v1"
EXCLUDED_TOP_LEVEL = {"backups", "logs", "exports"}
EXCLUDED_DB_FILES = {DB_FILENAME, f"{DB_FILENAME}-wal", f"{DB_FILENAME}-shm", f"{DB_FILENAME}-journal"}
USER_TABLES_SQL = (
    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
)


class PortabilityError(Exception):
    pass


@dataclass(frozen=True)
class ExportResult:
    path: Path
    manifest: dict


@dataclass(frozen=True)
class ImportResult:
    manifest: dict
    backup: Path | None
    table_counts: dict[str, int]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def table_counts(db_file: Path) -> dict[str, int]:
    with closing(sqlite3.connect(db_file)) as conn:
        tables = [row[0] for row in conn.execute(USER_TABLES_SQL)]
        # nama tabel berasal dari sqlite_master (bukan input pengguna)
        return {t: conn.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0] for t in tables}  # noqa: S608


def _data_files(data_dir: Path) -> list[Path]:
    files = []
    for path in sorted(data_dir.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(data_dir)
        if rel.parts[0] in EXCLUDED_TOP_LEVEL or (len(rel.parts) == 1 and rel.name in EXCLUDED_DB_FILES):
            continue
        files.append(path)
    return files


def _strip_mock(db_file: Path) -> None:
    with closing(sqlite3.connect(db_file)) as conn:
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("DELETE FROM messages WHERE is_mock = 1")
        conn.execute("DELETE FROM conversations WHERE is_mock = 1")
        conn.commit()
        conn.execute("VACUUM")


def export_data(data_dir: Path, out_path: Path | None = None, *, exclude_mock: bool = False) -> ExportResult:
    db_file = data_dir / DB_FILENAME
    if not db_file.exists():
        raise PortabilityError(f"Database tidak ditemukan: {db_file}")

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    if out_path is None:
        out_path = data_dir / "exports" / f"zoi-backup-{stamp}.zip"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="zoi-export-") as tmp:
        snapshot = Path(tmp) / DB_FILENAME
        sqlite_backup(db_file, snapshot)
        if exclude_mock:
            _strip_mock(snapshot)

        files = _data_files(data_dir)
        manifest = {
            "format": FORMAT,
            "app_version": __version__,
            "schema_revision": current_revision(snapshot),
            "created_at": datetime.now(UTC).isoformat(),
            "exclude_mock": exclude_mock,
            "tables": table_counts(snapshot),
            "files": {DB_FILENAME: _sha256(snapshot)}
            | {f"files/{p.relative_to(data_dir).as_posix()}": _sha256(p) for p in files},
        }
        with zipfile.ZipFile(out_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False))
            zf.write(snapshot, DB_FILENAME)
            for path in files:
                zf.write(path, f"files/{path.relative_to(data_dir).as_posix()}")
    return ExportResult(out_path, manifest)


def _safe_member(name: str) -> PurePosixPath:
    member = PurePosixPath(name)
    if member.is_absolute() or ".." in member.parts or re.match(r"^[A-Za-z]:", name) or "\\" in name:
        raise PortabilityError(f"Arsip berisi path tidak aman: {name}")
    return member


def read_manifest(zip_path: Path) -> dict:
    try:
        with zipfile.ZipFile(zip_path) as zf:
            manifest = json.loads(zf.read("manifest.json"))
    except (KeyError, zipfile.BadZipFile, json.JSONDecodeError) as exc:
        raise PortabilityError(f"Arsip ZOI tidak valid atau rusak: {exc}") from exc
    if manifest.get("format") != FORMAT:
        raise PortabilityError(f"Format arsip tidak dikenal: {manifest.get('format')!r}")
    return manifest


def verify_archive(zip_path: Path) -> dict:
    manifest = read_manifest(zip_path)
    with zipfile.ZipFile(zip_path) as zf:
        names = {n for n in zf.namelist() if not n.endswith("/")} - {"manifest.json"}
        for name in names:
            _safe_member(name)
        expected = manifest.get("files", {})
        if set(expected) != names:
            raise PortabilityError("Daftar file di arsip tidak cocok dengan manifest.")
        for name, digest in expected.items():
            if hashlib.sha256(zf.read(name)).hexdigest() != digest:
                raise PortabilityError(f"Checksum tidak cocok untuk {name} — arsip rusak atau diubah.")
    revision = manifest.get("schema_revision")
    if revision is not None and revision not in known_revisions():
        raise PortabilityError(
            f"Arsip memakai revisi skema '{revision}' yang tidak dikenal versi aplikasi ini. Perbarui ZOI dulu."
        )
    return manifest


def import_data(zip_path: Path, data_dir: Path) -> ImportResult:
    """Pulihkan arsip ke data_dir. Database lama selalu di-backup dulu. Aplikasi harus dalam keadaan berhenti."""
    manifest = verify_archive(zip_path)
    data_dir.mkdir(parents=True, exist_ok=True)
    db_file = data_dir / DB_FILENAME
    backup = backup_database(db_file, "pre-import") if db_file.exists() else None

    with tempfile.TemporaryDirectory(prefix="zoi-import-") as tmp, zipfile.ZipFile(zip_path) as zf:
        staged = Path(tmp)
        for name in manifest["files"]:
            member = _safe_member(name)
            target = staged / Path(*member.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(name) as src, target.open("wb") as dst:
                shutil.copyfileobj(src, dst)

        for suffix in ("-wal", "-shm", "-journal"):
            (data_dir / f"{DB_FILENAME}{suffix}").unlink(missing_ok=True)
        shutil.copy2(staged / DB_FILENAME, db_file)
        files_root = staged / "files"
        if files_root.exists():
            for src in files_root.rglob("*"):
                if src.is_file():
                    dest = data_dir / src.relative_to(files_root)
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dest)

    counts_before_migration = table_counts(db_file)
    for table, expected in manifest["tables"].items():
        if counts_before_migration.get(table) != expected:
            raise PortabilityError(
                f"Jumlah baris tabel {table} tidak cocok setelah impor "
                f"({counts_before_migration.get(table)} ≠ {expected})."
            )
    upgrade_database(db_file)
    return ImportResult(manifest=manifest, backup=backup, table_counts=table_counts(db_file))


ABSOLUTE_PATH_RE = re.compile(r"(^|[\s\"'=:])([A-Za-z]:[\\/]|\\\\[^\\]+\\|/(?:home|Users|mnt|var|tmp|root|opt|usr)/)")
_PATH_TOKEN_RE = re.compile(r"(?:[A-Za-z]:[\\/]|\\\\|/(?:home|Users|mnt|var|tmp|root|opt|usr)/)[^\s\"',;)]*")
MACHINE_KEYS = {"executable", "path"}
LOCAL_PATH = "[path lokal]"


def strip_machine_paths(value: object) -> object:
    """Hapus path khusus mesin dari data yang akan disimpan ke database (aturan portabilitas)."""
    if isinstance(value, dict):
        return {k: (LOCAL_PATH if v else v) if k in MACHINE_KEYS else strip_machine_paths(v)
                for k, v in value.items()}
    if isinstance(value, list):
        return [strip_machine_paths(v) for v in value]
    if isinstance(value, str):
        return _PATH_TOKEN_RE.sub(LOCAL_PATH, value)
    return value


def find_absolute_paths(db_file: Path) -> list[tuple[str, str, str]]:
    """Cari teks yang tampak seperti path absolut mesin di semua kolom teks (aturan portabilitas)."""
    hits: list[tuple[str, str, str]] = []
    with closing(sqlite3.connect(db_file)) as conn:
        tables = [row[0] for row in conn.execute(USER_TABLES_SQL) if row[0] != "alembic_version"]
        for table in tables:
            columns = [row[1] for row in conn.execute(f'PRAGMA table_info("{table}")')]
            for row in conn.execute(f'SELECT * FROM "{table}"'):  # noqa: S608
                for column, value in zip(columns, row, strict=True):
                    if isinstance(value, str) and ABSOLUTE_PATH_RE.search(value):
                        hits.append((table, column, value[:120]))
    return hits
