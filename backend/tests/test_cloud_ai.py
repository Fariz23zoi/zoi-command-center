"""AI cloud gratis: NVIDIA NIM (utama) + OpenRouter (cadangan). Semua tes memakai server TIRUAN di komputer ini."""

from __future__ import annotations

import json

import pytest
from pydantic import BaseModel

from app.ai.structured import chat_json
from app.config.modes import ConfigError, resolve_runtime
from app.providers.base import ChatMessage, ToolSpec
from app.providers.cloud import NVIDIA, OPENROUTER, LimitReached, RequestLimiter
from app.security.cost_guard import CostGuard
from tests.conftest import make_settings, wait_chat_done, wait_task
from tests.fake_cloud import NV_KEY, NV_MODEL, OR_KEY, OR_MODEL, FakeCloud

C = "/api/ai/cloud"


@pytest.fixture
def cloud():
    fake = FakeCloud()
    fake.start()
    yield fake
    fake.stop()


def env(cloud: FakeCloud, **overrides):
    return {"ai_provider": "nvidia", "nvidia_model": NV_MODEL, "ai_fallback": "openrouter",
            "openrouter_model": OR_MODEL, "cloud_test_url": cloud.url, **overrides}


@pytest.fixture
def app(client_factory, cloud):
    client = client_factory(**env(cloud))
    assert client.put(f"{C}/keys/nvidia", json={"key": NV_KEY}).status_code == 200
    assert client.put(f"{C}/keys/openrouter", json={"key": OR_KEY}).status_code == 200
    return client


def ask(client, text: str) -> dict:
    conversation = client.post("/api/chat", json={"message": text}).json()["conversation_id"]
    return wait_chat_done(client, conversation)[-1]


async def collect(provider, text: str, **kwargs):
    return [c async for c in provider.chat([ChatMessage("user", text)], **kwargs)]


# ── konfigurasi ───────────────────────────────────────────────────────────
@pytest.mark.parametrize(("overrides", "message"), [
    ({"ai_provider": "nvidia", "nvidia_model": "m", "ai_fallback": "openrouter", "openrouter_model": "x/berbayar"},
     "bukan model gratis"),
    ({"ai_provider": "openrouter", "openrouter_model": "openai/gpt-5"}, "bukan model gratis"),
    ({"ai_provider": "openrouter", "openrouter_model": "a:free", "ai_fallback": "openrouter"}, "ZOI_AI_FALLBACK"),
    ({"ai_fallback": "openrouter", "openrouter_model": "a:free"}, "ZOI_AI_FALLBACK"),
    ({"cloud_test_url": "https://api.example.com"}, "ZOI_CLOUD_TEST_URL"),
])
def test_config_rules(tmp_path, overrides, message):
    with pytest.raises(ConfigError, match=message):
        resolve_runtime(make_settings(tmp_path, **overrides))


def test_missing_cloud_model_is_warning_not_error(tmp_path):
    # Model belum diisi → aplikasi tetap jalan (AI "tidak tersedia"), bukan gagal start. Dipakai mode online.
    runtime = resolve_runtime(make_settings(tmp_path, ai_provider="nvidia"))
    assert any("ZOI_NVIDIA_MODEL" in w for w in runtime.warnings)
    runtime = resolve_runtime(make_settings(tmp_path, ai_provider="nvidia", nvidia_model="m",
                                            ai_fallback="openrouter"))
    assert any("ZOI_OPENROUTER_MODEL" in w for w in runtime.warnings)


def test_default_stays_local_and_cloud_hosts_stay_blocked(tmp_path, client):
    runtime = resolve_runtime(make_settings(tmp_path))
    assert runtime.provider == "mock" and runtime.cloud_names == ()
    local = resolve_runtime(make_settings(tmp_path, mode="local"))
    assert local.provider == "ollama" and local.cloud_names == ()
    guard = client.app.state.zoi.guard
    for host in ("integrate.api.nvidia.com", "openrouter.ai"):
        allowed, reason = guard.check(host)
        assert allowed is False and "tidak diaktifkan" in reason
    status = client.get(f"{C}/status").json()
    assert status["enabled"] is False and all(p["role"] is None for p in status["providers"])


