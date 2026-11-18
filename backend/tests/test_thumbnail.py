"""Thumbnail otomatis: teks hook dari AI ZOI (JSON terstruktur) + perapian kombinasi warna."""

from __future__ import annotations

import json

import pytest


class _FakeProvider:
    name = "nvidia"
    is_mock = False

    def __init__(self, replies):
        self.replies = list(replies)
        self.seen = []

    async def chat(self, messages, *, timeout_s=0, options=None):
        from app.providers.base import ChatChunk
        self.seen.append(messages)
        yield ChatChunk(type="text", text=self.replies.pop(0))
        yield ChatChunk(type="done")


HOOK = {"baris": [
    {"teks": "Pernah nggak sih,", "ukuran": "sedang", "warna": "hitam", "kotak": "putih"},
    {"teks": "NGGAK  MAU,", "ukuran": "besar", "warna": "putih", "kotak": "tanpa"},   # putih tanpa kotak → pink
    {"teks": "tapi tetap bilang", "ukuran": "kecil", "warna": "kuning", "kotak": "kuning"},  # sewarna → diperbaiki
    {"teks": "IYA", "ukuran": "besar", "warna": "pink", "kotak": "tanpa"},
], "bubble": ["GILA!", "  "], "aksen": "kuning"}


async def test_hook_is_parsed_and_tidied():
    from app.thumbnail import thumbnail_hook

    fake = _FakeProvider(["```json\n" + json.dumps(HOOK) + "\n```"])
    out = await thumbnail_hook(fake, "Orang yang susah menolak", "9:16")
    rows = out["baris"]
    assert rows[1] == {"teks": "NGGAK MAU,", "ukuran": "besar", "warna": "pink", "kotak": "tanpa"}
    assert rows[2]["warna"] != rows[2]["kotak"]
    assert out["bubble"] == ["GILA!"] and out["aksen"] == "kuning" and out["provider"] == "nvidia"
    assert "vertikal 9:16" in fake.seen[0][1].content


async def test_hook_bad_json_is_honest_error():
    from app.core.errors import ZoiError
    from app.thumbnail import thumbnail_hook

    with pytest.raises(ZoiError):
        await thumbnail_hook(_FakeProvider(["bukan json"] * 5), "topik", "16:9")


def test_endpoint_validates(client_factory):
    client = client_factory()
    assert client.post("/api/thumbnail/hook", json={"topik": ""}).status_code == 422
    assert client.post("/api/thumbnail/hook", json={"topik": "abc", "rasio": "4:3"}).status_code == 422
