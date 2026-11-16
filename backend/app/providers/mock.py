"""Mock Provider — HANYA untuk ZOI_MODE=development.

Aturan (lihat docs/adr/0003-mock-provider.md):
- Setiap jawaban diawali "[MOCK]" dan ditandai is_mock di database.
- Tidak pernah menghasilkan angka/statistik (dijaga tes: skenario tidak boleh berisi digit).
- Deterministik: jawaban dipilih dari skenario JSON berbasis kata kunci.
- Mensimulasikan kondisi gagal yang sama seperti provider sungguhan (error, timeout, tool call rusak)
  lewat kata pemicu khusus, agar kontrak yang sama bisa diuji.
"""

from __future__ import annotations

import asyncio
import json
import re
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.providers.base import (
    DEFAULT_CONTEXT_TOKENS,
    ChatChunk,
    ChatMessage,
    ChatOptions,
    ProviderStatus,
    ToolCall,
    ToolSpec,
)

SCRIPTS_DIR = Path(__file__).resolve().parent / "mock_scripts"
PREFIX = "[MOCK] "

# Pemicu kontrak (dipakai juga oleh server Ollama tiruan di tes).
TRIGGER_ERROR = "/uji-error"
TRIGGER_TIMEOUT = "/uji-timeout"
TRIGGER_TOOL = "/uji-tool"
TRIGGER_BAD_TOOL = "/uji-tool-rusak"
TRIGGER_THINK = "/uji-berpikir"
TRIGGER_BAD_JSON = "/uji-json-rusak"


class MockJsonUnsupported(ValueError):
    pass


def mock_instance(schema: dict[str, Any], defs: dict[str, Any] | None = None) -> Any:
    """Contoh minimal yang lolos skema — teks diberi label [MOCK]; angka TIDAK PERNAH dikarang."""
    defs = defs if defs is not None else schema.get("$defs", {})
    if "$ref" in schema:
        return mock_instance(defs[schema["$ref"].split("/")[-1]], defs)
    if "enum" in schema:
        return schema["enum"][0]
    if "anyOf" in schema:
        for option in schema["anyOf"]:
            if option.get("type") == "null":
                return None
        return mock_instance(schema["anyOf"][0], defs)
    kind = schema.get("type")
    if kind == "object":
        props = schema.get("properties", {})
        return {key: mock_instance(props[key], defs) for key in schema.get("required", list(props))}
    if kind == "array":
        return []
    if kind == "string":
        return "[MOCK]"
    if kind == "boolean":
        return False
    if kind == "null":
        return None
    raise MockJsonUnsupported("Mock Provider tidak mengarang angka untuk keluaran terstruktur.")


@dataclass(frozen=True)
class Rule:
    pattern: re.Pattern[str]
    reply: str


def load_rules(scripts_dir: Path = SCRIPTS_DIR) -> tuple[list[Rule], str]:
    rules: list[Rule] = []
    default = "Ini jawaban tiruan dari Mock Provider."
    for path in sorted(scripts_dir.glob("*.json")):
        data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        default = data.get("default", default)
        for item in data.get("rules", []):
            rules.append(Rule(re.compile(item["match"], re.IGNORECASE), item["reply"]))
    return rules, default


class MockProvider:
    name = "mock"
    is_mock = True
    model = "mock-scripted"

    def __init__(self, latency_ms: int = 300, scripts_dir: Path = SCRIPTS_DIR) -> None:
        self.latency_ms = latency_ms
        self.rules, self.default_reply = load_rules(scripts_dir)

    async def health(self) -> ProviderStatus:
        return ProviderStatus(
            name=self.name, available=True, is_mock=True, model=self.model, models=[self.model],
            detail="Mock Provider (mode development). Jawaban adalah TIRUAN, bukan AI sungguhan.",
        )

    async def list_models(self) -> list[str]:
        return [self.model]

    def set_model(self, model: str | None) -> None:  # noqa: ARG002 — model mock tetap
        return None

    async def context_tokens(self) -> int:
        return DEFAULT_CONTEXT_TOKENS

    def reply_for(self, text: str) -> str:
        for rule in self.rules:
            if rule.pattern.search(text):
                return rule.reply
        return self.default_reply

    async def _pause(self, factor: float = 1.0) -> None:
        if self.latency_ms:
            await asyncio.sleep(self.latency_ms / 1000 * factor)

    async def chat(
        self, messages: list[ChatMessage], tools: list[ToolSpec] | None = None, timeout_s: float = 120.0,
        options: ChatOptions | None = None,
    ) -> AsyncIterator[ChatChunk]:
        last_user = next((m.content for m in reversed(messages) if m.role == "user"), "")
        await self._pause()

        if options and options.json_schema is not None:
            if TRIGGER_BAD_JSON in last_user:
                yield ChatChunk(type="text", text='{"rusak": ')
                yield ChatChunk(type="done")
                return
            try:
                payload = json.dumps(mock_instance(options.json_schema), ensure_ascii=False)
            except (MockJsonUnsupported, KeyError, IndexError) as exc:
                yield ChatChunk(type="error", error=str(exc))
                return
            yield ChatChunk(type="text", text=payload)
            yield ChatChunk(type="done")
            return

        if TRIGGER_ERROR in last_user:
            yield ChatChunk(type="error", error="Simulasi error dari Mock Provider.")
            return
        if TRIGGER_TIMEOUT in last_user:
            yield ChatChunk(type="error", error=f"timeout: tidak ada jawaban dalam {timeout_s:g} detik (simulasi).")
            return
        if TRIGGER_BAD_TOOL in last_user:
            yield ChatChunk(type="error", error="Format pemanggilan tool dari model tidak valid (simulasi).")
            return
        if TRIGGER_TOOL in last_user:
            if not tools:
                yield ChatChunk(type="error", error="Model meminta tool, tetapi tidak ada tool yang diberikan.")
                return
            yield ChatChunk(type="tool_call", tool_call=ToolCall(name=tools[0].name, arguments={}))
            yield ChatChunk(type="done")
            return

        if TRIGGER_THINK in last_user:
            for word in "[MOCK] Menimbang pertanyaan sebelum menjawab.".split(" "):
                yield ChatChunk(type="thinking", text=word + " ")
                await self._pause(0.05)

        words = (PREFIX + self.reply_for(last_user)).split(" ")
        for index, word in enumerate(words):
            yield ChatChunk(type="text", text=word if index == 0 else " " + word)
            await self._pause(0.05)
        yield ChatChunk(type="done")
