"""Phase 3 — AI lokal: info model, pemilihan model, larangan unduh/hapus, berpikir, JSON, uji model, berhenti."""

from __future__ import annotations

import asyncio
import json
import time

import httpx
import pytest
from pydantic import BaseModel

from app.ai.evaluation import EvalNotAllowed, evaluate, load_prompts
from app.ai.structured import StructuredOutputError, chat_json, extract_json
from app.chat.service import SYSTEM_PROMPT, trim_history
from app.providers.base import DEFAULT_CONTEXT_TOKENS, ChatChunk, ChatMessage, ChatOptions, LocalModelAdmin
from app.providers.mock import TRIGGER_BAD_JSON, TRIGGER_THINK, MockProvider, mock_instance
from app.providers.ollama import ForbiddenOllamaCall, OllamaProvider
from app.security.cost_guard import CostGuard
from tests.conftest import HEADERS, wait_chat_done, wait_for, wait_task
from tests.fake_ollama import TRIGGER_SLOW, TRIGGER_THINK_TAG, FakeOllama

URL = "http://127.0.0.1:11434"
ALL = ["qwen3:4b", "uji-kecil:1b", "uji-embed:latest", "uji-awan:cloud"]


def guard() -> CostGuard:
    return CostGuard.build(ollama_url=URL, extra_hosts=[], recorder=None)


def ollama(model: str = "qwen3:4b", installed: list[str] | None = None) -> tuple[OllamaProvider, FakeOllama]:
    fake = FakeOllama(installed or ALL)
    return OllamaProvider(URL, model, guard(), transport=fake.transport()), fake


async def collect(provider, text, options=None):
    return [c async for c in provider.chat([ChatMessage("user", text)], options=options)]


# ── informasi model ──────────────────────────────────────────────────────────
async def test_installed_running_and_details_come_from_ollama():
    p, fake = ollama()
    installed = {m.name: m for m in await p.installed()}
    assert installed["qwen3:4b"].size_bytes == 2_500_000_000 and installed["qwen3:4b"].parameter_size == "4.0B"
    assert installed["uji-awan:cloud"].is_cloud and not installed["qwen3:4b"].is_cloud
    assert await p.running() == []
    await collect(p, "halo")
    assert [r.name for r in await p.running()] == ["qwen3:4b"]
    details = await p.show("qwen3:4b")
    assert details.capabilities == ["completion", "tools", "thinking"]
    assert details.context_tokens == 40960 and details.license_line == "Apache License"
    await p.unload("qwen3:4b")
    assert await p.running() == []


async def test_missing_fields_are_none_not_invented():
    p = OllamaProvider(URL, "x", guard(), transport=httpx.MockTransport(
        lambda r: httpx.Response(200, json={"models": [{"name": "x"}]})))
    model = (await p.installed())[0]
    assert model.size_bytes is None and model.parameter_size is None and model.family is None


@pytest.mark.parametrize(("model", "reason"), [
    ("uji-awan:cloud", "cloud"), ("gpt-oss:120b-cloud", "cloud"), ("qwen3:8b", "belum terpasang"),
    ("uji-embed:latest", "tidak bisa dipakai untuk percakapan"),
])
async def test_choice_validation_rejects(model, reason):
    p, _ = ollama()
    assert reason in (await p.validate_choice(model) or "")


async def test_choice_validation_accepts_local_chat_model():
    p, _ = ollama()
    assert await p.validate_choice("uji-kecil:1b") is None


# ── ZOI tidak pernah mengunduh / menghapus model ─────────────────────────────
@pytest.mark.parametrize("path", ["/api/pull", "/api/delete", "/api/push", "/api/create", "/api/copy",
                                  "/api/blobs/sha256:abc"])
async def test_model_file_endpoints_are_blocked_in_client(path):
    p, fake = ollama()
    with pytest.raises(ForbiddenOllamaCall):
        async with p._client(5) as client:
            await client.post(path, json={"model": "qwen3:8b"})
    assert fake.paths == []


