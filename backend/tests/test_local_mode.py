from __future__ import annotations

from pathlib import Path


def make_dist(tmp_path: Path) -> Path:
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>ZOI</title><div id=root></div>", encoding="utf-8")
    (dist / "assets" / "app.js").write_text("console.log('zoi')", encoding="utf-8")
    (tmp_path / "rahasia.txt").write_text("jangan bocor", encoding="utf-8")
    return dist


def test_local_mode_serves_frontend_on_one_origin(client_factory, tmp_path):
    client = client_factory(mode="local", frontend_dist=str(make_dist(tmp_path)))
    root = client.get("/")
    assert root.status_code == 200 and "<title>ZOI</title>" in root.text
    assert "default-src 'self'" in root.headers["content-security-policy"]
    assert client.get("/assets/app.js").text == "console.log('zoi')"
    assert "<title>ZOI</title>" in client.get("/tasks").text  # deep link → SPA
    assert client.get("/api/health").json()["mode"] == "local"
    assert client.get("/api/belum-ada").status_code == 404


def test_path_traversal_blocked(client_factory, tmp_path):
    client = client_factory(mode="local", frontend_dist=str(make_dist(tmp_path)))
    for path in ("/../rahasia.txt", "/%2e%2e/rahasia.txt", "/assets/../../rahasia.txt"):
        assert "jangan bocor" not in client.get(path).text


def test_missing_dist_explains(client_factory, tmp_path):
    response = client_factory(mode="local", frontend_dist=str(tmp_path / "kosong")).get("/")
    assert response.status_code == 503 and "belum di-build" in response.text


def test_development_root_points_to_vite(client):
    assert "5173" in client.get("/").json()["message"]
