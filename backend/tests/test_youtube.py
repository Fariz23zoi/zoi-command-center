"""Phase 6A — YouTube: OAuth (PKCE + loopback), data channel sendiri, kuota, penyimpanan token, kepatuhan.

Semua tes memakai server Google TIRUAN di komputer ini (tests/fake_google.py). Tidak ada panggilan ke Google.
"""

from __future__ import annotations

import json
import zipfile
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from app.agent.tools import Permission
from app.config.modes import ConfigError, resolve_runtime
from app.db.models import YouTubeQuota
from app.security.cost_guard import CostGuard
from app.youtube.errors import QuotaExceeded, YouTubeError
from app.youtube.oauth import build_auth_url, endpoints, new_pkce, parse_client_config
from app.youtube.quota import UNIT_LIMIT, QuotaTracker, next_reset, quota_day
from app.youtube.secrets_store import SERVICE, SecretStore
from app.youtube.service import ACCOUNT_KEY, TOKEN_NAME
from tests.conftest import make_settings, wait_for
from tests.fake_google import CHANNEL_ID, FakeGoogle

CLIENT_JSON = {"installed": {"client_id": "123-abc.apps.googleusercontent.com", "client_secret": "GOCSPX-rahasia-uji",
                             "auth_uri": "https://jahat.example/auth", "token_uri": "https://jahat.example/token"}}


@pytest.fixture
def google():
    fake = FakeGoogle()
    fake.url = fake.start()
    yield fake
    fake.stop()


@pytest.fixture
def yt(client_factory, google):
    return client_factory(youtube_test_url=google.url)


def browser(auth_url: str) -> httpx.Response:
    """Meniru browser pengguna: buka halaman izin, ikuti redirect ke pendengar loopback ZOI."""
    return httpx.get(auth_url, follow_redirects=True, timeout=10)


def connect(client, *, expect_connected: bool = True) -> dict:
    assert client.put("/api/youtube/client", json={"config": CLIENT_JSON}).status_code == 200
    started = client.post("/api/youtube/connect").json()
    page = browser(started["auth_url"])
    assert page.status_code == 200 and "Tab ini boleh ditutup" in page.text
    status = wait_for(lambda: (s := client.get("/api/youtube/status").json())["pending"] is False and s)
    assert status["connected"] is expect_connected
    return status


# ── konfigurasi & unit ────────────────────────────────────────────────────
@pytest.mark.parametrize("url", ["https://127.0.0.1:5600", "http://example.com:5600", "http://192.168.1.5:5600"])
def test_test_url_must_be_loopback_http(tmp_path, url):
    with pytest.raises(ConfigError):
        resolve_runtime(make_settings(tmp_path, youtube_test_url=url))


def test_test_url_is_announced(tmp_path):
    runtime = resolve_runtime(make_settings(tmp_path, youtube_test_url="http://127.0.0.1:5600/"))
    assert runtime.youtube_test_url == "http://127.0.0.1:5600"
    assert any("SERVER UJI" in w for w in runtime.warnings)


def test_real_endpoints_are_exact_google_hosts_and_allowed():
    ep = endpoints()
    guard = CostGuard.build(ollama_url="http://127.0.0.1:11434", extra_hosts=[], recorder=None)
    for url in (ep.auth, ep.token, ep.revoke, ep.data_api, ep.analytics_api):
        assert url.startswith("https://")
        assert guard.check(httpx.URL(url).host)[0] is True
    assert guard.check("generativelanguage.googleapis.com")[0] is False
    assert ep.is_test is False


def test_client_config_rules():
    config = parse_client_config(CLIENT_JSON)
    assert config.client_id.startswith("123-abc") and "GOCSPX" not in config.hint
    with pytest.raises(YouTubeError, match="Desktop app"):
        parse_client_config({"web": {"client_id": "a", "client_secret": "b"}})
    for bad in ([], {}, {"installed": {"client_id": "a"}},
                {"installed": {"client_id": "a" * 300, "client_secret": "b"}}):
        with pytest.raises(YouTubeError):
            parse_client_config(bad)


