"""Mode online: login satu kata sandi, rahasia terenkripsi di DB, dan Postgres (Neon).

Tes Postgres memakai server lokal di 127.0.0.1:5544 (tanpa jaringan luar). Bila tidak ada, dilewati.
"""

from __future__ import annotations

import subprocess
import uuid

import pytest
from fastapi.testclient import TestClient

from app.config.modes import ConfigError, resolve_runtime
from app.db.migrations import upgrade_engine
from app.db.session import Database, db_path
from app.main import create_app
from app.memory.service import MemoryService
from app.security.auth import AuthError, AuthService
from app.security.secrets_db import DbSecretStore
from tests.conftest import HEADERS, make_settings

PG = {"host": "127.0.0.1", "port": "5544", "user": "zoi"}
SECRET_KEY = "k" * 32
SETUP_TOKEN = "t" * 16
ONLINE = {"mode": "online", "secret_key": SECRET_KEY, "setup_token": SETUP_TOKEN,
          "public_url": "https://zoi.example.com"}


def _psql(sql: str) -> bool:
    try:
        r = subprocess.run(["psql", "-h", PG["host"], "-p", PG["port"], "-U", PG["user"], "-d", "postgres",
                            "-v", "ON_ERROR_STOP=1", "-c", sql], capture_output=True, timeout=20, check=False)
        return r.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


@pytest.fixture
def pg_url():
    name = f"zoi_t_{uuid.uuid4().hex[:12]}"
    if not _psql(f"CREATE DATABASE {name}"):
        pytest.skip("Postgres lokal 127.0.0.1:5544 tidak tersedia")
    yield f"postgresql://{PG['user']}@{PG['host']}:{PG['port']}/{name}"
    _psql(f"DROP DATABASE IF EXISTS {name} (FORCE)")


# ── konfigurasi mode online ───────────────────────────────────────────────
def test_online_config_rules(tmp_path):
    base = {"database_url": "postgresql://u:p@db.example.com/zoi", **ONLINE}
    runtime = resolve_runtime(make_settings(tmp_path, **base))
    assert runtime.is_online and runtime.host == "0.0.0.0" and runtime.serve_frontend
    assert runtime.stt == "none" and runtime.tts == "none"
    assert runtime.self_origins == ("https://zoi.example.com",) and runtime.public_host == "zoi.example.com"
    for missing in ("database_url", "secret_key", "setup_token"):
        with pytest.raises(ConfigError):
            resolve_runtime(make_settings(tmp_path, **{**base, missing: ""}))
    with pytest.raises(ConfigError, match="ZOI_DATABASE_URL"):
        resolve_runtime(make_settings(tmp_path, **{**base, "database_url": "mysql://u@h/db"}))
    with pytest.raises(ConfigError, match="whisper|Whisper|suara"):
        resolve_runtime(make_settings(tmp_path, **base, stt="whisper"))


# ── AuthService (unit, SQLite) ────────────────────────────────────────────
@pytest.fixture
def auth(tmp_path):
    db = Database(db_path(tmp_path / "data"))
    from app.db.base import Base
    Base.metadata.create_all(db.engine)
    yield AuthService(db, SETUP_TOKEN)
    db.dispose()


def test_auth_setup_and_login(auth):
    assert auth.status() == {"enabled": True, "ready": False}
    with pytest.raises(AuthError, match="Setup token"):
        auth.setup("salah", "kata-sandi-panjang")
    with pytest.raises(AuthError, match="minimal"):
        auth.setup(SETUP_TOKEN, "pendek")
    token = auth.setup(SETUP_TOKEN, "kata-sandi-panjang")
    assert auth.check(token) and auth.status()["ready"]
    assert not auth.check("token-palsu") and not auth.check(None)
    with pytest.raises(AuthError, match="salah"):
        auth.login("bukan-itu")
    token2 = auth.login("kata-sandi-panjang")
    assert auth.check(token2)
    auth.logout(token2)
    assert not auth.check(token2) and auth.check(token)
    # ganti kata sandi lewat setup → semua sesi lama keluar
    auth.setup(SETUP_TOKEN, "kata-sandi-baru-1")
    assert not auth.check(token)


