from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app.logging_setup import get_logger
from app.security.redact import redact_text


def test_csrf_header_required(client):
    raw = TestClient(client.app, base_url="http://127.0.0.1")
    assert raw.post("/api/tasks/system-check").status_code == 403
    assert raw.put("/api/preferences", json={}).status_code == 403
    assert raw.get("/api/health").status_code == 200


def test_untrusted_host_rejected(client):
    evil = TestClient(client.app, base_url="http://zoi.jahat.example")
    assert evil.get("/api/health").status_code == 400


def test_cors_development_only_frontend_origin(client):
    ok = client.options("/api/chat", headers={"Origin": "http://127.0.0.1:5173",
                                               "Access-Control-Request-Method": "POST",
                                               "Access-Control-Request-Headers": "content-type,x-zoi-client"})
    assert ok.headers.get("access-control-allow-origin") == "http://127.0.0.1:5173"
    bad = client.get("/api/health", headers={"Origin": "http://jahat.example"})
    assert "access-control-allow-origin" not in bad.headers


def test_no_cors_in_local_mode(client_factory):
    local = client_factory(mode="local")
    res = local.get("/api/health", headers={"Origin": "http://127.0.0.1:5173"})
    assert "access-control-allow-origin" not in res.headers


def test_security_headers(client):
    headers = client.get("/api/health").headers
    assert headers["x-content-type-options"] == "nosniff" and headers["x-frame-options"] == "DENY"


def test_api_docs_hidden_in_local_mode(client_factory):
    assert client_factory(mode="local").get("/api/docs").status_code == 404


def test_secrets_redacted():
    text = ("kunci sk-ant-abcdefghijklmnopqrstuvwxyz123 dan AIzaSyA1234567890abcdefghijklmnopqrstu "
            "Bearer abcdefghijklmnopqrstuvwxyz api_key=rahasia123456")
    out = redact_text(text)
    assert "sk-ant" not in out and "AIza" not in out and "rahasia123456" not in out
    assert out.count("[DISENSOR]") == 4


def test_log_file_redacts(client):
    ctx = client.app.state.zoi
    get_logger("uji").warning("percobaan", token="ya29.abcdefghijklmnopqrstuvwxyz0123")
    log_file = ctx.runtime.data_dir / "logs" / "zoi.log"
    for handler in __import__("logging").getLogger("zoi").handlers:
        handler.flush()
    lines = [json.loads(line) for line in log_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert any(line.get("event") == "percobaan" for line in lines)
    assert "ya29." not in log_file.read_text(encoding="utf-8")