def test_auth_url_is_read_only_pkce_offline():
    verifier, challenge = new_pkce()
    assert len(verifier) >= 43 and verifier != challenge
    url = httpx.URL(build_auth_url(endpoints(), parse_client_config(CLIENT_JSON), "http://127.0.0.1:5555", "st",
                                   challenge))
    params = dict(url.params)
    assert url.host == "accounts.google.com"  # endpoint di file client diabaikan
    assert params["code_challenge_method"] == "S256" and params["access_type"] == "offline"
    assert params["redirect_uri"] == "http://127.0.0.1:5555" and params["response_type"] == "code"
    scopes = params["scope"].split()
    assert scopes == ["https://www.googleapis.com/auth/youtube.readonly",
                      "https://www.googleapis.com/auth/yt-analytics.readonly"]
    assert not any(word in params["scope"] for word in ("upload", "force-ssl", "youtubepartner", "monetary"))


def test_secret_store_file_fallback_is_reported_honestly(tmp_path):
    store = SecretStore(tmp_path, backend=None)
    assert store.kind == "file" and "tidak terenkripsi" in store.warning
    store.set("a", "nilai")
    assert store.get("a") == "nilai" and (tmp_path / "secrets" / "tokens.json").is_file()
    store.delete("a")
    assert store.get("a") is None and not (tmp_path / "secrets" / "tokens.json").exists()


def test_secret_store_prefers_keyring(tmp_path):
    class Ring:
        def __init__(self):
            self.items = {}

        def get_password(self, service, name):
            return self.items.get((service, name))

        def set_password(self, service, name, value):
            self.items[(service, name)] = value

        def delete_password(self, service, name):
            del self.items[(service, name)]

    ring = Ring()
    store = SecretStore(tmp_path, backend=ring)
    store.set("a", "nilai")
    assert store.kind == "keyring" and store.warning is None and ring.items == {(SERVICE, "a"): "nilai"}
    assert not (tmp_path / "secrets").exists()
    store.delete("a")
    store.delete("a")  # sudah tidak ada → tidak error
    assert store.get("a") is None


def test_quota_day_follows_pacific_time():
    assert quota_day(datetime(2026, 11, 15, 7, 59, tzinfo=UTC)) == "2026-11-14"
    assert quota_day(datetime(2026, 11, 15, 8, 0, tzinfo=UTC)) == "2026-11-15"
    assert next_reset(datetime(2026, 11, 15, 9, 0, tzinfo=UTC)) == datetime(2026, 11, 16, 8, 0, tzinfo=UTC)


def test_quota_tracker_stops_before_official_limit(client):
    tracker = QuotaTracker(client.app.state.zoi.db)
    tracker.charge(units=UNIT_LIMIT - 1)
    tracker.charge(units=1)
    with pytest.raises(QuotaExceeded):
        tracker.charge(units=1)
    status = tracker.status()
    assert status["units_used"] == UNIT_LIMIT == 9000 and status["units_official"] == 10_000
    assert "hitungan ZOI" in status["source"]


# ── alur lengkap ──────────────────────────────────────────────────────────
def test_initial_status_is_honest(yt):
    status = yt.get("/api/youtube/status").json()
    assert status["client_configured"] is False and status["connected"] is False and status["account"] is None
    assert status["test_endpoint"] is True and status["can_publish"] is False
    assert status["quota"]["units_used"] == 0
    data = yt.get("/api/youtube/data").json()
    assert data["channel"] is None and data["videos"] is None and data["analytics"] is None and data["history"] == []
    assert "SERVER UJI" in data["source"]
    assert yt.post("/api/youtube/connect").status_code == 409
    assert yt.post("/api/youtube/refresh", json={}).json()["error"]["code"] == "not_connected"