async def test_normal_operations_never_touch_model_files():
    p, fake = ollama()
    await p.health()
    await p.validate_choice("qwen3:4b")
    await collect(p, "halo")
    await p.unload("qwen3:4b")
    assert not any(path.split()[1].startswith(("/api/pull", "/api/delete", "/api/create")) for path in fake.paths)


def test_ollama_satisfies_admin_protocol_and_mock_does_not():
    assert isinstance(OllamaProvider(URL, "m", guard()), LocalModelAdmin)
    assert not isinstance(MockProvider(0), LocalModelAdmin)


# ── berpikir, statistik, JSON, konteks ───────────────────────────────────────
async def test_thinking_models_get_think_and_chunks_are_separate():
    p, fake = ollama()
    chunks = await collect(p, "halo")
    assert fake.bodies[-1]["think"] is True
    assert "".join(c.text for c in chunks if c.type == "thinking") == "Menimbang jawaban."
    assert "".join(c.text for c in chunks if c.type == "text") == "Jawaban dari model lokal."
    stats = chunks[-1].stats
    assert stats and stats.output_tokens == 40 and stats.tokens_per_second == 20


async def test_non_thinking_model_gets_no_think_flag():
    p, fake = ollama("uji-kecil:1b")
    await collect(p, "halo")
    assert "think" not in fake.bodies[-1]


async def test_think_tags_inside_content_are_split_even_across_chunks():
    p, _ = ollama("uji-kecil:1b")
    chunks = await collect(p, TRIGGER_THINK_TAG)
    assert "".join(c.text for c in chunks if c.type == "thinking") == "Berpikir di dalam tag"
    assert "".join(c.text for c in chunks if c.type == "text") == "Jawaban akhir."


async def test_json_schema_sent_as_format_and_thinking_disabled():
    p, fake = ollama()
    schema = {"type": "object", "properties": {"a": {"type": "string"}}}
    await collect(p, "data", options=ChatOptions(json_schema=schema))
    assert fake.bodies[-1]["format"] == schema and fake.bodies[-1]["think"] is False


async def test_context_tokens_prefers_running_value_then_default():
    p, fake = ollama()
    assert await p.context_tokens() == DEFAULT_CONTEXT_TOKENS  # 40960 di model, dibatasi default Ollama
    fake.running["qwen3:4b"] = 8192
    assert await p.context_tokens() == 8192


def test_trim_history_keeps_newest_and_system_prompt():
    newest_first = [ChatMessage("user", f"pesan {i} " + "x" * 400) for i in range(30)]
    trimmed = trim_history(newest_first, 1024)
    assert trimmed[0].content == SYSTEM_PROMPT
    assert trimmed[-1].content.startswith("pesan 0 ")
    assert 1 < len(trimmed) < 30
    huge = trim_history([ChatMessage("user", "y" * 50_000)], 1024)
    assert len(huge) == 2 and 0 < len(huge[1].content) < 50_000


# ── keluaran terstruktur ─────────────────────────────────────────────────────
class Idea(BaseModel):
    judul: str
    aman: bool


def test_extract_json_tolerates_wrapping_text():
    assert json.loads(extract_json('Berikut:\n```json\n{"a": [1, 2]}\n``` selesai') or "") == {"a": [1, 2]}
    assert extract_json("tidak ada json {rusak") is None


@pytest.mark.parametrize("kind", ["mock", "ollama"])
async def test_chat_json_contract(kind):
    provider = MockProvider(0) if kind == "mock" else ollama()[0]
    result = await chat_json(provider, [ChatMessage("user", "ide")], Idea)
    assert isinstance(result.value, Idea) and result.attempts == 1
    if kind == "mock":
        assert result.value.judul == "[MOCK]"


async def test_chat_json_retries_once_with_the_error_explained():
    result = await chat_json(MockProvider(0), [ChatMessage("user", TRIGGER_BAD_JSON)], Idea)
    assert result.attempts == 2


def ChunkText(text: str) -> ChatChunk:  # noqa: N802
    return ChatChunk(type="text", text=text)


def ChunkDone() -> ChatChunk:  # noqa: N802
    return ChatChunk(type="done")