def test_cloud_hosts_open_only_for_chosen_providers(tmp_path):
    runtime = resolve_runtime(make_settings(tmp_path, ai_provider="nvidia", nvidia_model="m"))
    assert runtime.cloud_names == ("nvidia",)
    assert any("AI CLOUD aktif" in w and "NVIDIA NIM" in w for w in runtime.warnings)
    guard = CostGuard.build(ollama_url="http://127.0.0.1:11434", extra_hosts=["openrouter.ai", "api.openai.com"],
                            cloud_hosts=["integrate.api.nvidia.com"], recorder=None)
    assert guard.check("integrate.api.nvidia.com")[0] is True
    assert guard.check("openrouter.ai")[0] is False       # tidak dipilih → tetap tertutup walau di EXTRA hosts
    assert guard.check("api.openai.com")[0] is False
    with pytest.raises(ValueError, match="tidak dikenal"):
        CostGuard.build(ollama_url="http://127.0.0.1:1", extra_hosts=[], cloud_hosts=["api.openai.com"], recorder=None)


def test_real_endpoints_and_limits_are_below_official():
    assert NVIDIA.base_url == "https://integrate.api.nvidia.com/v1"
    assert OPENROUTER.base_url == "https://openrouter.ai/api/v1"
    assert NVIDIA.per_minute < NVIDIA.official_per_minute == 40
    assert OPENROUTER.per_minute < OPENROUTER.official_per_minute == 20
    assert OPENROUTER.per_day < OPENROUTER.official_per_day == 50
    assert OPENROUTER.free_suffix_required and not NVIDIA.free_suffix_required


# ── API key ───────────────────────────────────────────────────────────────
def test_keys_are_validated_stored_secretly_and_never_returned(client_factory, cloud, tmp_path):
    client = client_factory(**env(cloud))
    assert client.put(f"{C}/keys/nvidia", json={"key": "sk-or-v1-" + "x" * 30}).status_code == 400
    assert client.put(f"{C}/keys/nvidia", json={"key": "nvapi-pendek"}).status_code == 400
    assert client.put(f"{C}/keys/bytez", json={"key": NV_KEY}).status_code == 404
    status = client.put(f"{C}/keys/nvidia", json={"key": f"  {NV_KEY}\n"}).json()
    nvidia = next(p for p in status["providers"] if p["name"] == "nvidia")
    assert nvidia["has_key"] is True and nvidia["role"] == "utama" and nvidia["model"] == NV_MODEL
    assert NV_KEY not in json.dumps(status) and status["token_storage"] == "file" and status["storage_warning"]
    data = tmp_path / "data"
    assert json.loads((data / "secrets" / "tokens.json").read_text())["nvidia_api_key"] == NV_KEY
    ask(client, "halo")
    blob = (data / "zoi.db").read_bytes() + b"".join(p.read_bytes() for p in data.glob("zoi.db-wal"))
    logs = "".join(p.read_text(errors="ignore") for p in (data / "logs").glob("*"))
    assert NV_KEY.encode() not in blob and NV_KEY not in logs
    after = client.delete(f"{C}/keys/nvidia").json()["providers"]
    assert next(p for p in after if p["name"] == "nvidia")["has_key"] is False


def test_missing_key_is_reported_not_guessed(client_factory, cloud):
    client = client_factory(**env(cloud, ai_fallback="none", openrouter_model=""))
    health = client.get("/api/provider/status").json()
    assert health["available"] is False and "API key NVIDIA NIM belum dimasukkan" in health["detail"]
    message = ask(client, "halo")
    assert message["status"] == "error" and "Settings › AI Cloud" in message["error"]
    assert cloud.requests == []