def test_connect_refresh_and_read(yt, google):
    status = connect(yt)
    account = status["account"]
    assert account["channel_id"] == CHANNEL_ID and account["title"] == "Channel Uji ZOI"
    assert account["analytics_granted"] is True and account["needs_reauth"] is False
    assert status["token_storage"] == "file" and status["storage_warning"]  # workspace Linux: tanpa keyring
    token_form = next(r["form"] for r in google.requests if r["path"] == "/token")
    assert token_form["grant_type"] == "authorization_code" and len(token_form["code_verifier"]) >= 43
    assert token_form["redirect_uri"].startswith("http://127.0.0.1:")

    data = yt.post("/api/youtube/refresh", json={"what": "all"}).json()
    channel = data["channel"]["payload"]
    assert channel["subscriber_count"] == 1530 and channel["view_count"] == 45210 and channel["video_count"] == 37
    assert data["channel"]["fetched_at"]
    videos = data["videos"]["payload"]
    assert [v["title"] for v in videos] == ["Video uji pertama", "Video uji kedua", "Draf pribadi"]
    assert videos[0]["view_count"] == 1200 and videos[2]["privacy"] == "private"
    analytics = data["analytics"]["payload"]
    assert analytics["last_28_days"]["rows"][0]["views"] == 28 * 110
    assert len(analytics["daily"]["rows"]) == 28 and analytics["daily"]["columns"][0] == "day"
    assert analytics["last_365_days"]["rows"][0]["estimatedMinutesWatched"] == 365 * 330
    assert len(data["history"]) == 1 and data["history"][0]["subscriber_count"] == 1530
    # 1 unit saat menghubungkan + channel/playlistItems/videos; laporan Analytics dihitung terpisah.
    assert data["quota"]["units_used"] == 4 and data["quota"]["analytics_calls"] == 7
    by_video = analytics["by_video"]
    assert by_video["columns"] == ["video", "views", "estimatedMinutesWatched", "averageViewDuration",
                                   "averageViewPercentage"]
    assert by_video["rows"][0] == {"video": "vidAAAAAAA1", "views": 900, "estimatedMinutesWatched": 2700,
                                   "averageViewDuration": 180, "averageViewPercentage": 42.5}
    assert data["ypp"]["tiers"][1]["requirements"][0] == "1.000 subscriber"


def test_no_derived_metrics_and_no_secrets_in_responses(yt, google):
    connect(yt)
    data = yt.post("/api/youtube/refresh", json={}).json()
    text = json.dumps([data, yt.get("/api/youtube/status").json()]).lower()
    for secret in ("gocspx", "rt-", "at-", "client_secret", "refresh_token"):
        assert secret not in text
    for derived in ("progress", "percent", "persen", "score", "skor", "remaining", "kurang"):
        # averageViewPercentage adalah metrik milik YouTube sendiri (bukan hitungan ZOI) → nama kolomnya dikecualikan.
        shown = json.dumps({k: data[k] for k in ("channel", "videos", "analytics", "history")}).lower()
        assert derived not in shown.replace("averageviewpercentage", "")


def test_token_lives_only_in_secret_store(yt, google, tmp_path):
    connect(yt)
    data_dir = tmp_path / "data"
    tokens = json.loads((data_dir / "secrets" / "tokens.json").read_text())
    assert tokens[TOKEN_NAME] in google.refresh_tokens
    db_bytes = (data_dir / "zoi.db").read_bytes()
    for wal in data_dir.glob("zoi.db-wal"):
        db_bytes += wal.read_bytes()
    assert tokens[TOKEN_NAME].encode() not in db_bytes and b"GOCSPX" not in db_bytes
    logs = "".join(p.read_text(errors="ignore") for p in (data_dir / "logs").glob("*"))
    assert tokens[TOKEN_NAME] not in logs and "GOCSPX" not in logs


def test_export_never_contains_secrets(yt, tmp_path):
    from app.db.portability import export_data

    connect(yt)
    archive = export_data(tmp_path / "data", tmp_path / "out.zip")
    names = zipfile.ZipFile(archive.path).namelist()
    assert names and not any("secrets" in n or "tokens" in n or "youtube_client" in n for n in names)


def test_access_token_is_renewed_transparently(yt, google):
    connect(yt)
    google.expire_access_tokens()
    yt.app.state.zoi.youtube._access = ("at-kedaluwarsa", 1e18)  # token di memori yang ditolak YouTube → 401 → perbarui
    data = yt.post("/api/youtube/refresh", json={"what": "channel"}).json()
    assert data["channel"]["payload"]["title"] == "Channel Uji ZOI"
    assert any(r["form"].get("grant_type") == "refresh_token" for r in google.requests)


def test_user_denies_consent(yt, google):
    google.deny = True
    status = connect(yt, expect_connected=False)
    assert "menolak izin" in status["last_error"] and status["account"] is None
    assert google.count("/token") == 0


def test_state_mismatch_is_rejected(yt, google):
    yt.put("/api/youtube/client", json={"config": CLIENT_JSON})
    started = yt.post("/api/youtube/connect").json()
    redirect = dict(httpx.URL(started["auth_url"]).params)["redirect_uri"]
    httpx.get(f"{redirect}/?code=curian&state=salah", timeout=5)
    status = wait_for(lambda: (s := yt.get("/api/youtube/status").json())["pending"] is False and s)
    assert status["connected"] is False and "state berbeda" in status["last_error"]
    assert google.count("/token") == 0
    # Pendengar sekali pakai: sudah ditutup setelah satu jawaban.
    with pytest.raises(httpx.HTTPError):
        httpx.get(f"{redirect}/?code=lagi&state=salah", timeout=2)


