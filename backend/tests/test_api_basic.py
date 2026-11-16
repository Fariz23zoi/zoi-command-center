from __future__ import annotations

import shutil

from app.system import detectors


def test_health(client):
    body = client.get("/api/health").json()
    assert body["status"] == "ok" and body["mode"] == "development"


def test_config_development(client):
    cfg = client.get("/api/config").json()
    assert cfg["mode"] == "development"
    assert cfg["provider"] == "mock" and cfg["is_mock"] is True
    assert "MOCK" in cfg["banner"]


def test_config_local(client_factory):
    cfg = client_factory(mode="local").get("/api/config").json()
    assert cfg["mode"] == "local" and cfg["banner"] is None and cfg["is_mock"] is False
    assert cfg["provider"] == "ollama"


def test_system_status_is_real_and_sourced(client):
    data = client.get("/api/system/status").json()
    assert data["source"] and data["checked_at"]
    assert data["resources"]["memory"]["total_bytes"] > 0
    assert set(data["tools"]) == set(detectors.TOOLS)


def test_missing_tools_reported_not_invented(monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda _name: None)
    result = detectors.detect_tool("ffmpeg")
    assert result == {"name": "ffmpeg", "found": False, "version": None, "path": None}


def test_preferences_roundtrip_and_validation(client):
    assert client.get("/api/preferences").json() == {"ui_language": "id", "avatar_mode_preference": "auto"}
    assert client.put("/api/preferences", json={"ui_language": "en", "avatar_mode_preference": "2d"}).status_code == 200
    assert client.get("/api/preferences").json()["avatar_mode_preference"] == "2d"
    assert client.put("/api/preferences", json={"ui_language": "fr"}).status_code == 422
    assert client.put("/api/preferences", json={"clipper_dir": "C:/x"}).status_code == 422


def test_unknown_api_returns_json_404(client):
    response = client.get("/api/tidak-ada")
    assert response.status_code == 404 and response.json()["error"]["code"] == "not_found"


def test_provider_status_development(client):
    status = client.get("/api/provider/status").json()
    assert status["name"] == "mock" and status["is_mock"] is True and status["available"] is True


def test_websocket_runtime_installed():
    """uvicorn tanpa pustaka WebSocket menolak /ws di server sungguhan (TestClient tidak mendeteksinya)."""
    import importlib.util

    assert importlib.util.find_spec("websockets") is not None


def test_port_check_ignores_time_wait_but_detects_listener():
    import socket

    with socket.socket() as listener:
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # seperti listener uvicorn
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
        listener.listen()
        assert detectors.port_available("127.0.0.1", port) is False
        client = socket.create_connection(("127.0.0.1", port))
        conn, _ = listener.accept()
        conn.close()  # sisi server menutup lebih dulu → TIME_WAIT di port server
        client.close()
    assert detectors.port_available("127.0.0.1", port) is True