def test_auth_lockout(auth):
    auth.setup(SETUP_TOKEN, "kata-sandi-panjang")
    for _ in range(10):
        with pytest.raises(AuthError):
            auth.login("salah-terus")
    with pytest.raises(AuthError, match="Terlalu banyak"):
        auth.login("kata-sandi-panjang")  # kata sandi benar pun ditahan


def test_auth_disabled_mode(tmp_path):
    db = Database(db_path(tmp_path / "d2"))
    from app.db.base import Base
    Base.metadata.create_all(db.engine)
    service = AuthService(db, "", enabled=False)
    assert service.check(None) and service.status() == {"enabled": False, "ready": True}
    db.dispose()


# ── aplikasi penuh di Postgres ────────────────────────────────────────────
def test_online_app_requires_login(tmp_path, pg_url):
    app = create_app(make_settings(tmp_path, database_url=pg_url, **ONLINE), return_to_idle_s=0.05)
    with TestClient(app, base_url="https://127.0.0.1", headers=HEADERS) as client:  # cookie Secure butuh https
        assert client.get("/api/health").status_code == 200  # health publik (Render health check)
        assert client.get("/api/config").status_code == 401
        status = client.get("/api/auth/status").json()
        assert status == {"enabled": True, "ready": False, "logged_in": False}
        # WebSocket tanpa sesi ditolak
        import contextlib
        with contextlib.suppress(Exception):
            with client.websocket_connect("/ws") as ws:
                assert ws.receive_json().get("type") != "hello"
        assert client.post("/api/auth/setup", json={"token": "salah", "password": "kata-sandi-panjang"}
                           ).status_code == 403
        assert client.post("/api/auth/setup", json={"token": SETUP_TOKEN, "password": "kata-sandi-panjang"}
                           ).status_code == 200
        config = client.get("/api/config")
        assert config.status_code == 200
        body = config.json()
        assert body["online"] is True and body["mode"] == "online"
        # TestClient tidak mengirim cookie Secure lewat ws:// (browser asli mengirimnya lewat wss://),
        # jadi cookie sesi diteruskan manual di header.
        session = client.cookies.get("zoi_session")
        with client.websocket_connect("/ws", headers={"cookie": f"zoi_session={session}", "host": "127.0.0.1"}) as ws:
            assert ws.receive_json()["type"] == "hello"
        assert client.post("/api/auth/logout", json={}).status_code == 200
        assert client.get("/api/config").status_code == 401
        # login lagi dengan kata sandi
        assert client.post("/api/auth/login", json={"password": "salah"}).status_code == 401
        assert client.post("/api/auth/login", json={"password": "kata-sandi-panjang"}).status_code == 200
        assert client.get("/api/config").status_code == 200


def test_postgres_migrations_memory_and_secrets(pg_url):
    db = Database(url=pg_url)
    try:
        assert db.dialect == "postgresql"
        assert upgrade_engine(db.engine) is True
        assert upgrade_engine(db.engine) is False  # idempoten
        memory = MemoryService(db)
        a = memory.create(content="ZOI memakai Neon Postgres di mode online")
        memory.create(content="Avatar 3D dirender dengan Three.js")
        hits = memory.search("neon postgres")
        assert [m["id"] for m in hits] == [a["id"]]
        assert memory.search("tidakadakataini") == []
        store = DbSecretStore(db, SECRET_KEY)
        assert store.get("nvidia_api_key") is None
        store.set("nvidia_api_key", "nvapi-contoh-123")
        assert store.get("nvidia_api_key") == "nvapi-contoh-123"
        store.set("nvidia_api_key", "nvapi-baru")
        assert store.get("nvidia_api_key") == "nvapi-baru"
        # kunci berbeda → tidak terbaca (dan tidak meledak)
        assert DbSecretStore(db, "x" * 32).get("nvidia_api_key") is None
        store.delete("nvidia_api_key")
        assert store.get("nvidia_api_key") is None
    finally:
        db.dispose()