# ── percakapan ────────────────────────────────────────────────────────────
def test_chat_through_primary_is_labelled(app, cloud):
    health = app.get("/api/provider/status").json()
    assert health["available"] is True and health["name"] == "nvidia" and health["is_mock"] is False
    message = ask(app, "apa kabar /pikir")
    assert message["content"] == "[uji nvidia] jawaban untuk: apa kabar /pikir"
    assert message["provider"] == "nvidia" and message["model"] == NV_MODEL and message["note"] is None
    assert message["thinking"] == "menimbang jawaban" and message["is_mock"] is False
    sent = cloud.chats("nvidia")[0]
    assert sent["authorized"] and sent["body"]["model"] == NV_MODEL and sent["body"]["stream"] is True
    assert cloud.chats("openrouter") == []
    config = app.get("/api/config").json()
    assert config["is_cloud"] is True and config["cloud_providers"] == ["nvidia", "openrouter"]
    assert any("SERVER UJI" in w for w in config["warnings"])


def test_memory_context_is_sent_as_data(app, cloud):
    app.post("/api/memories", json={"content": "Channel saya tentang kopi nusantara", "kind": "fakta"})
    ask(app, "ide video kopi nusantara")
    contents = [m["content"] for m in cloud.chats("nvidia")[0]["body"]["messages"]]
    assert any("kopi nusantara" in c and "BUKAN" in c for c in contents[:-1])


@pytest.mark.parametrize(("status", "word"), [(429, "batas permintaan"), (500, "bermasalah"), (503, "bermasalah")])
def test_fallback_to_openrouter_is_announced(app, cloud, status, word):
    cloud.status["nvidia"] = status
    message = ask(app, "halo")
    assert message["status"] == "complete" and message["content"] == "[uji openrouter] jawaban untuk: halo"
    assert message["provider"] == "openrouter" and message["model"] == OR_MODEL
    assert "Dijawab OpenRouter (cadangan) karena NVIDIA NIM gagal" in message["note"] and word in message["note"]
    assert cloud.chats("openrouter")[0]["body"]["model"] == OR_MODEL


def test_fallback_when_primary_unreachable_or_slow(app, cloud):
    cloud.hang_s["nvidia"] = 1.5
    provider = app.app.state.zoi.provider

    async def run():
        return await collect(provider, "halo", timeout_s=0.3)

    chunks = app.portal.call(run)
    assert "".join(c.text for c in chunks if c.type == "text") == "[uji openrouter] jawaban untuk: halo"
    assert chunks[-1].served_by == "openrouter" and "timeout" in chunks[-1].note


@pytest.mark.parametrize(("status", "word"), [(401, "menolak API key"), (402, "pembayaran"),
                                              (404, "tidak bisa memanggil")])
def test_no_fallback_for_configuration_problems(app, cloud, status, word):
    cloud.status["nvidia"] = status
    message = ask(app, "halo")
    assert message["status"] == "error" and word in message["error"] and message["content"] == ""
    assert cloud.chats("openrouter") == []


def test_no_fallback_after_answer_started(app, cloud):
    cloud.cut.add("nvidia")
    message = ask(app, "halo")
    assert message["status"] == "error" and message["content"].startswith("[uji nvidia]")
    assert cloud.chats("openrouter") == []


def test_both_fail_reports_both(app, cloud):
    cloud.status |= {"nvidia": 429, "openrouter": 429}
    message = ask(app, "halo")
    assert message["status"] == "error"
    assert "NVIDIA NIM" in message["error"] and "cadangan OpenRouter juga gagal" in message["error"]


def test_unreadable_stream_is_an_error(app, cloud):
    cloud.garbage.add("nvidia")
    cloud.garbage.add("openrouter")
    assert "tidak dapat dibaca" in ask(app, "halo")["error"]


