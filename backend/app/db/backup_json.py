"""Cadangan data lintas-database (zoi.backup/v2): ZIP berisi manifest + satu JSON per tabel.

Bekerja di SQLite dan Postgres, jadi dipakai tombol unduh/pulihkan di Settings (mode apa pun).
Tabel `secrets` (API key, token) dan `auth_sessions` TIDAK PERNAH ikut — hubungkan ulang akun setelah pulih.
Format v1 (file SQLite utuh, lewat CLI) tetap ada untuk mode local.
"""

from __future__ import annotations

import hashlib
import io
import json
import zipfile
from datetime import UTC, datetime
from typing import Any

import sqlalchemy as sa
from alembic.runtime.migration import MigrationContext

from app import __version__
from app.db.base import Base, UTCDateTime
from app.db.migrations import head_revision, known_revisions
from app.db.session import Database

FORMAT = "zoi.backup/v2"
EXCLUDED = {"secrets", "auth_sessions"}
# Baris app_meta yang tidak pernah ikut arsip dan tidak pernah ditimpa saat pulih (hash kata sandi login).
PROTECTED_META_KEYS = ("auth:",)
MAX_ARCHIVE_BYTES = 50 * 1024 * 1024


class BackupError(Exception):
    pass


def _parse_dt(value: Any) -> Any:
    """Nilai waktu diekspor sebagai teks ISO; dikembalikan jadi datetime agar kolom UTCDateTime menerimanya."""
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError as exc:
            raise BackupError(f"Nilai waktu tidak valid di arsip: {value!r}") from exc
    return value


def _tables() -> list[sa.Table]:
    return [t for t in Base.metadata.sorted_tables if t.name not in EXCLUDED]


def _revision(db: Database) -> str | None:
    with db.engine.connect() as conn:
        return MigrationContext.configure(conn).get_current_revision()


def export_bytes(db: Database) -> tuple[bytes, dict[str, Any]]:
    """Seluruh data (tanpa rahasia) sebagai ZIP di memori + manifestnya."""
    payloads: dict[str, bytes] = {}
    counts: dict[str, int] = {}
    with db.session() as s:
        for table in _tables():
            rows = [dict(r._mapping) for r in s.execute(sa.select(table))]
            if table.name == "app_meta":
                rows = [r for r in rows if not str(r.get("key", "")).startswith(PROTECTED_META_KEYS)]
            counts[table.name] = len(rows)
            payloads[f"data/{table.name}.json"] = json.dumps(rows, ensure_ascii=False,
                                                             default=str).encode("utf-8")
    manifest = {
        "format": FORMAT, "app_version": __version__, "schema_revision": _revision(db),
        "created_at": datetime.now(UTC).isoformat(), "tables": counts,
        "files": {name: hashlib.sha256(blob).hexdigest() for name, blob in payloads.items()},
    }
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False))
        for name, blob in payloads.items():
            zf.writestr(name, blob)
    return buffer.getvalue(), manifest


def _read_archive(data: bytes) -> tuple[dict[str, Any], dict[str, list[dict[str, Any]]]]:
    if len(data) > MAX_ARCHIVE_BYTES:
        raise BackupError(f"Arsip terlalu besar (maksimal {MAX_ARCHIVE_BYTES // (1024 * 1024)} MB).")
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            manifest = json.loads(zf.read("manifest.json"))
            blobs = {n: zf.read(n) for n in zf.namelist() if n != "manifest.json" and not n.endswith("/")}
    except (KeyError, zipfile.BadZipFile, json.JSONDecodeError) as exc:
        raise BackupError(f"File cadangan tidak valid atau rusak: {exc}") from exc
    if manifest.get("format") != FORMAT:
        raise BackupError(f"Format cadangan tidak dikenal: {manifest.get('format')!r}. Tombol ini menerima "
                          f"file '{FORMAT}' hasil tombol Unduh cadangan.")
    expected = manifest.get("files", {})
    if set(expected) != set(blobs):
        raise BackupError("Daftar file di arsip tidak cocok dengan manifest.")
    for name, digest in expected.items():
        if hashlib.sha256(blobs[name]).hexdigest() != digest:
            raise BackupError(f"Checksum tidak cocok untuk {name} — arsip rusak atau diubah.")
    revision = manifest.get("schema_revision")
    if revision not in known_revisions():
        raise BackupError(f"Cadangan memakai revisi skema '{revision}' yang tidak dikenal versi aplikasi ini. "
                          "Perbarui ZOI dulu, lalu pulihkan lagi.")
    if revision != head_revision():
        raise BackupError(f"Cadangan dibuat dengan skema lama ('{revision}'). Pulihkan dulu di versi ZOI yang "
                          "sama dengan saat cadangan dibuat, atau buat cadangan baru.")
    tables: dict[str, list[dict[str, Any]]] = {}
    for name, blob in blobs.items():
        table = name.removeprefix("data/").removesuffix(".json")
        rows = json.loads(blob)
        if not isinstance(rows, list):
            raise BackupError(f"Isi {name} tidak valid.")
        tables[table] = rows
    return manifest, tables


def restore_bytes(db: Database, data: bytes) -> dict[str, Any]:
    """Kosongkan tabel lalu isi dari arsip, dalam SATU transaksi — gagal berarti data lama utuh."""
    manifest, incoming = _read_archive(data)
    known = {t.name: t for t in _tables()}
    strange = set(incoming) - set(known)
    if strange:
        raise BackupError(f"Arsip berisi tabel yang tidak dikenal: {', '.join(sorted(strange))}.")
    with db.session() as s:
        for table in reversed(_tables()):
            if table.name == "app_meta":
                # kata sandi login saat ini dipertahankan — cadangan tidak pernah membawanya
                key = table.c.key
                s.execute(sa.delete(table).where(sa.not_(sa.or_(
                    *(key.like(f"{p}%") for p in PROTECTED_META_KEYS)))))
                continue
            s.execute(sa.delete(table))
        for table in _tables():
            rows = incoming.get(table.name, [])
            if table.name == "app_meta":
                rows = [r for r in rows if not str(r.get("key", "")).startswith(PROTECTED_META_KEYS)]
            if not rows:
                continue
            columns = {c.name: c for c in table.columns}
            dt_cols = {n for n, c in columns.items() if isinstance(c.type, UTCDateTime)}
            cleaned = [{k: (_parse_dt(v) if k in dt_cols else v) for k, v in row.items() if k in columns}
                       for row in rows]
            s.execute(sa.insert(table), cleaned)
    with db.session() as s:
        counts = {}
        for t in _tables():
            query = sa.select(sa.func.count()).select_from(t)
            if t.name == "app_meta":
                query = query.where(sa.not_(sa.or_(*(t.c.key.like(f"{p}%") for p in PROTECTED_META_KEYS))))
            counts[t.name] = s.execute(query).scalar_one()
    for name, expected in manifest.get("tables", {}).items():
        if name in known and counts.get(name) != expected:
            raise BackupError(f"Jumlah baris tabel {name} tidak cocok setelah pulih "
                              f"({counts.get(name)} ≠ {expected}).")
    return {"tables": counts, "created_at": manifest.get("created_at"),
            "app_version": manifest.get("app_version")}