def test_loopback_ignores_unrelated_requests(yt, google):
    yt.put("/api/youtube/client", json={"config": CLIENT_JSON})
    started = yt.post("/api/youtube/connect").json()
    redirect = dict(httpx.URL(started["auth_url"]).params)["redirect_uri"]
    assert httpx.get(f"{redirect}/favicon.ico", timeout=5).status_code == 404
    assert yt.get("/api/youtube/status").json()["pending"] is True
    assert browser(started["auth_url"]).status_code == 200
    wait_for(lambda: yt.get("/api/youtube/status").json()["connected"])


@pytest.mark.parametrize(("switch", "value", "message"), [
    ("no_refresh_token", True, "refresh token"),
    ("granted_scope", "https://www.googleapis.com/auth/yt-analytics.readonly", "youtube.readonly"),
    ("no_channel", True, "tidak punya channel"),
])
def test_connect_failures_leave_nothing_behind(yt, google, tmp_path, switch, value, message):
    setattr(google, switch, value)
    status = connect(yt, expect_connected=False)
    assert message in status["last_error"]
    assert not (tmp_path / "data" / "secrets" / "tokens.json").exists()
    assert yt.get("/api/youtube/data").json()["channel"] is None


def test_analytics_scope_not_granted_is_reported(yt, google):
    google.granted_scope = "https://www.googleapis.com/auth/youtube.readonly"
    status = connect(yt)
    assert status["account"]["analytics_granted"] is False
    data = yt.post("/api/youtube/refresh", json={}).json()
    assert "Izin YouTube Analytics tidak diberikan" in data["analytics"]["payload"]["error"]
    assert google.count("/v2/reports") == 0 and data["channel"]["payload"]["subscriber_count"] == 1530


def test_dashboard_breakdowns(yt, google):
    connect(yt)
    payload = yt.post("/api/youtube/refresh", json={}).json()["analytics"]["payload"]
    assert payload["traffic_sources"]["rows"][0] == {"insightTrafficSourceType": "YT_SEARCH", "views": 500}
    assert payload["devices"]["rows"][0] == {"deviceType": "MOBILE", "views": 700}
    prev = payload["previous_28_days"]
    assert prev["end"] < payload["last_28_days"]["start"] and "breakdown_error" not in payload


def test_analytics_failure_does_not_hide_channel_data(yt, google):
    connect(yt)
    google.analytics_forbidden = True
    data = yt.post("/api/youtube/refresh", json={}).json()
    assert "403" in data["analytics"]["payload"]["error"] and "last_28_days" not in data["analytics"]["payload"]
    assert data["channel"]["payload"]["view_count"] == 45210


def test_cancel_pending_connect(yt):
    yt.put("/api/youtube/client", json={"config": CLIENT_JSON})
    started = yt.post("/api/youtube/connect").json()
    assert yt.get("/api/youtube/status").json()["pending"] is True
    assert yt.post("/api/youtube/connect/cancel").status_code == 204
    assert yt.get("/api/youtube/status").json()["pending"] is False
    redirect = dict(httpx.URL(started["auth_url"]).params)["redirect_uri"]
    with pytest.raises(httpx.HTTPError):
        httpx.get(f"{redirect}/?code=x&state=y", timeout=2)


def test_connect_times_out(client_factory, google, monkeypatch):
    client = client_factory(youtube_test_url=google.url)
    client.app.state.zoi.youtube.connect_timeout_s = 0.2
    client.put("/api/youtube/client", json={"config": CLIENT_JSON})
    client.post("/api/youtube/connect")
    status = wait_for(lambda: (s := client.get("/api/youtube/status").json())["pending"] is False and s)
    assert "Waktu habis" in status["last_error"]


def test_revoked_grant_needs_reauth(yt, google):
    connect(yt)
    google.revoke_all()
    yt.app.state.zoi.youtube._access = None
    response = yt.post("/api/youtube/refresh", json={"what": "channel"})
    assert response.status_code == 409 and response.json()["error"]["code"] == "needs_reauth"
    assert yt.get("/api/youtube/status").json()["account"]["needs_reauth"] is True


def test_youtube_quota_error_is_reported(yt, google):
    connect(yt)
    google.quota_exceeded = True
    response = yt.post("/api/youtube/refresh", json={"what": "channel"})
    assert response.status_code == 429 and response.json()["error"]["code"] == "quota_exceeded"