def test_no_fallback_configured(client_factory, cloud):
    client = client_factory(**env(cloud, ai_fallback="none", openrouter_model=""))
    client.put(f"{C}/keys/nvidia", json={"key": NV_KEY})
    cloud.status["nvidia"] = 429
    message = ask(client, "halo")
    assert message["status"] == "error" and "429" in message["error"] and cloud.chats("openrouter") == []


# ── penjaga biaya ─────────────────────────────────────────────────────────
def test_openrouter_refuses_non_free_model_before_sending(app, cloud):
    backup = app.app.state.zoi.provider.backup
    backup.model = "uji/berbayar"

    async def run():
        return await collect(backup, "halo")

    chunks = app.portal.call(run)
    assert chunks[-1].type == "error" and ":free" in chunks[-1].error and chunks[-1].error_kind == "config"
    assert cloud.chats("openrouter") == []


def test_only_inference_paths_are_reachable(app, cloud):
    primary = app.app.state.zoi.provider.primary

    async def run():
        async with primary._client(5.0) as client:
            return await client.get(f"{primary.spec.base_url}/credits")

    with pytest.raises(Exception, match="tidak dipakai ZOI"):
        app.portal.call(run)
    assert not any(r["path"].endswith("/credits") for r in cloud.requests)


def test_local_limit_stops_before_sending_and_triggers_fallback(app, cloud):
    primary = app.app.state.zoi.provider.primary
    for _ in range(NVIDIA.per_minute):
        primary.limiter.acquire()
    message = ask(app, "halo")
    assert message["provider"] == "openrouter" and "Batas aman NVIDIA NIM" in message["note"]
    assert cloud.chats("nvidia") == []


def test_daily_limit_is_persisted(client, monkeypatch):
    db = client.app.state.zoi.db
    limiter = RequestLimiter(db, OPENROUTER, clock=iter(range(0, 100_000, 61)).__next__)
    for _ in range(OPENROUTER.per_day):
        limiter.acquire()
    with pytest.raises(LimitReached, match="harian"):
        limiter.acquire()
    again = RequestLimiter(db, OPENROUTER)  # mis. setelah ZOI dijalankan ulang
    assert again.status()["day_used"] == 45 and again.status()["day_official"] == 50
    with pytest.raises(LimitReached):
        again.acquire()
    monkeypatch.setattr(RequestLimiter, "_today", staticmethod(lambda: "2099-01-01"))
    again.acquire()
    assert again.status()["day_used"] == 1


def test_minute_limit_uses_sliding_window(client):
    now = [0.0]
    limiter = RequestLimiter(client.app.state.zoi.db, NVIDIA, clock=lambda: now[0])
    for _ in range(NVIDIA.per_minute):
        limiter.acquire()
    with pytest.raises(LimitReached, match="menit"):
        limiter.acquire()
    now[0] = 61.0
    limiter.acquire()


# ── keluaran terstruktur, tool, konten ────────────────────────────────────
class Jawaban(BaseModel):
    judul: str
    poin: list[str]


def test_structured_output_sends_schema_as_text_and_validates(app, cloud):
    provider = app.app.state.zoi.provider

    async def run():
        return await chat_json(provider, [ChatMessage("user", "buat ringkasan")], Jawaban)

    result = app.portal.call(run)
    assert isinstance(result.value, Jawaban) and result.attempts == 1 and result.served_by is None
    body = cloud.chats("nvidia")[0]["body"]
    assert "response_format" not in body and '"judul"' in body["messages"][-1]["content"]


def test_tool_calls_are_assembled_from_fragments(app, cloud):
    provider = app.app.state.zoi.provider
    tool = ToolSpec("cari", "mencari", {"type": "object", "properties": {"kata": {"type": "string"}}})

    async def run():
        return await collect(provider, "tolong /tool", tools=[tool])

    chunks = app.portal.call(run)
    call = next(c.tool_call for c in chunks if c.type == "tool_call")
    assert call.name == "cari" and call.arguments == {"kata": "kopi"} and chunks[-1].type == "done"
    assert chunks[-1].stats.output_tokens == 7


