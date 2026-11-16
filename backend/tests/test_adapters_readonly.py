"""ZOI tidak boleh mengubah satu file pun di CLIPPER / Blueprint Studio.

Jika env ZOI_TEST_CLIPPER_DIR / ZOI_TEST_BLUEPRINT_FILE diisi, tes memakai salinan ASLI aplikasi itu.
Jika tidak, dipakai struktur tiruan dengan bentuk yang sama.
"""

from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path

import pytest

from tests.conftest import wait_task


def snapshot(root: Path) -> dict[str, tuple[str, int, int]]:
    files = [root] if root.is_file() else sorted(p for p in root.rglob("*") if p.is_file() and ".git" not in p.parts)
    result = {}
    for path in files:
        stat = path.stat()
        result[str(path)] = (hashlib.sha256(path.read_bytes()).hexdigest(), stat.st_size, stat.st_mtime_ns)
    return result


@pytest.fixture
def clipper_dir(tmp_path: Path) -> Path:
    real = os.environ.get("ZOI_TEST_CLIPPER_DIR")
    if real:
        return Path(real)
    root = tmp_path / "zoi-ai-clipper"
    (root / "shorts_generator").mkdir(parents=True)
    for name in ("app.py", "main.py", "LICENSE", "shorts_generator/__init__.py"):
        (root / name).write_text("# tiruan\n", encoding="utf-8")
    return root


@pytest.fixture
def blueprint_file(tmp_path: Path) -> Path:
    real = os.environ.get("ZOI_TEST_BLUEPRINT_FILE")
    if real:
        return Path(real)
    path = tmp_path / "Blueprint_Studio.html"
    path.write_text("<!DOCTYPE html><html><head><title>Blueprint Studio</title></head></html>", encoding="utf-8")
    return path


def test_detection_is_read_only(client_factory, clipper_dir, blueprint_file):
    before = snapshot(clipper_dir) | snapshot(blueprint_file)
    client = client_factory(clipper_dir=str(clipper_dir), blueprint_file=str(blueprint_file))

    adapters = {a["name"]: a for a in client.get("/api/adapters").json()["adapters"]}
    assert adapters["zoi_ai_clipper"]["found"] is True, adapters["zoi_ai_clipper"]["problems"]
    assert adapters["blueprint_studio"]["found"] is True, adapters["blueprint_studio"]["problems"]

    task = client.post("/api/tasks/system-check").json()
    wait_task(client, task["id"], {"COMPLETED"})

    assert snapshot(clipper_dir) | snapshot(blueprint_file) == before
    assert not any(name == "shorts_generator" or name.startswith("shorts_generator.") for name in sys.modules)


def test_unconfigured_and_missing_paths_reported(client_factory, tmp_path):
    client = client_factory(clipper_dir=str(tmp_path / "tidak-ada"))
    adapters = {a["name"]: a for a in client.get("/api/adapters").json()["adapters"]}
    assert adapters["zoi_ai_clipper"]["configured"] and not adapters["zoi_ai_clipper"]["found"]
    assert not adapters["blueprint_studio"]["configured"]
    assert "ZOI_BLUEPRINT_FILE" in adapters["blueprint_studio"]["problems"][0]


def test_wrong_html_not_accepted(client_factory, tmp_path):
    other = tmp_path / "lain.html"
    other.write_text("<title>Bukan</title>", encoding="utf-8")
    adapters = {a["name"]: a for a in client_factory(blueprint_file=str(other)).get("/api/adapters").json()["adapters"]}
    assert adapters["blueprint_studio"]["found"] is False


def test_clipper_launcher_starts_and_stops_without_touching_repo(client_factory, tmp_path):
    import socket
    import sys
    import time

    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    root = tmp_path / "zoi-ai-clipper"
    (root / "shorts_generator").mkdir(parents=True)
    for name in ("main.py", "LICENSE"):
        (root / name).write_text("x", encoding="utf-8")
    (root / "app.py").write_text(
        "import http.server\n"
        f"http.server.HTTPServer(('127.0.0.1', {port}), http.server.BaseHTTPRequestHandler).serve_forever()\n",
        encoding="utf-8")
    before = snapshot(root)

    bare = client_factory()
    assert bare.get("/api/clipper/status").json()["can_start"] is False
    assert bare.post("/api/clipper/start").status_code == 409

    client = client_factory(clipper_dir=str(root), clipper_python=sys.executable)
    adapter = next(a for a in client.app.state.zoi.adapters if a.name == "zoi_ai_clipper")
    adapter.port = port
    assert client.get("/api/clipper/status").json() == {"running": False, "port": port, "can_start": True,
                                                        "reason": None, "started_by_zoi": False}
    assert client.post("/api/clipper/start").json()["started_by_zoi"] is True
    deadline = time.monotonic() + 10
    while not adapter.running() and time.monotonic() < deadline:
        time.sleep(0.1)
    assert client.get("/api/clipper/status").json()["running"] is True
    stopped = client.post("/api/clipper/stop").json()
    assert stopped["started_by_zoi"] is False and stopped["running"] is False
    assert snapshot(root) == before
