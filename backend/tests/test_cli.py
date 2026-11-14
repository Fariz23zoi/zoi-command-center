from __future__ import annotations

import json
import socket

import pytest

from app import cli
from tests.conftest import wait_chat_done


@pytest.fixture
def env(monkeypatch, tmp_path):
    for key in list(__import__("os").environ):
        if key.startswith("ZOI_"):
            monkeypatch.delenv(key)
    monkeypatch.setenv("ZOI_ENV_FILE", str(tmp_path / "tidak-ada.env"))
    monkeypatch.setenv("ZOI_DATA_DIR", str(tmp_path / "data"))
    return monkeypatch


def test_doctor_development(env, capsys):
    assert cli.main(["doctor", "--skip-port", "--json"]) == 0
    checks = {c["name"]: c for c in json.loads(capsys.readouterr().out)}
    assert checks["Python"]["status"] == "OK"
    assert "Mock" in checks["Penyedia AI"]["detail"]


def test_doctor_local_without_frontend_fails(env, tmp_path, capsys):
    env.setenv("ZOI_MODE", "local")
    env.setenv("ZOI_FRONTEND_DIST", str(tmp_path / "kosong"))
    env.setenv("ZOI_OLLAMA_URL", "http://127.0.0.1:9")
    assert cli.main(["doctor", "--skip-port"]) == 1
    out = capsys.readouterr().out
    assert "[FAIL] Frontend" in out and "[WARN] Ollama" in out and "Konfigurasi" in out


def test_doctor_reports_busy_port(env, capsys):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        sock.listen()
        env.setenv("ZOI_PORT", str(sock.getsockname()[1]))
        assert cli.main(["doctor"]) == 1
    assert "sudah dipakai" in capsys.readouterr().out


def test_bad_config_exit_code(env):
    env.setenv("ZOI_MODE", "local")
    env.setenv("ZOI_AI_PROVIDER", "mock")
    assert cli.main(["doctor"]) == 2


def test_export_import_via_cli(env, tmp_path, client_factory, capsys):
    client = client_factory(data_dir=str(tmp_path / "data"))
    res = client.post("/api/chat", json={"message": "halo"}).json()
    wait_chat_done(client, res["conversation_id"])
    archive = tmp_path / "arsip.zip"
    assert cli.main(["data", "export", "--out", str(archive), "--exclude-mock"]) == 0
    assert cli.main(["data", "verify", str(archive)]) == 0
    env.setenv("ZOI_DATA_DIR", str(tmp_path / "baru"))
    env.setenv("ZOI_PORT", "8765")
    assert cli.main(["data", "import", str(archive), "--yes"]) == 0
    assert "Impor selesai" in capsys.readouterr().out


def test_db_upgrade_and_status(env, capsys):
    assert cli.main(["db", "upgrade"]) == 0
    assert cli.main(["db", "status"]) == 0
    assert "0003_agent_memory" in capsys.readouterr().out
