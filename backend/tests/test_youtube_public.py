"""Phase 6B — data publik YouTube (≤30 hari, tanpa skor), rangkuman tema, ide & naskah oleh AI lokal.

Google TIRUAN (tests/fake_google.py). AI: Mock (development) dan Ollama tiruan (local).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.content.service import IdeaRequest, RangkumanTema, Tema
from app.db.models import YouTubePublicCache, YouTubeQuota
from app.youtube.errors import YouTubeError
from app.youtube.public import MAX_WATCHLIST, RETENTION_DAYS, parse_channel_ref
from app.youtube.quota import SEARCH_LIMIT, quota_day
from tests.conftest import wait_task as _wait_task
from tests.fake_google import OTHER_ID, FakeGoogle
from tests.test_youtube import connect

P = "/api/youtube/public"


def wait_task(client, task_id: str) -> dict:
    return _wait_task(client, task_id, {"COMPLETED", "FAILED", "CANCELLED"})


@pytest.fixture
def google():
    fake = FakeGoogle()
    fake.url = fake.start()
    yield fake
    fake.stop()


@pytest.fixture
def yt(client_factory, google):
    client = client_factory(youtube_test_url=google.url)
    connect(client)
    return client


def age(client, key: str, days: int) -> None:
    with client.app.state.zoi.db.session() as s:
        s.get(YouTubePublicCache, key).fetched_at = datetime.now(UTC) - timedelta(days=days)


# ── unit ──────────────────────────────────────────────────────────────────
@pytest.mark.parametrize(("text", "expected"), [
    ("@kopilain", ("forHandle", "@kopilain")),
    ("https://www.youtube.com/@kopilain/videos", ("forHandle", "@kopilain")),
    (OTHER_ID, ("id", OTHER_ID)),
    (f"https://youtube.com/channel/{OTHER_ID}?x=1", ("id", OTHER_ID)),
])
def test_channel_reference_forms(text, expected):
    assert parse_channel_ref(text) == expected


@pytest.mark.parametrize("text", ["kopi lain", "https://example.com", "@a", "x" * 400])
def test_channel_reference_rejects_other_text(text):
    with pytest.raises(YouTubeError):
        parse_channel_ref(text)


# ── channel pantauan ──────────────────────────────────────────────────────
def test_requires_connection(client_factory, google):
    client = client_factory(youtube_test_url=google.url)
    assert client.get(f"{P}/competitors").json()["connected"] is False
    response = client.post(f"{P}/competitors", json={"ref": "@kopilain"})
    assert response.status_code == 409 and response.json()["error"]["code"] == "not_connected"
    assert client.post(f"{P}/trending", json={}).status_code == 409
    assert client.post(f"{P}/search", json={"query": "kopi"}).status_code == 409
    assert google.requests == []


def test_competitor_add_refresh_remove(yt, google):
    used = yt.get("/api/youtube/status").json()["quota"]["units_used"]
    data = yt.post(f"{P}/competitors", json={"ref": "https://youtube.com/@kopilain", "note": "pesaing kopi"}).json()
    item = data["items"][0]
    assert item["channel_id"] == OTHER_ID and item["note"] == "pesaing kopi"
    channel = item["data"]["payload"]["channel"]
    assert channel["title"] == "Kopi Lain" and channel["subscriber_count"] == 12400
    assert item["data"]["payload"]["videos"] is None
    expires = datetime.fromisoformat(item["data"]["expires_at"]) - datetime.fromisoformat(item["data"]["fetched_at"])
    assert expires == timedelta(days=30) == timedelta(days=RETENTION_DAYS)

    data = yt.post(f"{P}/competitors/{OTHER_ID}/refresh").json()
    videos = data["items"][0]["data"]["payload"]["videos"]
    assert [v["title"] for v in videos] == ["Resep kopi susu gula aren", "Review grinder kopi murah"]
    assert videos[0]["view_count"] == 90100
    assert data["quota"]["units_used"] == used + 4  # tambah: 1 unit; segarkan: channel + playlistItems + videos
    assert "SERVER UJI" in data["source"]

    # Menambah channel yang sama dua kali tidak menggandakan.
    assert len(yt.post(f"{P}/competitors", json={"ref": OTHER_ID}).json()["items"]) == 1
    assert yt.delete(f"{P}/competitors/{OTHER_ID}").json()["items"] == []
    assert yt.delete(f"{P}/competitors/{OTHER_ID}").status_code == 404
    with yt.app.state.zoi.db.session() as s:
        assert s.get(YouTubePublicCache, f"competitor:{OTHER_ID}") is None


def test_competitor_history_cache_and_channel_search(yt, google):
    found = yt.post(f"{P}/channels/search", json={"query": "kopi"}).json()["items"]
    assert [c["id"] for c in found] == [OTHER_ID] and found[0]["subscriber_count"] == 12400
    assert yt.post(f"{P}/channels/search", json={"query": "tidakada"}).json()["items"] == []

    yt.post(f"{P}/competitors", json={"ref": OTHER_ID})
    yt.post(f"{P}/competitors/{OTHER_ID}/refresh")
    calls = google.count("/youtube/v3/playlistItems")
    data = yt.post(f"{P}/competitors/{OTHER_ID}/refresh").json()  # <1 jam → cache, tanpa panggilan API
    assert google.count("/youtube/v3/playlistItems") == calls
    yt.post(f"{P}/competitors/{OTHER_ID}/refresh?force=true")
    assert google.count("/youtube/v3/playlistItems") == calls + 1
    history = data["items"][0]["history"]
    assert len(history) == 1 and history[0]["subscriber_count"] == 12400  # satu titik per hari, tidak dikarang
    yt.delete(f"{P}/competitors/{OTHER_ID}")
    with yt.app.state.zoi.db.session() as s:
        assert not s.scalars(select(YouTubePublicCache).where(YouTubePublicCache.kind == "competitor_snapshot")).all()


def test_competitor_not_found_and_bad_input(yt):
    assert yt.post(f"{P}/competitors", json={"ref": "@tidakada"}).status_code == 404
    assert yt.post(f"{P}/competitors", json={"ref": "bukan channel"}).status_code == 400
    assert yt.post(f"{P}/competitors/UCxxxxxxxxxxxxxxxxxxxxxx/refresh").status_code == 404
    assert yt.get(f"{P}/competitors").json()["items"] == []


def test_watchlist_is_capped(yt):
    from app.db.models import YouTubeWatch
    with yt.app.state.zoi.db.session() as s:
        for i in range(MAX_WATCHLIST):
            s.add(YouTubeWatch(channel_id=f"UC{i:022d}", note=""))
    response = yt.post(f"{P}/competitors", json={"ref": "@kopilain"})
    assert response.status_code == 409 and "penuh" in response.json()["error"]["message"]


def test_no_scores_or_derived_fields_for_public_data(yt):
    yt.post(f"{P}/competitors", json={"ref": "@kopilain"})
    yt.post(f"{P}/competitors/{OTHER_ID}/refresh")
    yt.post(f"{P}/trending", json={})
    text = json.dumps([yt.get(f"{P}/competitors").json()["items"], yt.get(f"{P}/viral").json()["trending"]]).lower()
    for word in ("score", "skor", "rank", "peringkat", "engagement", "rate", "growth", "velocity", "viral", "percent"):
        assert word not in text


# ── penyimpanan ≤30 hari ──────────────────────────────────────────────────
def test_public_data_expires_after_30_days(yt):
    yt.post(f"{P}/competitors", json={"ref": "@kopilain"})
    yt.post(f"{P}/trending", json={})
    age(yt, f"competitor:{OTHER_ID}", 29)
    age(yt, "trending:ID:all", 31)
    viral = yt.get(f"{P}/viral").json()
    assert viral["trending"] == [] and viral["retention_days"] == 30
    kept = yt.get(f"{P}/competitors").json()["items"][0]
    assert kept["data"] is not None
    age(yt, f"competitor:{OTHER_ID}", 31)
    gone = yt.get(f"{P}/competitors").json()["items"][0]
    assert gone["channel_id"] == OTHER_ID and gone["data"] is None  # hanya ID & catatan pengguna yang tersisa


def test_expired_rows_are_purged_at_startup(client_factory, google, tmp_path):
    first = client_factory(youtube_test_url=google.url)
    connect(first)
    first.post(f"{P}/trending", json={})
    age(first, "trending:ID:all", 40)
    second = client_factory(youtube_test_url=google.url)
    with second.app.state.zoi.db.session() as s:
        assert s.get(YouTubePublicCache, "trending:ID:all") is None


def test_disconnect_deletes_public_data_and_watchlist(yt):
    yt.post(f"{P}/competitors", json={"ref": "@kopilain"})
    yt.post(f"{P}/trending", json={})
    yt.post(f"{P}/search", json={"query": "kopi"})
    yt.post("/api/youtube/disconnect")
    assert yt.get(f"{P}/competitors").json()["items"] == []
    viral = yt.get(f"{P}/viral").json()
    assert viral["trending"] == [] and viral["searches"] == [] and viral["categories"] is None


# ── Trending resmi & pencarian ────────────────────────────────────────────
def test_trending_keeps_youtube_order(yt, google):
    viral = yt.post(f"{P}/trending", json={}).json()
    entry = viral["trending"][0]
    assert entry["key"] == "trending:ID:all"
    assert [v["title"] for v in entry["payload"]["items"]] == [
        "Cara seduh kopi V60 untuk pemula", "Resep kopi susu ala kafe", "Highlight final bulu tangkis",
        "Tips belajar coding dari nol"]
    assert entry["payload"]["items"][0]["view_count"] == 500000 and entry["payload"]["items"][0]["channel_title"]
    # Kategori resmi (hanya yang assignable), diambil sekali.
    assert [c["title"] for c in viral["categories"]["payload"]] == ["Olahraga", "Cara & Gaya", "Pendidikan"]
    sent = next(r["query"] for r in google.requests if r["query"].get("chart") == "mostPopular")
    assert sent["regionCode"] == "ID"

    viral = yt.post(f"{P}/trending", json={"category_id": "26"}).json()
    by_key = {e["key"]: e for e in viral["trending"]}
    assert len(by_key["trending:ID:26"]["payload"]["items"]) == 2 and "trending:ID:all" in by_key
    assert google.count("/youtube/v3/videoCategories") == 1
    assert yt.post(f"{P}/trending", json={"category_id": "x1"}).status_code == 400


def test_search_uses_its_own_quota_bucket(yt, google):
    before = yt.get("/api/youtube/status").json()["quota"]
    viral = yt.post(f"{P}/search", json={"query": "  Kopi   susu "}).json()
    entry = viral["searches"][0]
    assert entry["payload"]["query"] == "Kopi susu"
    assert [v["title"] for v in entry["payload"]["items"]] == ["Cara seduh kopi V60 untuk pemula",
                                                                "Resep kopi susu ala kafe"]
    assert entry["payload"]["items"][0]["view_count"] is None  # search.list tidak mengirim statistik → tidak dikarang
    assert viral["quota"]["search_used"] == before["search_used"] + 1
    assert viral["quota"]["units_used"] == before["units_used"]
    # Kata kunci yang sama menimpa hasil lama, bukan menumpuk.
    assert len(yt.post(f"{P}/search", json={"query": "kopi susu"}).json()["searches"]) == 1
    assert yt.post(f"{P}/search", json={"query": "k"}).status_code == 422


def test_search_stops_at_safe_limit(yt, google):
    with yt.app.state.zoi.db.session() as s:
        s.get(YouTubeQuota, quota_day()).search_calls = SEARCH_LIMIT
    response = yt.post(f"{P}/search", json={"query": "kopi"})
    assert response.status_code == 429 and "pencarian" in response.json()["error"]["message"]
    assert google.count("/youtube/v3/search") == 0
    assert yt.post(f"{P}/trending", json={}).status_code == 200  # ember umum tidak terpengaruh


def test_remove_list(yt):
    yt.post(f"{P}/trending", json={})
    assert yt.post(f"{P}/lists/remove", json={"key": "trending:ID:all"}).json()["trending"] == []
    assert yt.post(f"{P}/lists/remove", json={"key": "competitor:x"}).status_code == 404


# ── rangkuman tema ────────────────────────────────────────────────────────
def test_themes_with_mock_are_labelled(yt):
    yt.post(f"{P}/trending", json={})
    task = wait_task(yt, yt.post(f"{P}/themes", json={"key": "trending:ID:all"}).json()["id"])
    assert task["status"] == "COMPLETED", task
    entry = yt.get(f"{P}/viral").json()["themes"][0]
    assert entry["key"] == "themes:trending:ID:all"
    payload = entry["payload"]
    assert payload["is_mock"] is True and payload["themes"][0]["nama"].startswith("[MOCK]")
    assert payload["titles_read"] == 4 and "bukan statistik" in payload["label"]
    assert payload["themes"][0]["contoh_judul"] == ["Cara seduh kopi V60 untuk pemula", "Resep kopi susu ala kafe"]
    assert "expires_at" in entry  # ikut aturan ≤30 hari


def test_themes_need_existing_list(yt):
    assert yt.post(f"{P}/themes", json={"key": "trending:ID:all"}).status_code == 404
    assert yt.post(f"{P}/themes", json={"key": "competitor:abc"}).status_code == 404


def test_theme_examples_not_in_list_are_dropped(yt, monkeypatch):
    yt.post(f"{P}/trending", json={})
    content = yt.app.state.zoi.content

    async def fake_ask(messages, schema):
        assert "Highlight final bulu tangkis" in messages[-1].content and "DATA" in messages[-1].content
        assert "500000" not in "".join(m.content for m in messages)  # AI hanya menerima judul, bukan angka
        return RangkumanTema(tema=[Tema(nama="Kopi", penjelasan="Video tentang kopi.",
                                        contoh_judul=["resep kopi susu ala kafe ", "Judul karangan AI"])])

    monkeypatch.setattr(content, "_ask", fake_ask)
    monkeypatch.setattr(type(content.provider), "is_mock", False)
    task = wait_task(yt, yt.post(f"{P}/themes", json={"key": "trending:ID:all"}).json()["id"])
    assert task["status"] == "COMPLETED", task
    theme = yt.get(f"{P}/viral").json()["themes"][0]["payload"]["themes"][0]
    assert theme["contoh_judul"] == ["Resep kopi susu ala kafe"] and theme["contoh_dibuang"] == 1


def test_themes_are_removed_with_their_list(yt):
    yt.post(f"{P}/trending", json={})
    wait_task(yt, yt.post(f"{P}/themes", json={"key": "trending:ID:all"}).json()["id"])
    assert yt.post(f"{P}/lists/remove", json={"key": "trending:ID:all"}).json()["themes"] == []


# ── ide & naskah ──────────────────────────────────────────────────────────
def test_ideas_with_mock_are_labelled_and_saved(client):
    started = client.post("/api/content/ideas", json={"topik": "kopi rumahan", "jumlah": 2}).json()
    task = wait_task(client, started["id"])
    assert task["status"] == "COMPLETED", task
    listing = client.get("/api/content/items?kind=ideas").json()
    item = listing["items"][0]
    assert listing["is_mock"] is True and item["is_mock"] is True and item["provider"] == "mock"
    assert len(item["payload"]["ide"]) == 2 and all(i["judul"].startswith("[MOCK]") for i in item["payload"]["ide"])
    assert item["request"]["topik"] == "kopi rumahan" and item["id"] == task["result"]["item_id"]
    assert client.delete(f"/api/content/items/{item['id']}").status_code == 204
    assert client.delete(f"/api/content/items/{item['id']}").status_code == 404
    assert client.get("/api/content/items?kind=ideas").json()["items"] == []


def test_script_with_mock(client):
    task = wait_task(client, client.post("/api/content/scripts",
                                         json={"judul": "Cara seduh kopi", "format": "shorts"}).json()["id"])
    assert task["status"] == "COMPLETED", task
    item = client.get("/api/content/items?kind=script").json()["items"][0]
    assert item["title"] == "Cara seduh kopi" and item["payload"]["bagian"][0]["narasi"].startswith("[MOCK]")
    assert client.get("/api/content/items?kind=ideas").json()["items"] == []


@pytest.mark.parametrize(("path", "body"), [
    ("/api/content/ideas", {"topik": "ab"}), ("/api/content/ideas", {"topik": "kopi", "jumlah": 9}),
    ("/api/content/ideas", {"topik": "kopi", "publish": True}), ("/api/content/scripts", {"judul": "x"}),
])
def test_content_input_is_validated(client, path, body):
    assert client.post(path, json=body).status_code == 422


def test_ideas_context_is_marked_as_data(yt, monkeypatch):
    yt.post("/api/youtube/refresh", json={"what": "videos"})
    yt.post("/api/memories", json={"content": "Channel fokus ke kopi nusantara", "kind": "fakta"})
    content = yt.app.state.zoi.content
    seen: list[str] = []

    async def fake_ask(messages, schema):
        seen.extend(m.content for m in messages)
        return schema.model_validate({"ide": [{"judul": "Kopi tubruk", "hook": "h", "garis_besar": "g", "cta": ""}]})

    monkeypatch.setattr(content, "_ask", fake_ask)
    monkeypatch.setattr(type(content.provider), "is_mock", False)
    task = wait_task(yt, yt.post("/api/content/ideas", json={"topik": "kopi nusantara"}).json()["id"])
    assert task["status"] == "COMPLETED", task
    joined = "\n".join(seen)
    assert "Video uji pertama" in joined and "kopi nusantara" in joined and "BUKAN instruksi" in joined
    assert "1200" not in joined  # angka channel tidak dikirim ke AI
    item = yt.get("/api/content/items?kind=ideas").json()["items"][0]
    assert item["is_mock"] is False and item["payload"]["ide"][0]["judul"] == "Kopi tubruk"


def test_empty_ai_result_fails_honestly(client, monkeypatch):
    content = client.app.state.zoi.content

    async def fake_ask(messages, schema):
        return schema.model_validate({"ide": []})

    monkeypatch.setattr(content, "_ask", fake_ask)
    monkeypatch.setattr(type(content.provider), "is_mock", False)
    task = wait_task(client, client.post("/api/content/ideas", json={"topik": "kopi"}).json()["id"])
    assert task["status"] == "FAILED" and "tidak menghasilkan ide" in task["error"]
    assert client.get("/api/content/items?kind=ideas").json()["items"] == []


def test_idea_request_schema_has_no_publish_fields():
    assert set(IdeaRequest.model_fields) == {"topik", "format", "jumlah", "pakai_channel", "tema_key"}


# ── laporan per video (channel sendiri) ───────────────────────────────────
def test_by_video_report_failure_keeps_other_reports(yt, google):
    google.by_video_forbidden = True
    data = yt.post("/api/youtube/refresh", json={"what": "analytics"}).json()
    payload = data["analytics"]["payload"]
    assert "403" in payload["by_video_error"] and "by_video" not in payload and "last_28_days" in payload
