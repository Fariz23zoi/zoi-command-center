"""ADR 0015 — akses dari HP lewat Tailscale Serve (mode local)."""

from __future__ import annotations

import pytest
from starlette.websockets import WebSocketDisconnect

from app.config.modes import ConfigError, resolve_runtime
from tests.conftest import make_settings

REMOTE = "https://laptop-zoi.tail1234.ts.net"
HOST = "laptop-zoi.tail1234.ts.net"


def test_remote_url_validation(tmp_path):
    runtime = resolve_runtime(make_settings(tmp_path, remote_url=REMOTE + "/"))
    assert runtime.remote_url == REMOTE and runtime.remote_host == HOST
    assert REMOTE in runtime.self_origins and any("Tailscale" in w for w in runtime.warnings)
    for bad in ("http://laptop.tail1.ts.net", "https://contoh.com", "https://x.tail1.ts.net/zoi"):
        with pytest.raises(ConfigError, match="ZOI_REMOTE_URL"):
            resolve_runtime(make_settings(tmp_path, remote_url=bad))


def test_remote_requests_need_tailscale_identity(client_factory):
    client = client_factory(remote_url=REMOTE, remote_user="Fariz@Contoh.com")
    # dari laptop sendiri (127.0.0.1) tetap seperti biasa
    assert client.get("/api/health").status_code == 200
    # lewat alamat Tailscale tanpa identitas → ditolak
    assert client.get("/api/health", headers={"host": HOST}).status_code == 403
    # akun lain → ditolak; akun pemilik (tanpa beda huruf besar) → boleh
    other = {"host": HOST, "Tailscale-User-Login": "orang@lain.com"}
    assert client.get("/api/health", headers=other).status_code == 403
    owner = {"host": HOST, "Tailscale-User-Login": "fariz@contoh.com"}
    assert client.get("/api/health", headers=owner).status_code == 200
    page = client.get("/api/config", headers=owner)
    assert page.status_code == 200
    with client.websocket_connect("/ws", headers={**owner, "origin": REMOTE}) as ws:
        assert ws.receive_json()["type"] == "hello"


def test_unknown_host_still_rejected_without_remote(client):
    assert client.get("/api/health", headers={"host": HOST}).status_code == 400


def test_websocket_via_tailscale_without_identity_rejected(client_factory):
    client = client_factory(remote_url=REMOTE)
    headers = {"host": HOST, "origin": REMOTE}
    with pytest.raises(WebSocketDisconnect), client.websocket_connect("/ws", headers=headers) as ws:
        ws.receive_json()


def test_remote_url_rejected_in_online_mode(tmp_path):
    with pytest.raises(ConfigError, match="hanya untuk mode local"):
        resolve_runtime(make_settings(tmp_path, mode="online", remote_url=REMOTE,
                                      database_url="postgresql://u:p@h/db", secret_key="k" * 32,
                                      setup_token="t" * 16, public_url="https://zoi.example.com"))
