"""Kontrak yang SAMA untuk Mock dan Ollama — agar perpindahan mock → AI sungguhan tidak mengubah kode."""

from __future__ import annotations

import pytest

from app.providers.base import ChatMessage, ToolSpec
from app.providers.mock import TRIGGER_BAD_TOOL, TRIGGER_ERROR, TRIGGER_TIMEOUT, TRIGGER_TOOL, MockProvider
from app.providers.ollama import OllamaProvider
from app.security.cost_guard import CostGuard
from tests.fake_ollama import FakeOllama

TOOLS = [ToolSpec(name="periksa_sistem", description="Periksa sistem", parameters={"type": "object"})]


def guard() -> CostGuard:
    return CostGuard.build(ollama_url="http://127.0.0.1:11434", extra_hosts=[], recorder=None)


@pytest.fixture(params=["mock", "ollama"])
def provider(request):
    if request.param == "mock":
        return MockProvider(latency_ms=0)
    fake = FakeOllama()
    p = OllamaProvider("http://127.0.0.1:11434", "qwen3:4b", guard(), transport=fake.transport())
    p.fake = fake  # type: ignore[attr-defined]
    return p


async def collect(provider, text, tools=None):
    return [c async for c in provider.chat([ChatMessage("system", "s"), ChatMessage("user", text)], tools=tools)]


async def test_health_available(provider):
    status = await provider.health()
    assert status.available and status.name == provider.name and status.is_mock == provider.is_mock


async def test_text_stream_ends_with_single_done(provider):
    chunks = await collect(provider, "halo")
    assert chunks[-1].type == "done"
    assert [c.type for c in chunks].count("done") == 1
    assert "".join(c.text for c in chunks if c.type == "text").strip()


@pytest.mark.parametrize("trigger", [TRIGGER_ERROR, TRIGGER_TIMEOUT, TRIGGER_BAD_TOOL])
async def test_failures_are_error_chunks_not_exceptions(provider, trigger):
    chunks = await collect(provider, f"tolong {trigger}", tools=TOOLS)
    assert chunks[-1].type == "error" and chunks[-1].error
    if trigger == TRIGGER_TIMEOUT:
        assert "timeout" in chunks[-1].error


async def test_tool_call_structure(provider):
    chunks = await collect(provider, TRIGGER_TOOL, tools=TOOLS)
    calls = [c.tool_call for c in chunks if c.type == "tool_call"]
    assert calls and calls[0].name == "periksa_sistem" and isinstance(calls[0].arguments, dict)
    assert chunks[-1].type == "done"


async def test_ollama_never_pulls_models():
    fake = FakeOllama()
    p = OllamaProvider("http://127.0.0.1:11434", "qwen3:4b", guard(), transport=fake.transport())
    await p.health()
    await collect(p, "halo")
    assert not any("/api/pull" in path or "/api/create" in path for path in fake.paths)


async def test_ollama_model_not_installed_is_reported():
    p = OllamaProvider("http://127.0.0.1:11434", "qwen3:8b", guard(), transport=FakeOllama().transport())
    status = await p.health()
    assert not status.available and "ollama pull qwen3:8b" in status.detail and "tidak mengunduh" in status.detail


async def test_ollama_without_model_is_unavailable():
    p = OllamaProvider("http://127.0.0.1:11434", "", guard(), transport=FakeOllama().transport())
    assert not (await p.health()).available
    chunks = await collect(p, "halo")
    assert chunks == [chunks[0]] and chunks[0].type == "error"


async def test_ollama_unreachable_is_honest():
    p = OllamaProvider("http://127.0.0.1:9", "qwen3:4b", guard(), health_timeout_s=0.5)
    status = await p.health()
    assert not status.available and "tidak dapat dihubungi" in status.detail
