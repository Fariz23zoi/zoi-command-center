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
