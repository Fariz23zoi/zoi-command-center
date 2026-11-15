from __future__ import annotations

import hashlib
import json
import sqlite3
import zipfile
from pathlib import Path

import pytest

from app.db.migrations import upgrade_database
from app.db.portability import (
    PortabilityError,
    export_data,
    find_absolute_paths,
    import_data,
    table_counts,
    verify_archive,
)
from tests.conftest import wait_chat_done, wait_task


def populate(client) -> Path:
    for text in ("halo", "bantuan"):
        res = client.post("/api/chat", json={"message": text}).json()
        wait_chat_done(client, res["conversation_id"])
    task = client.post("/api/tasks/system-check").json()
    wait_task(client, task["id"], {"COMPLETED"})
    client.put("/api/preferences", json={"ui_language": "id", "avatar_mode_preference": "2d"})
    data_dir = client.app.state.zoi.runtime.data_dir
    media = data_dir / "packages" / "paket-uji" / "naskah.txt"
    media.parent.mkdir(parents=True)
    media.write_text("isi paket", encoding="utf-8")
    return data_dir


def rows(db_file: Path, sql: str) -> list:
    with sqlite3.connect(db_file) as conn:
        return conn.execute(sql).fetchall()


def test_roundtrip_identical(client, tmp_path):
    data_dir = populate(client)
    result = export_data(data_dir, tmp_path / "arsip.zip")
    target = tmp_path / "mesin-baru"
    imported = import_data(result.path, target)

    assert imported.table_counts == table_counts(data_dir / "zoi.db")
    assert imported.table_counts["messages"] == 4 and imported.table_counts["tasks"] == 1
    assert (target / "packages" / "paket-uji" / "naskah.txt").read_text(encoding="utf-8") == "isi paket"
    for table in ("messages", "conversations", "tasks", "task_events", "app_meta", "system_checks"):
        query = f"SELECT * FROM {table} ORDER BY 1"
        assert rows(data_dir / "zoi.db", query) == rows(target / "zoi.db", query), table
    assert imported.backup is None


def test_manifest_checksums(client, tmp_path):
    result = export_data(populate(client), tmp_path / "arsip.zip")
    with zipfile.ZipFile(result.path) as zf:
        manifest = json.loads(zf.read("manifest.json"))
        for name, digest in manifest["files"].items():
            assert hashlib.sha256(zf.read(name)).hexdigest() == digest
        assert not any(n.startswith(("files/logs", "files/backups", "files/exports")) for n in zf.namelist())
    assert manifest["schema_revision"] == "0007_online" and manifest["format"] == "zoi.backup/v1"


def test_exclude_mock(client, tmp_path):
    data_dir = populate(client)
    result = export_data(data_dir, tmp_path / "tanpa-mock.zip", exclude_mock=True)
    assert result.manifest["tables"]["messages"] == 0 and result.manifest["tables"]["conversations"] == 0
    assert result.manifest["tables"]["tasks"] == 1
    target = tmp_path / "local"
    import_data(result.path, target)
    assert rows(target / "zoi.db", "SELECT COUNT(*) FROM messages WHERE is_mock=1") == [(0,)]


def test_import_backs_up_existing_data(client, tmp_path):
    result = export_data(populate(client), tmp_path / "a.zip")
    target = tmp_path / "ada-isinya"
    upgrade_database(target / "zoi.db")
    imported = import_data(result.path, target)
    assert imported.backup is not None and imported.backup.exists()


def test_tampered_archive_rejected(client, tmp_path):
    result = export_data(populate(client), tmp_path / "a.zip")
    tampered = tmp_path / "rusak.zip"
    with zipfile.ZipFile(result.path) as src, zipfile.ZipFile(tampered, "w") as dst:
        for item in src.infolist():
            data = src.read(item.filename)
            dst.writestr(item, data + b"x" if item.filename == "zoi.db" else data)
    with pytest.raises(PortabilityError, match="Checksum"):
        verify_archive(tampered)


def test_unsafe_paths_rejected(tmp_path):
    evil = tmp_path / "jahat.zip"
    content = b"x"
    manifest = {"format": "zoi.backup/v1", "schema_revision": None, "tables": {},
                "files": {"../../luar.txt": hashlib.sha256(content).hexdigest()}}
    with zipfile.ZipFile(evil, "w") as zf:
        zf.writestr("manifest.json", json.dumps(manifest))
        zf.writestr("../../luar.txt", content)
    with pytest.raises(PortabilityError, match="tidak aman"):
        verify_archive(evil)


def test_garbage_rejected(tmp_path):
    junk = tmp_path / "bukan.zip"
    junk.write_bytes(b"bukan zip")
    with pytest.raises(PortabilityError):
        verify_archive(junk)


def test_no_absolute_paths_in_database(client):
    data_dir = populate(client)
    assert find_absolute_paths(data_dir / "zoi.db") == []


def test_absolute_path_scanner_detects_violation(client):
    data_dir = populate(client)
    with sqlite3.connect(data_dir / "zoi.db") as conn:
        conn.execute("INSERT INTO app_meta VALUES ('salah', '\"C:\\\\Users\\\\fariz\\\\video.mp4\"', "
                     "'2026-11-14T00:00:00.000000+00:00')")
    assert find_absolute_paths(data_dir / "zoi.db")
