from __future__ import annotations

import httpx
import pytest

from app.security.cost_guard import CostGuard, CostGuardBlocked

PAID = ["api.openai.com", "api.anthropic.com", "generativelanguage.googleapis.com", "api.elevenlabs.io",
        "api.deepgram.com", "eastus.tts.speech.microsoft.com", "myres.cognitiveservices.azure.com",
        "api.muapi.ai", "ollama.com"]


def build(extra=(), recorder=None):
    return CostGuard.build(ollama_url="http://192.168.1.50:11434", extra_hosts=list(extra), recorder=recorder)


@pytest.mark.parametrize("host", PAID)
def test_paid_hosts_blocked_even_if_whitelisted(host):
    allowed, reason = build(extra=[host]).check(host)
    assert not allowed and "berbayar" in reason


@pytest.mark.parametrize("host", ["127.0.0.1", "localhost", "www.googleapis.com", "youtubeanalytics.googleapis.com",
                                  "192.168.1.50"])
def test_allowed_hosts(host):
    assert build().check(host)[0]


def test_unknown_host_blocked():
    assert not build().check("contoh.com")[0]


def test_client_enforces_and_records():
    records = []
    guard = build(recorder=lambda *a: records.append(a))
    transport = httpx.MockTransport(lambda r: httpx.Response(200, json={}))
    with guard.client(transport=transport) as client:
        client.get("http://127.0.0.1:11434/api/tags")
        with pytest.raises(CostGuardBlocked):
            client.post("https://api.openai.com/v1/chat/completions")
    assert records[0][3] is True and records[1][0] == "api.openai.com" and records[1][3] is False


def test_blocked_attempts_visible_in_audit(client):
    guard = client.app.state.zoi.guard
    with pytest.raises(CostGuardBlocked):
        guard.enforce("POST", "https://api.anthropic.com/v1/messages")
    entries = client.get("/api/network/audit").json()["entries"]
    assert entries[0]["host"] == "api.anthropic.com" and entries[0]["allowed"] is False