def test_local_quota_limit_blocks_before_sending(yt, google):
    connect(yt)
    with yt.app.state.zoi.db.session() as s:
        s.get(YouTubeQuota, quota_day()).units = UNIT_LIMIT
    before = google.count("/youtube/v3/channels")
    response = yt.post("/api/youtube/refresh", json={"what": "channel"})
    assert response.status_code == 429 and "Batas aman" in response.json()["error"]["message"]
    assert google.count("/youtube/v3/channels") == before


def test_client_file_rules(yt):
    web = {"web": {"client_id": "a", "client_secret": "b"}}
    assert yt.put("/api/youtube/client", json={"config": web}).status_code == 400
    hint = yt.put("/api/youtube/client", json={"config": CLIENT_JSON}).json()["client_id_hint"]
    assert hint.endswith("apps.googleusercontent.com")
    assert hint == yt.get("/api/youtube/status").json()["client_id_hint"]
    assert yt.delete("/api/youtube/client").status_code == 204
    assert yt.get("/api/youtube/status").json()["client_configured"] is False
    connect(yt)
    assert yt.put("/api/youtube/client", json={"config": CLIENT_JSON}).status_code == 409
    assert yt.delete("/api/youtube/client").status_code == 409
    assert yt.post("/api/youtube/connect").status_code == 409


def test_real_mode_requires_google_client_id(client):
    bad = {"installed": {"client_id": "bukan-google", "client_secret": "x"}}
    response = client.put("/api/youtube/client", json={"config": bad})
    assert response.status_code == 400 and "apps.googleusercontent.com" in response.json()["error"]["message"]
    assert client.get("/api/youtube/status").json()["test_endpoint"] is False


def test_disconnect_revokes_and_deletes_everything(yt, google, tmp_path):
    connect(yt)
    yt.post("/api/youtube/refresh", json={})
    result = yt.post("/api/youtube/disconnect").json()
    assert result["revoked_at_google"] is True and result["note"] is None
    assert google.revoked == google.refresh_tokens
    status = yt.get("/api/youtube/status").json()
    assert status["connected"] is False and status["client_configured"] is True
    data = yt.get("/api/youtube/data").json()
    assert data["channel"] is None and data["videos"] is None and data["analytics"] is None and data["history"] == []
    assert not (tmp_path / "data" / "secrets" / "tokens.json").exists()
    assert yt.post("/api/youtube/refresh", json={}).status_code == 409


def test_disconnect_when_google_unreachable_still_deletes_locally(yt, google, tmp_path):
    connect(yt)
    google.stop()
    result = yt.post("/api/youtube/disconnect").json()
    assert result["revoked_at_google"] is False and "myaccount.google.com" in result["note"]
    assert yt.get("/api/youtube/status").json()["connected"] is False
    assert not (tmp_path / "data" / "secrets" / "tokens.json").exists()


def test_unverified_data_is_purged_after_30_days(yt, google):
    connect(yt)
    yt.post("/api/youtube/refresh", json={})
    service = yt.app.state.zoi.youtube
    account = service.account()
    service._save_account({**account, "verified_at": (datetime.now(UTC) - timedelta(days=31)).isoformat()})
    data = yt.get("/api/youtube/data").json()
    assert data["purged_unverified"] is True and data["connected"] is True
    assert data["channel"] is None and data["history"] == [] and data["analytics"] is None
    restored = yt.post("/api/youtube/refresh", json={"what": "channel"}).json()
    assert restored["channel"]["payload"]["title"] == "Channel Uji ZOI" and restored["purged_unverified"] is False
    assert datetime.fromisoformat(service.account()["verified_at"]) > datetime.now(UTC) - timedelta(minutes=1)


def test_data_within_30_days_is_kept(yt, google):
    connect(yt)
    service = yt.app.state.zoi.youtube
    service._save_account({**service.account(), "verified_at": (datetime.now(UTC) - timedelta(days=29)).isoformat()})
    assert yt.get("/api/youtube/data").json()["channel"] is not None


def test_snapshot_is_one_row_per_day(yt, google):
    connect(yt)
    google.subscribers = "1544"
    data = yt.post("/api/youtube/refresh", json={"what": "channel"}).json()
    assert len(data["history"]) == 1 and data["history"][0]["subscriber_count"] == 1544


