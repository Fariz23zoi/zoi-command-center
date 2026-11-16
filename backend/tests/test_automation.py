"""Phase 8 — otomatisasi terjadwal, susulan, bangun via GitHub Actions, notifikasi di dalam ZOI."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.automation.schedule import WIB, Schedule
from app.db.models import Automation
from tests import fake_google
from tests.conftest import wait_for
from tests.fake_google import OTHER_ID, FakeGoogle
from tests.test_youtube import connect

WAKE = "w" * 32


def _done(client, task_id):
    return wait_for(lambda: (t := client.get(f"/api/tasks/{task_id}").json())["status"] in
                    {"COMPLETED", "FAILED", "CANCELLED"} and t, timeout=20)


def _make_due(client, automation_id, minutes_ago):
    with client.app.state.zoi.db.session() as s:
        s.get(Automation, automation_id).next_due_at = datetime.now(UTC) - timedelta(minutes=minutes_ago)


# ── jadwal ────────────────────────────────────────────────────────────────
def test_schedule_next_after_in_wib():
    daily = Schedule(frequency="daily", hour=7, minute=30)
    at = datetime(2026, 11, 16, 7, 0, tzinfo=WIB)  # Senin 07.00 WIB
    assert daily.next_after(at) == datetime(2026, 11, 16, 7, 30, tzinfo=WIB).astimezone(UTC)
    assert daily.next_after(datetime(2026, 11, 16, 8, 0, tzinfo=WIB)) == \
        datetime(2026, 11, 17, 7, 30, tzinfo=WIB).astimezone(UTC)
    weekly = Schedule(frequency="weekly", weekday=4, hour=9, minute=0)  # Jumat
    assert weekly.next_after(at) == datetime(2026, 11, 20, 9, 0, tzinfo=WIB).astimezone(UTC)
    assert weekly.describe() == "Setiap Jumat 09.00 WIB" and daily.describe() == "Setiap hari 07.30 WIB"


# ── API dasar & pengingat ─────────────────────────────────────────────────
def test_crud_run_and_notifications(client):
    assert client.post("/api/automation", json={"kind": "tidak_ada"}).status_code == 400
    assert client.post("/api/automation", json={"kind": "pengingat_produksi", "params": {}}).status_code == 400
    created = client.post("/api/automation", json={
        "kind": "pengingat_produksi", "name": "Upload Jumat", "params": {"text": "Render & upload video edukasi."},
        "schedule": {"frequency": "weekly", "weekday": 4, "hour": 9}}).json()
    assert created["schedule_text"] == "Setiap Jumat 09.00 WIB" and created["next_due_at"]
    started = client.post(f"/api/automation/{created['id']}/run").json()
    assert _done(client, started["task"]["id"])["status"] == "COMPLETED"
    notes = client.get("/api/notifications").json()
    assert notes["unread"] == 1 and notes["items"][0]["body"] == "Render & upload video edukasi."
    assert notes["items"][0]["title"] == "Pengingat: Upload Jumat"
    assert client.post("/api/notifications/read").json()["unread"] == 0
    item = client.get("/api/automation").json()["items"][0]
    assert item["last_run"]["status"] == "COMPLETED" and item["last_run"]["trigger"] == "manual"
    # nonaktif → tidak punya jadwal berikutnya; aktif lagi → dijadwalkan ulang
    assert client.patch(f"/api/automation/{created['id']}", json={"enabled": False}).json()["next_due_at"] is None
    assert client.patch(f"/api/automation/{created['id']}", json={"enabled": True}).json()["next_due_at"]
    assert client.delete(f"/api/automation/{created['id']}").status_code == 204
    assert client.get("/api/automation").json()["items"] == []


def test_missed_schedule_runs_once_and_is_labeled_late(client):
    created = client.post("/api/automation", json={"kind": "pengingat_produksi", "params": {"text": "Cek naskah"}}
                          ).json()
    _make_due(client, created["id"], minutes_ago=60 * 26)  # terlewat lebih dari sehari (ZOI tertidur)
    service = client.app.state.zoi.automation
    started = service.check_due("jadwal")
    assert len(started) == 1
    assert _done(client, started[0]["task"]["id"])["status"] == "COMPLETED"
    run = client.get(f"/api/automation/{created['id']}/runs").json()["items"][0]
    assert run["late"] is True and run["trigger"] == "susulan"
    # sudah dijadwalkan ke waktu berikutnya di masa depan → pemeriksaan kedua tidak menjalankan apa pun
    assert service.check_due("jadwal") == []
    nxt = datetime.fromisoformat(client.get("/api/automation").json()["items"][0]["next_due_at"])
    assert nxt > datetime.now(UTC)


def test_scheduler_loop_runs_due_automation(client_factory):
    client = client_factory()
    created = client.post("/api/automation", json={"kind": "pengingat_produksi", "params": {"text": "x"}}).json()
    _make_due(client, created["id"], minutes_ago=1)
    # loop penjadwal di lifespan berjalan tiap 60 detik; panggil langsung seperti satu putaran loop
    started = client.app.state.zoi.automation.check_due("jadwal")
    assert started and _done(client, started[0]["task"]["id"])["status"] == "COMPLETED"
    run = client.get(f"/api/automation/{created['id']}/runs").json()["items"][0]
    assert run["late"] is False and run["trigger"] == "jadwal"


def test_wake_endpoint_token(client_factory):
    client = client_factory(wake_token=WAKE)
    assert client.post("/api/automation/wake").status_code == 401
    assert client.post("/api/automation/wake", headers={"Authorization": "Bearer salah"}).status_code == 401
    created = client.post("/api/automation", json={"kind": "pengingat_produksi", "params": {"text": "pagi"}}).json()
    _make_due(client, created["id"], minutes_ago=2)
    woke = client.post("/api/automation/wake", headers={"Authorization": f"Bearer {WAKE}"})
    assert woke.status_code == 200 and woke.json() == {"ok": True, "started": 1}
    run = client.get(f"/api/automation/{created['id']}/runs").json()["items"][0]
    assert run["trigger"] == "bangun"
    assert client.get("/api/automation").json()["wake_enabled"] is True
    off = client_factory()
    assert off.post("/api/automation/wake", headers={"Authorization": f"Bearer {WAKE}"}).status_code == 401


def test_short_wake_token_rejected(settings_factory):
    from app.config.modes import ConfigError, resolve_runtime
    with pytest.raises(ConfigError, match="ZOI_WAKE_TOKEN"):
        resolve_runtime(settings_factory(wake_token="pendek"))


def test_interrupted_run_is_marked_honestly(client):
    created = client.post("/api/automation", json={"kind": "pengingat_produksi", "params": {"text": "x"}}).json()
    from app.db.models import AutomationRun
    with client.app.state.zoi.db.session() as s:
        s.add(AutomationRun(id="r-putus", automation_id=created["id"], trigger="jadwal", late=False,
                            status="RUNNING", summary="", result_json="{}"))
    client.app.state.zoi.automation.recover()
    run = client.get(f"/api/automation/{created['id']}/runs").json()["items"][0]
    assert run["status"] == "FAILED" and "Terputus" in run["summary"]


# ── dengan YouTube tiruan ─────────────────────────────────────────────────
@pytest.fixture
def google():
    fake = FakeGoogle()
    fake.url = fake.start()
    yield fake
    fake.stop()


def test_youtube_automations(client_factory, google, monkeypatch):
    client = client_factory(youtube_test_url=google.url)
    # tanpa akun → laporan gagal jujur + notifikasi kegagalan
    report = client.post("/api/automation", json={"kind": "laporan_channel"}).json()
    task = client.post(f"/api/automation/{report['id']}/run").json()["task"]
    assert _done(client, task["id"])["status"] == "FAILED"
    assert "belum terhubung" in client.get("/api/notifications").json()["items"][0]["body"]

    connect(client)
    task = client.post(f"/api/automation/{report['id']}/run").json()["task"]
    assert _done(client, task["id"])["status"] == "COMPLETED"
    body = client.get("/api/notifications").json()["items"][0]["body"]
    assert "Subscriber:" in body and "Sumber: YouTube" in body and "%" not in body

    # tren: pemeriksaan pertama tanpa pembanding, lalu judul baru terdeteksi
    trend = client.post("/api/automation", json={"kind": "pantau_tren"}).json()
    task = client.post(f"/api/automation/{trend['id']}/run").json()["task"]
    assert _done(client, task["id"])["status"] == "COMPLETED"
    assert "belum ada pembanding" in client.get("/api/notifications").json()["items"][0]["body"]
    monkeypatch.setattr(fake_google, "TRENDING", [*fake_google.TRENDING, {
        "id": "trdAAAAAAA9", "title": "Video baru trending", "channel": "Baru", "category": "26"}])
    task = client.post(f"/api/automation/{trend['id']}/run").json()["task"]
    assert _done(client, task["id"])["status"] == "COMPLETED"
    note = client.get("/api/notifications").json()["items"][0]
    assert note["title"] == "1 judul baru di Trending" and "Video baru trending" in note["body"]

    # kompetitor: tambah, jalankan, lalu video baru muncul
    assert client.post("/api/youtube/public/competitors", json={"ref": OTHER_ID}).status_code == 200
    watch = client.post("/api/automation", json={"kind": "pantau_kompetitor"}).json()
    task = client.post(f"/api/automation/{watch['id']}/run").json()["task"]
    assert _done(client, task["id"])["status"] == "COMPLETED"
    monkeypatch.setattr(fake_google, "OTHER_VIDEOS", [{
        "id": "othAAAAAAA9", "title": "Kopi tubruk tradisional", "views": "10", "likes": "1", "comments": "0",
        "duration": "PT5M", "privacy": "public", "published": "2026-11-15T03:00:00Z"}, *fake_google.OTHER_VIDEOS])
    task = client.post(f"/api/automation/{watch['id']}/run").json()["task"]
    assert _done(client, task["id"])["status"] == "COMPLETED"
    note = client.get("/api/notifications").json()["items"][0]
    assert note["title"] == "1 video baru dari kompetitor" and "Kopi tubruk tradisional" in note["body"]

    # alat agen hanya-baca
    tools = {t["name"]: t for t in client.get("/api/agent/status").json()["tools"]}
    assert tools["otomasi_daftar"]["permission"] == "read"
