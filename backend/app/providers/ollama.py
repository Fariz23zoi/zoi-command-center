"""Ollama Provider — dipakai di ZOI_MODE=local (atau Ollama di komputer lain di LAN).

- Semua koneksi lewat Cost Guard.
- ZOI TIDAK PERNAH mengunduh, menghapus, membuat, atau mengunggah model (keputusan pengguna, Phase 3 K-1).
  Endpoint tersebut diblokir di klien ini sendiri, bukan hanya tidak dipanggil.
- Model cloud Ollama ditolak: tag ':cloud' / '-cloud', atau entri yang membawa penanda remote.
- Angka (ukuran, RAM/VRAM, token/detik) hanya diteruskan dari Ollama; field yang tidak dilaporkan → None.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from dataclasses import asdict, dataclass, field
from typing import Any

import httpx

from app.providers.base import (
    DEFAULT_CONTEXT_TOKENS,
    ChatChunk,
    ChatMessage,
    ChatOptions,
    ChatStats,
    LLMProvider,
    ProviderStatus,
    ToolCall,
    ToolSpec,
    is_cloud_model,
)
from app.security.cost_guard import CostGuard, CostGuardBlocked

FORBIDDEN_PATHS = ("/api/pull", "/api/delete", "/api/push", "/api/create", "/api/copy", "/api/blobs")
# Jeda maksimal menunggu potongan berikutnya. Longgar karena memuat model ke RAM di CPU lambat bisa lama.
READ_TIMEOUT_S = 300.0


class ForbiddenOllamaCall(RuntimeError):
    pass


@dataclass
class InstalledModel:
    name: str
    size_bytes: int | None
    family: str | None
    parameter_size: str | None
    quantization: str | None
    modified_at: str | None
    is_cloud: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RunningModel:
    name: str
    size_bytes: int | None
    vram_bytes: int | None
    context_tokens: int | None
    expires_at: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ModelDetails:
    name: str
    capabilities: list[str] = field(default_factory=list)
    context_tokens: int | None = None
    architecture: str | None = None
    parameter_size: str | None = None
    quantization: str | None = None
    license_line: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _int(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def _str(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


class OllamaProvider:
    name = "ollama"
    is_mock = False

    def __init__(
        self,
        base_url: str,
        model: str,
        guard: CostGuard,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        health_timeout_s: float = 3.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model: str | None = model or None
        self.guard = guard
        self._transport = transport
        self._health_timeout_s = health_timeout_s
        self._details: dict[str, ModelDetails] = {}

    # ── koneksi ────────────────────────────────────────────────────────────
    def _client(self, timeout: float | httpx.Timeout) -> httpx.AsyncClient:
        kwargs: dict[str, Any] = {"base_url": self.base_url, "timeout": timeout,
                                  "event_hooks": {"request": [self._refuse_forbidden]}}
        if self._transport is not None:
            kwargs["transport"] = self._transport
        return self.guard.async_client(**kwargs)

    @staticmethod
    async def _refuse_forbidden(request: httpx.Request) -> None:
        if request.url.path.startswith(FORBIDDEN_PATHS):
            raise ForbiddenOllamaCall(f"ZOI tidak mengelola file model ({request.url.path}). "
                                      "Jalankan perintah ollama sendiri.")

    def set_model(self, model: str | None) -> None:
        self.model = model or None

    def with_model(self, model: str) -> LLMProvider:
        return OllamaProvider(self.base_url, model, self.guard, transport=self._transport,
                              health_timeout_s=self._health_timeout_s)

    # ── informasi ─────────────────────────────────────────────────────────
    async def version(self) -> str | None:
        async with self._client(self._health_timeout_s) as client:
            response = await client.get("/api/version")
            response.raise_for_status()
            return _str(response.json().get("version"))

    async def installed(self) -> list[InstalledModel]:
        async with self._client(self._health_timeout_s) as client:
            response = await client.get("/api/tags")
            response.raise_for_status()
            entries = response.json().get("models", [])
        result = []
        for entry in entries if isinstance(entries, list) else []:
            name = _str(entry.get("name")) if isinstance(entry, dict) else None
            if not name:
                continue
            details = entry.get("details") if isinstance(entry.get("details"), dict) else {}
            result.append(InstalledModel(
                name=name, size_bytes=_int(entry.get("size")), family=_str(details.get("family")),
                parameter_size=_str(details.get("parameter_size")),
                quantization=_str(details.get("quantization_level")),
                modified_at=_str(entry.get("modified_at")), is_cloud=is_cloud_model(name, entry),
            ))
        return sorted(result, key=lambda m: m.name)

    async def list_models(self) -> list[str]:
        return [m.name for m in await self.installed()]

    async def running(self) -> list[RunningModel]:
        async with self._client(self._health_timeout_s) as client:
            response = await client.get("/api/ps")
            response.raise_for_status()
            entries = response.json().get("models", [])
        return [
            RunningModel(name=_str(e.get("name")) or _str(e.get("model")) or "?", size_bytes=_int(e.get("size")),
                         vram_bytes=_int(e.get("size_vram")), context_tokens=_int(e.get("context_length")),
                         expires_at=_str(e.get("expires_at")))
            for e in (entries if isinstance(entries, list) else []) if isinstance(e, dict)
        ]

    async def show(self, model: str) -> ModelDetails:
        async with self._client(self._health_timeout_s * 3) as client:
            response = await client.post("/api/show", json={"model": model})
            response.raise_for_status()
            data = response.json()
        details = data.get("details") if isinstance(data.get("details"), dict) else {}
        info = data.get("model_info") if isinstance(data.get("model_info"), dict) else {}
        arch = _str(info.get("general.architecture"))
        context = _int(info.get(f"{arch}.context_length")) if arch else None
        if context is None:
            context = next((_int(v) for k, v in info.items() if k.endswith(".context_length")), None)
        caps = data.get("capabilities")
        license_text = _str(data.get("license"))
        result = ModelDetails(
            name=model,
            capabilities=[c for c in caps if isinstance(c, str)] if isinstance(caps, list) else [],
            context_tokens=context, architecture=arch,
            parameter_size=_str(details.get("parameter_size")), quantization=_str(details.get("quantization_level")),
            license_line=license_text.strip().splitlines()[0][:160] if license_text and license_text.strip() else None,
        )
        self._details[model] = result
        return result

    async def _cached_details(self, model: str) -> ModelDetails | None:
        if model in self._details:
            return self._details[model]
        try:
            return await self.show(model)
        except (httpx.HTTPError, ValueError, CostGuardBlocked):
            return None

    async def context_tokens(self) -> int:
        """Jendela konteks yang dipakai: dari /api/ps bila model sedang dimuat, selain itu default Ollama."""
        if not self.model:
            return DEFAULT_CONTEXT_TOKENS
        try:
            for running in await self.running():
                if running.name == self.model and running.context_tokens:
                    return running.context_tokens
        except (httpx.HTTPError, ValueError, CostGuardBlocked):
            pass
        details = await self._cached_details(self.model)
        maximum = details.context_tokens if details and details.context_tokens else DEFAULT_CONTEXT_TOKENS
        return min(maximum, DEFAULT_CONTEXT_TOKENS)

    async def unload(self, model: str) -> None:
        """Melepas model dari RAM/VRAM (keep_alive 0). Tidak menghapus file model."""
        async with self._client(self._health_timeout_s * 10) as client:
            response = await client.post("/api/generate", json={"model": model, "keep_alive": 0})
            response.raise_for_status()

    async def validate_choice(self, model: str) -> str | None:
        """None bila model boleh dipakai; selain itu alasan penolakan (Bahasa Indonesia)."""
        if is_cloud_model(model):
            return "Model cloud Ollama tidak diizinkan. Pilih model lokal."
        installed = {m.name: m for m in await self.installed()}
        if model not in installed:
            return (f"Model '{model}' belum terpasang di Ollama. ZOI tidak mengunduh model; "
                    f"jalankan sendiri: ollama pull {model}")
        if installed[model].is_cloud:
            return "Model ini dijalankan di cloud Ollama, bukan di komputer ini. Tidak diizinkan."
        details = await self.show(model)
        if details.capabilities and "completion" not in details.capabilities:
            caps = ", ".join(details.capabilities)
            return f"Model '{model}' tidak bisa dipakai untuk percakapan (kemampuan: {caps})."
        return None

    async def health(self) -> ProviderStatus:
        base = {"name": self.name, "is_mock": False, "model": self.model}
        try:
            version = await self.version()
            models = await self.list_models()
        except CostGuardBlocked as exc:
            return ProviderStatus(available=False, detail=str(exc), **base)
        except (httpx.HTTPError, ValueError) as exc:
            return ProviderStatus(
                available=False, **base,
                detail=f"Ollama tidak dapat dihubungi di {self.base_url} ({type(exc).__name__}). "
                       "Pastikan aplikasi Ollama berjalan.",
            )
        if not self.model:
            return ProviderStatus(available=False, models=models, **base,
                                  detail=f"Ollama {version} aktif, tetapi belum ada model aktif. "
                                         "Pilih di Settings › AI Lokal atau isi ZOI_OLLAMA_MODEL.")
        if is_cloud_model(self.model):
            return ProviderStatus(available=False, models=models, **base,
                                  detail="Model cloud Ollama tidak diizinkan. Pilih model lokal.")
        if self.model not in models:
            return ProviderStatus(
                available=False, models=models, **base,
                detail=f"Model '{self.model}' belum terpasang di Ollama. ZOI tidak mengunduh model otomatis; "
                       f"jalankan sendiri: ollama pull {self.model}",
            )
        return ProviderStatus(available=True, models=models, **base, detail=f"Ollama {version} siap.")

    # ── percakapan ────────────────────────────────────────────────────────
    async def chat(
        self, messages: list[ChatMessage], tools: list[ToolSpec] | None = None, timeout_s: float = READ_TIMEOUT_S,
        options: ChatOptions | None = None,
    ) -> AsyncIterator[ChatChunk]:
        if not self.model:
            yield ChatChunk(type="error", error="AI tidak tersedia: belum ada model aktif.")
            return
        if is_cloud_model(self.model):
            yield ChatChunk(type="error", error="Model cloud Ollama tidak diizinkan.")
            return

        payload: dict[str, Any] = {
            "model": self.model,
            "stream": True,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
        }
        if tools:
            payload["tools"] = [t.to_ollama() for t in tools]
        if options and options.json_schema is not None:
            payload["format"] = options.json_schema
        details = await self._cached_details(self.model)
        thinking_model = bool(details and "thinking" in details.capabilities)
        if thinking_model:
            # Proses berpikir dikirim terpisah dan tidak dicampur ke jawaban. Untuk JSON, berpikir dimatikan.
            payload["think"] = not (options and options.json_schema is not None)

        timeout = httpx.Timeout(connect=5.0, read=timeout_s, write=30.0, pool=5.0)
        tags = _ThinkTagSplitter()
        try:
            async with self._client(timeout) as client, client.stream("POST", "/api/chat", json=payload) as resp:
                if resp.status_code != 200:
                    body = (await resp.aread()).decode("utf-8", errors="replace")
                    try:
                        detail = json.loads(body).get("error", body)
                    except (json.JSONDecodeError, AttributeError):
                        detail = body
                    yield ChatChunk(type="error",
                                    error=f"Ollama menolak permintaan ({resp.status_code}): {str(detail)[:300]}")
                    return
                async for line in resp.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        yield ChatChunk(type="error", error="Ollama mengirim data yang tidak dapat dibaca.")
                        return
                    if data.get("error"):
                        yield ChatChunk(type="error", error=f"Ollama: {data['error']}")
                        return
                    message = data.get("message") or {}
                    if message.get("thinking"):
                        yield ChatChunk(type="thinking", text=message["thinking"])
                    for raw in message.get("tool_calls") or []:
                        call = _parse_tool_call(raw)
                        if call is None:
                            yield ChatChunk(type="error", error="Format pemanggilan tool dari model tidak valid.")
                            return
                        yield ChatChunk(type="tool_call", tool_call=call)
                    if message.get("content"):
                        # Sebagian model menulis <think>…</think> di isi jawaban; dipisahkan di sini.
                        for kind, text in tags.feed(message["content"]):
                            yield ChatChunk(type=kind, text=text)
                    if data.get("done"):
                        for kind, text in tags.flush():
                            yield ChatChunk(type=kind, text=text)
                        yield ChatChunk(type="done", stats=_stats(data))
                        return
                yield ChatChunk(type="error", error="Koneksi ke Ollama terputus sebelum jawaban selesai.")
        except ForbiddenOllamaCall as exc:
            yield ChatChunk(type="error", error=str(exc))
        except CostGuardBlocked as exc:
            yield ChatChunk(type="error", error=str(exc))
        except httpx.TimeoutException:
            yield ChatChunk(type="error", error=f"timeout: Ollama tidak mengirim apa pun selama {timeout_s:g} detik.")
        except httpx.HTTPError as exc:
            yield ChatChunk(type="error", error=f"Ollama tidak dapat dihubungi ({type(exc).__name__}).")


class _ThinkTagSplitter:
    """Memisahkan <think>…</think> yang ditulis model di dalam content, walau tag terpotong antar-chunk."""

    OPEN, CLOSE = "<think>", "</think>"

    def __init__(self) -> None:
        self.buffer = ""
        self.inside = False

    def feed(self, text: str) -> list[tuple[str, str]]:
        self.buffer += text
        out: list[tuple[str, str]] = []
        while self.buffer:
            tag = self.CLOSE if self.inside else self.OPEN
            index = self.buffer.find(tag)
            if index >= 0:
                if index:
                    out.append(("thinking" if self.inside else "text", self.buffer[:index]))
                self.buffer = self.buffer[index + len(tag):]
                self.inside = not self.inside
                continue
            keep = _partial_suffix(self.buffer, tag)
            emit = self.buffer[:len(self.buffer) - keep]
            if emit:
                out.append(("thinking" if self.inside else "text", emit))
            self.buffer = self.buffer[len(self.buffer) - keep:]
            break
        return out

    def flush(self) -> list[tuple[str, str]]:
        rest, self.buffer = self.buffer, ""
        return [("thinking" if self.inside else "text", rest)] if rest else []


def _partial_suffix(text: str, tag: str) -> int:
    for size in range(min(len(tag) - 1, len(text)), 0, -1):
        if tag.startswith(text[-size:]):
            return size
    return 0


def _stats(data: dict[str, Any]) -> ChatStats:
    duration = _int(data.get("eval_duration"))
    return ChatStats(prompt_tokens=_int(data.get("prompt_eval_count")), output_tokens=_int(data.get("eval_count")),
                     output_seconds=duration / 1e9 if duration else None)


def _parse_tool_call(raw: Any) -> ToolCall | None:
    if not isinstance(raw, dict):
        return None
    function = raw.get("function")
    if not isinstance(function, dict) or not isinstance(function.get("name"), str):
        return None
    arguments = function.get("arguments", {})
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except json.JSONDecodeError:
            return None
    if not isinstance(arguments, dict):
        return None
    return ToolCall(name=function["name"], arguments=arguments)