def test_events_announce_changes(yt, google):
    with yt.websocket_connect("ws://127.0.0.1/ws") as ws:
        connect(yt)
        seen = set()
        for _ in range(40):
            event = ws.receive_json()
            seen.add(event["type"])
            if "youtube.updated" in seen:
                break
        assert "youtube.updated" in seen


def test_writes_require_client_header(yt):
    response = yt.post("/api/youtube/disconnect", headers={"X-ZOI-Client": ""})
    assert response.status_code == 403


def test_agent_tools_are_read_only_and_ask_permission(yt, google):
    tools = {t["name"]: t for t in yt.get("/api/agent/status").json()["tools"]}
    assert tools["youtube_channel_saya"]["permission"] == Permission.EXTERNAL.value
    assert tools["youtube_video_saya"]["permission"] == Permission.EXTERNAL.value
    assert tools["youtube_kuota"]["permission"] == Permission.READ.value
    assert not [n for n in tools if n.startswith("youtube_") and n not in
                ("youtube_channel_saya", "youtube_video_saya", "youtube_kuota")]


def test_restored_backup_without_token_asks_to_reconnect(yt, google):
    connect(yt)
    yt.app.state.zoi.youtube.store.delete(TOKEN_NAME)  # seperti data dipulihkan di komputer lain
    yt.app.state.zoi.youtube._access = None
    status = yt.get("/api/youtube/status").json()
    assert status["connected"] is True and status["account"]["needs_reauth"] is True
    response = yt.post("/api/youtube/refresh", json={"what": "channel"})
    assert response.status_code == 409 and response.json()["error"]["code"] == "needs_reauth"
    assert yt.post("/api/youtube/disconnect").json()["revoked_at_google"] is False


def test_account_meta_is_not_secret(yt, google):
    connect(yt)
    account = yt.app.state.zoi.youtube.account()
    assert set(account) == {"channel_id", "title", "custom_url", "connected_at", "verified_at", "scopes",
                            "analytics_granted", "needs_reauth"}
    assert ACCOUNT_KEY == "youtube_account"


# ── agen ──────────────────────────────────────────────────────────────────
def _plan(client, request: str) -> dict:
    run_id = client.post("/api/agent/plan", json={"request": request}).json()["run"]["id"]
    return wait_for(lambda: (r := client.get(f"/api/agent/runs/{run_id}").json())["status"] != "planning" and r)


def _wait(client, run_id: str, statuses: set[str]) -> dict:
    return wait_for(lambda: (r := client.get(f"/api/agent/runs/{run_id}").json())["status"] in statuses and r)


def test_agent_reads_channel_only_after_approval(yt, google):
    connect(yt)
    before = google.count("/youtube/v3/channels")
    run = _plan(yt, "cek channel youtube saya")
    assert [(s["tool"], s["permission"]) for s in run["plan"]["langkah"]] == [
        ("youtube_kuota", "read"), ("youtube_channel_saya", "external")]
    yt.post(f"/api/agent/runs/{run['id']}/approve")
    waiting = _wait(yt, run["id"], {"waiting_approval"})
    pending = [a for a in waiting["approvals"] if a["status"] == "pending"]
    assert pending[0]["tool"] == "youtube_channel_saya" and google.count("/youtube/v3/channels") == before
    # Tool external tidak bisa dijadikan otomatis.
    assert yt.put("/api/agent/tools/youtube_channel_saya/permission", json={"mode": "auto"}).status_code == 400
    yt.post(f"/api/agent/approvals/{pending[0]['id']}", json={"decision": "approve"})
    done = _wait(yt, run["id"], {"completed"})
    assert google.count("/youtube/v3/channels") == before + 1
    result = done["results"][1]
    assert result["status"] == "ok" and "SERVER UJI" in json.dumps(result, ensure_ascii=False)


def test_agent_tool_reports_not_connected(yt, google):
    run = _plan(yt, "cek channel youtube saya")
    yt.post(f"/api/agent/runs/{run['id']}/approve")
    waiting = _wait(yt, run["id"], {"waiting_approval"})
    pending = next(a for a in waiting["approvals"] if a["status"] == "pending")
    yt.post(f"/api/agent/approvals/{pending['id']}", json={"decision": "approve"})
    done = _wait(yt, run["id"], {"completed", "failed"})
    assert done["results"][1]["status"] != "ok" and "belum terhubung" in json.dumps(done, ensure_ascii=False)
    assert google.requests == []
