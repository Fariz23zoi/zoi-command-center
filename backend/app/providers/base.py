"""Antarmuka penyedia AI. Mock dan Ollama mengimplementasikan kontrak yang SAMA.

Kontrak chat(): selalu menghasilkan aliran ChatChunk dan diakhiri tepat satu chunk "done" atau "error".
Kegagalan (timeout, server mati, format rusak) dilaporkan sebagai chunk "error" — bukan exception —
agar UI selalu bisa menampilkan alasannya.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal, Protocol, runtime_checkable

Role = Literal["system", "user", "assistant", "tool"]

# Ollama memakai jendela konteks 4096 token bila tidak diatur (num_ctx). ZOI tidak mengubahnya agar RAM tetap kecil.
DEFAULT_CONTEXT_TOKENS = 4096


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


ChunkType = Literal["text", "thinking", "tool_call", "done", "error"]


@dataclass(frozen=True)
class ChatStats:
    """Angka dari penyedia AI itu sendiri (Ollama: eval_count/eval_duration). Mock tidak pernah mengisinya."""

    prompt_tokens: int | None = None
    output_tokens: int | None = None
    output_seconds: float | None = None

    @property
    def tokens_per_second(self) -> float | None:
        if not self.output_tokens or not self.output_seconds:
            return None
        return self.output_tokens / self.output_seconds


@dataclass(frozen=True)
class ChatChunk:
    type: ChunkType
    text: str = ""
    tool_call: ToolCall | None = None
    error: str | None = None
    stats: ChatStats | None = None
    # Jenis kegagalan (penyedia cloud): rate_limit|server|unreachable|timeout|auth|payment|model|request|config.
    error_kind: str | None = None
    # Diisi pada potongan "done" bila yang menjawab BUKAN penyedia utama (cadangan), beserta alasannya.
    served_by: str | None = None
    served_model: str | None = None
    note: str | None = None


@dataclass(frozen=True)
class ChatOptions:
    """Opsi tambahan per permintaan. `json_schema` → keluaran terstruktur (format JSON schema)."""

    json_schema: dict[str, Any] | None = None
    context_tokens: int | None = None


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
        self, messages: list[ChatMessage], tools: list[ToolSpec] | None = None, timeout_s: float = 120.0,
        options: ChatOptions | None = None,
    ) -> AsyncIterator[ChatChunk]: ...

    def set_model(self, model: str | None) -> None: ...

    async def context_tokens(self) -> int: ...


def is_cloud_model(model: str, entry: dict[str, Any] | None = None) -> bool:
    """Model cloud Ollama (dijalankan di server Ollama, bukan di komputer ini) selalu ditolak."""
    if ":cloud" in model or model.endswith("-cloud"):
        return True
    return bool(entry and any(entry.get(k) for k in ("remote_model", "remote_host")))


class ModelInfo(Protocol):
    def to_dict(self) -> dict[str, Any]: ...


@runtime_checkable
class LocalModelAdmin(Protocol):
    """Kemampuan tambahan penyedia AI lokal (Ollama): membaca model & memilih model. TIDAK ada unduh/hapus."""

    base_url: str
    model: str | None

    async def version(self) -> str | None: ...

    async def installed(self) -> list[Any]: ...

    async def running(self) -> list[Any]: ...

    async def show(self, model: str) -> Any: ...

    async def unload(self, model: str) -> None: ...

    async def validate_choice(self, model: str) -> str | None: ...

    async def health(self) -> ProviderStatus: ...

    def set_model(self, model: str | None) -> None: ...

    def with_model(self, model: str) -> LLMProvider:
        """Instance baru dengan koneksi yang sama tetapi model berbeda (untuk uji model)."""
        ...


@runtime_checkable
class CloudAdmin(Protocol):
    """Penyedia AI cloud (NVIDIA NIM / OpenRouter). `cloud_parts()` → penyedia utama lalu cadangan (bila ada)."""

    is_cloud: bool
    is_test: bool

    def cloud_parts(self) -> list[Any]: ...


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

    def set_model(self, model: str | None) -> None:  # noqa: ARG002 — tidak ada model
        return None

    async def context_tokens(self) -> int:
        return DEFAULT_CONTEXT_TOKENS

    async def chat(
        self, messages: list[ChatMessage], tools: list[ToolSpec] | None = None, timeout_s: float = 120.0,
        options: ChatOptions | None = None,
    ) -> AsyncIterator[ChatChunk]:
        yield ChatChunk(type="error", error="AI tidak tersedia: ZOI_AI_PROVIDER=none.")