def test_content_ideas_label_the_provider_that_answered(app, cloud):
    done = {"COMPLETED", "FAILED"}
    task = wait_task(app, app.post("/api/content/ideas", json={"topik": "kopi rumahan"}).json()["id"], done)
    assert task["status"] == "COMPLETED", task
    first = app.get("/api/content/items?kind=ideas").json()["items"][0]
    assert (first["provider"], first["model"], first["is_mock"]) == ("nvidia", NV_MODEL, False)
    cloud.status["nvidia"] = 500
    task = wait_task(app, app.post("/api/content/ideas", json={"topik": "teh rumahan"}).json()["id"], done)
    assert task["status"] == "COMPLETED", task
    second = app.get("/api/content/items?kind=ideas").json()["items"][0]
    assert (second["provider"], second["model"]) == ("openrouter", OR_MODEL)


def test_agent_is_available_with_cloud(app):
    status = app.get("/api/agent/status").json()
    assert status["available"] is True


# ── Settings › AI Cloud ───────────────────────────────────────────────────
def test_status_page_data(app):
    status = app.get(f"{C}/status").json()
    assert status["enabled"] is True and status["test_endpoint"] is True and status["provider"] == "nvidia"
    by_name = {p["name"]: p for p in status["providers"]}
    assert by_name["nvidia"]["role"] == "utama" and by_name["openrouter"]["role"] == "cadangan"
    assert by_name["openrouter"]["free_only"] is True and by_name["openrouter"]["limits"]["day_limit"] == 45
    assert by_name["nvidia"]["limits"]["minute_limit"] == 30 and "hitungan ZOI" in by_name["nvidia"]["limits"]["source"]
    assert any("suara" in line.lower() for line in status["never_sent"]) and status["data_sent"]
    assert "hanya bisa diubah lewat file .env" in status["selection"]


def test_models_and_test_button(app, cloud):
    models = app.get(f"{C}/models/openrouter").json()
    assert models["models"] == [OR_MODEL] and models["current_listed"] is True  # yang berbayar disaring
    assert app.get(f"{C}/models/nvidia").json()["models"] == sorted([NV_MODEL, "nvidia/tidak-bisa-dipanggil"])
    result = app.post(f"{C}/test/nvidia").json()
    assert result["ok"] is True and result["reply"].startswith("[uji nvidia]") and result["limits"]["minute_used"] == 1
    cloud.status["openrouter"] = 429
    result = app.post(f"{C}/test/openrouter").json()
    assert result["ok"] is False and "429" in result["error"]
    assert app.get(f"{C}/models/bytez").status_code == 409


def test_listed_but_uncallable_model_is_explained(client_factory, cloud):
    client = client_factory(**env(cloud, nvidia_model="nvidia/tidak-bisa-dipanggil"))
    client.put(f"{C}/keys/nvidia", json={"key": NV_KEY})
    assert client.get("/api/provider/status").json()["available"] is True  # ada di daftar…
    result = client.post(f"{C}/test/nvidia").json()                        # …tetapi tidak bisa dipanggil
    assert result["ok"] is False and "tidak tersedia untuk akun gratis" in result["error"]


def test_cloud_page_works_when_cloud_is_off(client):
    assert client.put(f"{C}/keys/openrouter", json={"key": OR_KEY}).json()["enabled"] is False
    assert client.post(f"{C}/test/openrouter").status_code == 409
    assert client.get("/api/ai/status").status_code == 200


def test_local_ai_page_points_to_cloud(app):
    assert "Settings › AI Cloud" in app.get("/api/ai/status").json()["detail"]


def test_voice_stays_local(app, cloud):
    status = app.get("/api/voice/status").json()
    assert "nvidia" not in json.dumps(status).lower() and "openrouter" not in json.dumps(status).lower()
    assert not any("audio" in r["path"] or "speech" in r["path"] for r in cloud.requests)
