"""Antarmuka penyedia AI. Mock dan Ollama mengimplementasikan kontrak yang SAMA.

Kontrak chat(): selalu menghasilkan aliran ChatChunk dan diakhiri tepat satu chunk "done" atau "error".
Kegagalan (timeout, server mati, format rusak) dilaporkan sebagai chunk "error" — bukan exception —
agar UI selalu bisa menampilkan alasannya.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal, Protocol

Role = Literal["system", "user", "assistant", "tool"]


@dataclass(frozen=True)
class ChatMessage:
    role: Role
    content: str


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]

    def to_ollama(self) -> dict[str, Any]:
        return {"type": "function",
                "function": {"name": self.name, "description": self.description, "parameters": self.parameters}}


@dataclass(frozen=True)
class ToolCall:
    name: str
    arguments: dict[str, Any]


ChunkType = Literal["text", "tool_call", "done", "error"]


@dataclass(frozen=True)
class ChatChunk:
    type: ChunkType
    text: str = ""
    tool_call: ToolCall | None = None
    error: str | None = None


@dataclass
class ProviderStatus:
    name: str
    available: bool
    is_mock: bool
    model: str | None
    detail: str
    models: list[str] = field(default_factory=list)
    checked_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class LLMProvider(Protocol):
    name: str
    is_mock: bool
    model: str | None

    async def health(self) -> ProviderStatus: ...

    async def list_models(self) -> list[str]: ...

    def chat(
        self, messages: list[ChatMessage], tools: list[ToolSpec] | None = None, timeout_s: float = 120.0
    ) -> AsyncIterator[ChatChunk]: ...


class NoneProvider:
    """Dipakai saat ZOI_AI_PROVIDER=none. Jujur: AI tidak tersedia."""

    name = "none"
    is_mock = False
    model = None

    async def health(self) -> ProviderStatus:
        return ProviderStatus(name=self.name, available=False, is_mock=False, model=None,
                              detail="AI dinonaktifkan (ZOI_AI_PROVIDER=none).")

    async def list_models(self) -> list[str]:
        return []

    async def chat(
        self, messages: list[ChatMessage], tools: list[ToolSpec] | None = None, timeout_s: float = 120.0
    ) -> AsyncIterator[ChatChunk]:
        yield ChatChunk(type="error", error="AI tidak tersedia: ZOI_AI_PROVIDER=none.")