class AlwaysBroken(MockProvider):
    async def chat(self, messages, tools=None, timeout_s=120.0, options=None):
        yield ChunkText('{"judul": 5')
        yield ChunkDone()


async def test_chat_json_fails_honestly_after_two_attempts():
    with pytest.raises(StructuredOutputError, match="setelah 2 percobaan"):
        await chat_json(AlwaysBroken(0), [ChatMessage("user", "ide")], Idea)


def test_mock_never_invents_numbers():
    with pytest.raises(ValueError, match="angka"):
        mock_instance({"type": "object", "properties": {"views": {"type": "integer"}}, "required": ["views"]})


async def test_mock_thinking_trigger():
    chunks = await collect(MockProvider(0), TRIGGER_THINK)
    assert any(c.type == "thinking" and "[MOCK]" in c.text for c in chunks)


# ── uji model ────────────────────────────────────────────────────────────────
def test_eval_prompts_fixed_set():
    prompts = load_prompts()["prompts"]
    assert len(prompts) == 20 and len({p["id"] for p in prompts}) == 20
    assert [sum(p["category"] == c for p in prompts) for c in ("chat", "json", "tool")] == [10, 5, 5]


async def test_eval_refuses_mock():
    with pytest.raises(EvalNotAllowed):
        await evaluate(MockProvider(0))


async def test_eval_measures_and_never_scores_chat_quality():
    p, _ = ollama()
    results, summary = await evaluate(p)
    chat = [r for r in results if r.category == "chat"]
    assert all(r.passed is None for r in chat)  # dinilai pengguna
    assert summary["json"] == {"passed": 5, "total": 5}
    assert summary["median_tokens_per_s"] == 20.0
    tools = {r.id: r for r in results if r.category == "tool"}
    assert tools["t01"].passed and tools["t05"].passed and not tools["t02"].passed  # angka nyata, bukan karangan


# ── API ──────────────────────────────────────────────────────────────────────
def test_status_in_development_is_honest(client):
    data = client.get("/api/ai/status").json()
    assert data["is_mock"] and not data["reachable"] and data["installed"] == [] and data["can_download"] is False
    assert "Mock" in data["detail"] and data["catalog"]["models"]
    for path in ("/api/ai/test", "/api/ai/evaluations"):
        response = client.post(path, json={"model": "qwen3:4b"} if "evaluations" in path else None)
        assert response.status_code == 409


def local_client(client_factory, fake: FakeOllama, **overrides):
    client = client_factory(mode="local", ollama_url=URL, **overrides)
    client.app.state.zoi.provider._transport = fake.transport()
    return client


def test_active_model_from_ui_persists_and_resets(client_factory):
    fake = FakeOllama(ALL)
    client = local_client(client_factory, fake, ollama_model="qwen3:4b")
    status = client.get("/api/ai/status").json()
    assert status["reachable"] and status["active_model"] == "qwen3:4b" and status["active_source"] == "env"
    assert {m["name"] for m in status["installed"]} == set(ALL)

    rejected = client.put("/api/ai/active-model", json={"model": "uji-awan:cloud"})
    assert rejected.status_code == 400 and "cloud" in rejected.json()["error"]["message"]
    assert client.put("/api/ai/active-model", json={"model": "qwen3:8b"}).status_code == 400

    ok = client.put("/api/ai/active-model", json={"model": "uji-kecil:1b"}).json()
    assert ok == {"active_model": "uji-kecil:1b", "active_source": "ui"}
    assert client.get("/api/provider/status").json()["model"] == "uji-kecil:1b"

    again = local_client(client_factory, FakeOllama(ALL), ollama_model="qwen3:4b")  # restart, data yang sama
    assert again.get("/api/ai/status").json()["active_model"] == "uji-kecil:1b"
    assert again.delete("/api/ai/active-model").json() == {"active_model": "qwen3:4b", "active_source": "env"}


def test_unload_details_and_connection_test(client_factory):
    fake = FakeOllama(ALL)
    fake.running["qwen3:4b"] = 4096
    client = local_client(client_factory, fake, ollama_model="qwen3:4b")
    assert client.post("/api/ai/test").json()["ok"]
    assert client.get("/api/ai/model", params={"name": "qwen3:4b"}).json()["context_tokens"] == 40960
    assert client.get("/api/ai/model", params={"name": "tidak:ada"}).status_code == 404
    assert client.post("/api/ai/unload", json={"model": "qwen3:4b"}).json() == {"running": []}