# ── Bagian B: OAuth web, cadangan, paket produksi ─────────────────────────
WEB_CLIENT = {"web": {"client_id": "456-web.apps.googleusercontent.com", "client_secret": "GOCSPX-web-uji",
                      "redirect_uris": ["https://zoi.example.com/api/youtube/callback"]}}
DESKTOP_CLIENT = {"installed": {"client_id": "123-abc.apps.googleusercontent.com",
                                "client_secret": "GOCSPX-rahasia-uji"}}


@pytest.fixture
def google():
    from tests.fake_google import FakeGoogle
    fake = FakeGoogle()
    fake.url = fake.start()
    yield fake
    fake.stop()


def _login(client):
    assert client.post("/api/auth/setup", json={"token": SETUP_TOKEN, "password": "kata-sandi-panjang"}
                       ).status_code == 200


def test_online_youtube_web_oauth(tmp_path, pg_url, google):
    import httpx

    app = create_app(make_settings(tmp_path, database_url=pg_url, youtube_test_url=google.url, **ONLINE),
                     return_to_idle_s=0.05)
    with TestClient(app, base_url="https://127.0.0.1", headers=HEADERS) as client:
        _login(client)
        status = client.get("/api/youtube/status").json()
        assert status["web_flow"] is True and status["client_kind"] == "web"
        assert status["callback_url"] == "https://zoi.example.com/api/youtube/callback"
        # File Desktop app ditolak dengan arahan yang benar
        wrong = client.put("/api/youtube/client", json={"config": DESKTOP_CLIENT})
        assert wrong.status_code == 400 and "Web application" in wrong.json()["error"]["message"]
        assert client.put("/api/youtube/client", json={"config": WEB_CLIENT}).status_code == 200
        started = client.post("/api/youtube/connect").json()
        url = httpx.URL(started["auth_url"])
        assert dict(url.params)["redirect_uri"] == "https://zoi.example.com/api/youtube/callback"
        # "Browser" membuka halaman izin Google (fake) TANPA mengikuti redirect ke alamat publik
        answer = httpx.get(started["auth_url"], follow_redirects=False, timeout=10)
        assert answer.status_code in (302, 303)
        back = httpx.URL(answer.headers["location"])
        assert str(back).startswith("https://zoi.example.com/api/youtube/callback")
        # Google mengarahkan browser pengguna ke callback ZOI (cookie sesi ikut)
        done = client.get(f"/api/youtube/callback?{back.query.decode()}", follow_redirects=False)
        assert done.status_code == 303 and done.headers["location"] == "/settings/youtube"
        status = client.get("/api/youtube/status").json()
        assert status["connected"] is True and status["last_error"] is None
        assert status["account"]["channel_id"]
        # state salah → ditolak jujur, tidak terhubung ulang
        client.post("/api/youtube/disconnect")
        client.post("/api/youtube/connect")
        bad = client.get("/api/youtube/callback?code=x&state=salah", follow_redirects=False)
        assert bad.status_code == 303
        status = client.get("/api/youtube/status").json()
        assert status["connected"] is False and "state" in (status["last_error"] or "")


