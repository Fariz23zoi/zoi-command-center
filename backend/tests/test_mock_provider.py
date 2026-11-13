from __future__ import annotations

import json
import re

from app.providers.base import ChatMessage
from app.providers.mock import PREFIX, SCRIPTS_DIR, MockProvider
from tests.conftest import wait_chat_done


def test_scripts_contain_no_numbers():
    """Mock tidak boleh bisa menghasilkan statistik: skenario dilarang berisi digit."""
    for path in SCRIPTS_DIR.glob("*.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        texts = [data.get("default", "")] + [r["reply"] for r in data.get("rules", [])]
        for text in texts:
            assert not re.search(r"\d", text), f"{path.name}: {text}"


async def test_every_reply_is_prefixed():
    provider = MockProvider(latency_ms=0)
    for text in ["halo", "berapa subscriber saya?", "apa saja", "clipper"]:
        chunks = [c async for c in provider.chat([ChatMessage("user", text)])]
        reply = "".join(c.text for c in chunks if c.type == "text")
        assert reply.startswith(PREFIX)
        assert not re.search(r"\d", reply)


def test_chat_persists_mock_flags(client):
    res = client.post("/api/chat", json={"message": "Halo ZOI"})
    assert res.status_code == 202
    body = res.json()
    messages = wait_chat_done(client, body["conversation_id"])
    assert [m["role"] for m in messages] == ["user", "assistant"]
    assistant = messages[-1]
    assert assistant["status"] == "complete" and assistant["content"].startswith("[MOCK]")
    assert assistant["provider"] == "mock" and assistant["is_mock"] is True
    assert all(m["is_mock"] for m in messages)
    convs = client.get("/api/conversations").json()["conversations"]
    assert convs[0]["is_mock"] is True and convs[0]["title"] == "Halo ZOI"


def test_chat_continues_same_conversation(client):
    first = client.post("/api/chat", json={"message": "halo"}).json()
    wait_chat_done(client, first["conversation_id"])
    second = client.post("/api/chat", json={"message": "bantuan", "conversation_id": first["conversation_id"]})
    msgs = wait_chat_done(client, second.json()["conversation_id"])
    assert len(msgs) == 4


def test_chat_validation(client):
    assert client.post("/api/chat", json={"message": ""}).status_code == 422
    assert client.post("/api/chat", json={"message": "   "}).status_code == 400
    assert client.post("/api/chat", json={"message": "x" * 4001}).status_code == 422
    assert client.post("/api/chat", json={"message": "hai", "conversation_id": "tidak-ada"}).status_code == 404


def test_provider_error_saved_honestly(client):
    res = client.post("/api/chat", json={"message": "/uji-error"}).json()
    assistant = wait_chat_done(client, res["conversation_id"])[-1]
    assert assistant["status"] == "error" and "Simulasi error" in assistant["error"]


def test_local_mode_never_falls_back_to_mock(client_factory):
    client = client_factory(mode="local", ollama_url="http://127.0.0.1:9", ollama_model="qwen3:4b")
    res = client.post("/api/chat", json={"message": "halo"}).json()
    assistant = wait_chat_done(client, res["conversation_id"])[-1]
    assert assistant["provider"] == "ollama" and assistant["is_mock"] is False
    assert assistant["status"] == "error" and "tidak dapat dihubungi" in assistant["error"]
    assert "[MOCK]" not in assistant["content"]
    status = client.get("/api/provider/status").json()
    assert status["available"] is False and status["is_mock"] is False