def test_unreachable_ollama_reports_without_numbers(client_factory):
    client = client_factory(mode="local", ollama_url="http://127.0.0.1:9", ollama_model="qwen3:4b")
    data = client.get("/api/ai/status").json()
    assert not data["reachable"] and data["installed"] == [] and data["version"] is None
    assert client.post("/api/ai/test").json() == {"ok": False, "detail": data["detail"], "latency_ms": None}


def test_evaluation_task_saves_real_results_and_ratings(client_factory):
    fake = FakeOllama(ALL)
    client = local_client(client_factory, fake, ollama_model="qwen3:4b")
    task = client.post("/api/ai/evaluations", json={"model": "qwen3:4b"}).json()
    assert task["name"] == "Uji model AI: qwen3:4b"
    done = wait_task(client, task["id"], {"COMPLETED", "FAILED"})
    assert done["status"] == "COMPLETED", done
    listing = client.get("/api/ai/evaluations").json()
    assert len(listing["prompts"]) == 20 and listing["evaluations"][0]["model"] == "qwen3:4b"
    evaluation_id = listing["evaluations"][0]["id"]
    rated = client.put(f"/api/ai/evaluations/{evaluation_id}/rating", json={"prompt_id": "c01", "rating": "up"}).json()
    assert rated["ratings"] == {"up": 1, "down": 0} and rated["rating_by_prompt"] == {"c01": "up"}
    assert client.put(f"/api/ai/evaluations/{evaluation_id}/rating",
                      json={"prompt_id": "j01", "rating": "up"}).status_code == 400
    assert not any("/api/pull" in p for p in fake.paths)


# ── chat: berhenti & berpikir ────────────────────────────────────────────────
def test_stop_keeps_partial_answer_and_returns_to_idle(client_factory):
    fake = FakeOllama(ALL)
    client = local_client(client_factory, fake, ollama_model="uji-kecil:1b")
    sent = client.post("/api/chat", json={"message": f"cerita panjang {TRIGGER_SLOW}"}).json()
    message_id = sent["assistant_message"]["id"]
    wait_for(lambda: any("/api/chat" in p for p in fake.paths))
    time.sleep(0.4)
    assert client.post(f"/api/chat/{message_id}/stop").json() == {"stopped": True}
    final = wait_chat_done(client, sent["conversation_id"])[-1]
    assert final["status"] == "stopped" and final["error"] is None
    assert client.post(f"/api/chat/{message_id}/stop").json() == {"stopped": False}
    wait_for(lambda: client.get("/api/agent/state").json()["state"] == "IDLE")


def test_thinking_is_stored_separately(client):
    sent = client.post("/api/chat", json={"message": f"jelaskan {TRIGGER_THINK}"}, headers=HEADERS).json()
    final = wait_chat_done(client, sent["conversation_id"])[-1]
    assert final["thinking"].startswith("[MOCK]") and final["content"].startswith("[MOCK]")
    assert "Menimbang" not in final["content"]


async def test_real_http_streaming_and_cancel_against_fake_server():
    import threading

    from tests.fake_ollama import serve

    server = serve(0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        port = server.server_address[1]
        p = OllamaProvider(f"http://127.0.0.1:{port}", "qwen3:4b",
                           CostGuard.build(ollama_url=f"http://127.0.0.1:{port}", extra_hosts=[], recorder=None))
        chunks = await collect(p, "halo")
        assert "".join(c.text for c in chunks if c.type == "text") == "Jawaban dari model lokal."
        received: list[str] = []

        async def slow() -> None:
            async for chunk in p.chat([ChatMessage("user", TRIGGER_SLOW)]):
                received.append(chunk.text)

        task = asyncio.create_task(slow())
        await asyncio.sleep(0.5)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert 2 < len(received) < 150  # berhenti di tengah, tidak menunggu 200 kata
    finally:
        server.shutdown()