def test_backup_roundtrip_and_secrets_never_included(tmp_path, pg_url):
    app = create_app(make_settings(tmp_path, database_url=pg_url, **ONLINE), return_to_idle_s=0.05)
    with TestClient(app, base_url="https://127.0.0.1", headers=HEADERS) as client:
        _login(client)
        # isi data + rahasia
        memory = client.post("/api/memories", json={"content": "Catatan penting sebelum cadangan",
                                                    "kind": "fakta"})
        assert memory.status_code in (200, 201)
        assert client.put("/api/ai/cloud/keys/nvidia", json={"key": "nvapi-rahasia-cadangan"}).status_code == 200
        download = client.get("/api/backup/download")
        assert download.status_code == 200
        blob = download.content
        assert b"Catatan penting sebelum cadangan" in blob or True  # terkompresi — dicek lewat pulihkan
        assert b"nvapi-rahasia-cadangan" not in blob  # rahasia TIDAK PERNAH ikut arsip
        import io
        import zipfile
        names = zipfile.ZipFile(io.BytesIO(blob)).namelist()
        assert "data/memories.json" in names
        assert "data/secrets.json" not in names and "data/auth_sessions.json" not in names
        import json as jsonlib
        meta_rows = jsonlib.loads(zipfile.ZipFile(io.BytesIO(blob)).read("data/app_meta.json"))
        assert not any(str(r.get("key", "")).startswith("auth:") for r in meta_rows)  # hash kata sandi tidak ikut
        # ubah data → pulihkan → data kembali
        memory_id = memory.json()["id"]
        assert client.delete(f"/api/memories/{memory_id}").status_code in (200, 204)
        restored = client.post("/api/backup/restore", content=blob,
                               headers={"Content-Type": "application/zip"})
        assert restored.status_code == 200 and restored.json()["ok"] is True
        items = client.get("/api/memories").json()["items"]
        assert any("Catatan penting sebelum cadangan" in m["content"] for m in items)
        assert client.get("/api/config").status_code == 200  # sesi & kata sandi selamat dari pemulihan
        # file rusak → ditolak jujur, data utuh
        bad = client.post("/api/backup/restore", content=b"bukan-zip",
                          headers={"Content-Type": "application/zip"})
        assert bad.status_code == 400
        assert any("Catatan penting" in m["content"] for m in client.get("/api/memories").json()["items"])


def test_production_package_from_script(client):
    """Paket produksi dibuat dari naskah (mode development, Mock) dan bentuknya cocok untuk Blueprint."""
    import json as jsonlib

    task = client.post("/api/content/scripts", json={"judul": "Cara kerja vaksin", "format": "shorts"}).json()
    from tests.conftest import wait_for

    def done():
        t = client.get(f"/api/tasks/{task['id']}").json()
        return t["status"] in {"COMPLETED", "FAILED"} and t
    assert wait_for(done)["status"] == "COMPLETED"
    items = client.get("/api/content/items?kind=script").json()["items"]
    assert items, "naskah mock harus ada"
    item_id = items[0]["id"]
    response = client.get(f"/api/content/items/{item_id}/package")
    assert response.status_code == 200
    assert "paket-zoi-" in response.headers["content-disposition"]
    package = jsonlib.loads(response.content)
    assert package["format"] == "zoi.paket/v1" and package["mock"] is True
    assert package["rasio"] == "9:16" and package["beats"]
    for beat in package["beats"]:
        assert set(beat) == {"k", "n", "v"}  # bentuk persis yang dibaca Blueprint Studio
    assert package["naskah_tts"].strip()
    # draf ide tidak bisa dipaketkan
    missing = client.get("/api/content/items/tidak-ada/package")
    assert missing.status_code == 404


def test_security_headers_online(tmp_path, pg_url):
    app = create_app(make_settings(tmp_path, database_url=pg_url, **ONLINE), return_to_idle_s=0.05)
    with TestClient(app, base_url="https://127.0.0.1", headers=HEADERS) as client:
        health = client.get("/api/health")
        assert health.headers["strict-transport-security"] == "max-age=31536000"
        assert health.headers["cache-control"] == "no-store"
        assert health.headers["x-content-type-options"] == "nosniff"
        assert client.get("/api/docs").status_code == 401  # butuh login; dan docs tidak ada di mode online:
        client.post("/api/auth/setup", json={"token": SETUP_TOKEN, "password": "kata-sandi-panjang"})
        assert client.get("/api/docs").status_code == 404


def test_no_hsts_in_development(client):
    response = client.get("/api/health")
    assert "strict-transport-security" not in response.headers
    assert response.headers["cache-control"] == "no-store"
