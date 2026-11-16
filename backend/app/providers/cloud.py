"""Penyedia AI CLOUD GRATIS bergaya OpenAI: NVIDIA NIM (utama) dan OpenRouter (cadangan).

Diizinkan atas keputusan pengguna (15 Nov 2026) — lihat docs/adr/0011. Aturan ZERO PAID tetap berlaku:
- Hanya dua host, dan hanya path inferensi/daftar model (dicek di sini DAN di Cost Guard).
- OpenRouter: model WAJIB berakhiran ':free'; permintaan lain ditolak sebelum dikirim.
- Hitungan permintaan sendiri, berhenti di bawah batas gratis.
- API key diambil dari penyimpanan rahasia saat dipakai; tidak pernah dicatat atau dikembalikan.
- Bila cadangan dipakai, potongan "done" membawa siapa yang sebenarnya menjawab dan alasannya.
"""

from __future__ import annotations

import json
import time
from collections import deque
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx

from app.db.models import AppMeta
from app.db.session import Database
from app.providers.base import (
    ChatChunk,
    ChatMessage,
    ChatOptions,
    ChatStats,
    LLMProvider,
    ProviderStatus,
    ToolCall,
    ToolSpec,
)
from app.security.cost_guard import CostGuard, CostGuardBlocked

CLOUD_CONTEXT_TOKENS = 16_384  # anggaran riwayat yang dikirim; bukan klaim tentang jendela konteks model
HEALTH_CACHE_S = 60.0
FREE_SUFFIX = ":free"
FALLBACK_KINDS = {"rate_limit", "server", "unreachable", "timeout"}


@dataclass(frozen=True)
class CloudSpec:
    name: str                 # "nvidia" | "openrouter"
    label: str
    base_url: str             # tanpa garis miring akhir, mis. https://integrate.api.nvidia.com/v1
    key_name: str             # nama entri di penyimpanan rahasia
    key_prefix: str
    per_minute: int           # batas aman ZOI (di bawah batas resmi)
    official_per_minute: int
    per_day: int | None
    official_per_day: int | None
    free_suffix_required: bool
    signup_url: str


NVIDIA = CloudSpec(name="nvidia", label="NVIDIA NIM", base_url="https://integrate.api.nvidia.com/v1",
                   key_name="nvidia_api_key", key_prefix="nvapi-", per_minute=30, official_per_minute=40,
                   per_day=None, official_per_day=None, free_suffix_required=False,
                   signup_url="https://build.nvidia.com")
OPENROUTER = CloudSpec(name="openrouter", label="OpenRouter", base_url="https://openrouter.ai/api/v1",
                       key_name="openrouter_api_key", key_prefix="sk-or-", per_minute=15, official_per_minute=20,
                       per_day=45, official_per_day=50, free_suffix_required=True,
                       signup_url="https://openrouter.ai")
SPECS = {NVIDIA.name: NVIDIA, OPENROUTER.name: OPENROUTER}
ALLOWED_PATH_ENDINGS = ("/chat/completions", "/models")


def spec_for(name: str, test_url: str = "") -> CloudSpec:
    spec = SPECS[name]
    if not test_url:
        return spec
    path = "/nvidia/v1" if name == "nvidia" else "/openrouter/api/v1"
    return CloudSpec(**{**spec.__dict__, "base_url": f"{test_url}{path}"})


class LimitReached(Exception):
    pass


class RequestLimiter:
    """Hitungan ZOI sendiri: jendela geser 60 detik (di memori) + hitungan harian UTC (di database)."""

    def __init__(self, db: Database, spec: CloudSpec, clock: Callable[[], float] = time.monotonic) -> None:
        self.db = db
        self.spec = spec
        self._clock = clock
        self._recent: deque[float] = deque()

    def _key(self) -> str:
        return f"cloud_requests:{self.spec.name}"

    @staticmethod
    def _today() -> str:
        return datetime.now(UTC).date().isoformat()

    def _day_count(self) -> int:
        with self.db.session() as s:
            row = s.get(AppMeta, self._key())
            data = json.loads(row.value_json) if row else {}
        return int(data.get("count", 0)) if data.get("day") == self._today() else 0

    def _minute_count(self) -> int:
        cutoff = self._clock() - 60.0
        while self._recent and self._recent[0] <= cutoff:
            self._recent.popleft()
        return len(self._recent)

    def acquire(self) -> None:
        if self._minute_count() >= self.spec.per_minute:
            raise LimitReached(f"Batas aman {self.spec.label} tercapai ({self.spec.per_minute} permintaan/menit). "
                               "Tunggu sebentar.")
        used = self._day_count()
        if self.spec.per_day is not None and used >= self.spec.per_day:
            raise LimitReached(f"Batas aman harian {self.spec.label} tercapai ({used}/{self.spec.per_day} "
                               "permintaan). Dihitung ulang tengah malam UTC.")
        self._recent.append(self._clock())
        with self.db.session() as s:
            row = s.get(AppMeta, self._key())
            value = json.dumps({"day": self._today(), "count": used + 1})
            if row is None:
                s.add(AppMeta(key=self._key(), value_json=value))
            else:
                row.value_json = value

    def status(self) -> dict[str, Any]:
        return {"source": "hitungan ZOI sendiri (bukan angka dari penyedia)",
                "minute_used": self._minute_count(), "minute_limit": self.spec.per_minute,
                "minute_official": self.spec.official_per_minute, "day_used": self._day_count(),
                "day_limit": self.spec.per_day, "day_official": self.spec.official_per_day}


def _error(kind: str, text: str) -> ChatChunk:
    return ChatChunk(type="error", error=text, error_kind=kind)


class OpenAICompatProvider:
    is_mock = False
    is_cloud = True

    def __init__(self, spec: CloudSpec, model: str, guard: CostGuard, key_getter: Callable[[], str | None],
                 limiter: RequestLimiter, *, is_test: bool = False) -> None:
        self.spec = spec
        self.name = spec.name
        self.model: str | None = model or None
        self.guard = guard
        self._key = key_getter
        self.limiter = limiter
        self.is_test = is_test
        self._health: tuple[float, ProviderStatus] | None = None

    # ── koneksi ───────────────────────────────────────────────────────────
    @staticmethod
    async def _only_inference(request: httpx.Request) -> None:
        if not request.url.path.endswith(ALLOWED_PATH_ENDINGS):
            raise CostGuardBlocked(request.url.host, f"path {request.url.path} tidak dipakai ZOI (hanya inferensi "
                                                     "dan daftar model)")

    def _client(self, timeout: float | httpx.Timeout) -> httpx.AsyncClient:
        return self.guard.async_client(timeout=timeout, event_hooks={"request": [self._only_inference]})

    def _headers(self) -> dict[str, str] | None:
        key = self._key()
        return {"Authorization": f"Bearer {key}"} if key else None

    def has_key(self) -> bool:
        return bool(self._key())

    def model_problem(self, model: str | None = None) -> str | None:
        model = model if model is not None else self.model
        if not model:
            return f"Model {self.spec.label} belum diisi di .env."
        if self.spec.free_suffix_required and not model.endswith(FREE_SUFFIX):
            return (f"Model OpenRouter harus berakhiran '{FREE_SUFFIX}' (model gratis). '{model}' ditolak agar "
                    "tidak ada permintaan berbayar.")
        return None

    def set_model(self, model: str | None) -> None:  # noqa: ARG002 — model cloud hanya dari .env (keputusan K-2)
        return None

    async def context_tokens(self) -> int:
        return CLOUD_CONTEXT_TOKENS

    def invalidate(self) -> None:
        self._health = None

    # ── informasi ─────────────────────────────────────────────────────────
    async def list_models(self) -> list[str]:
        headers = self._headers()
        if headers is None:
            return []
        async with self._client(10.0) as client:
            response = await client.get(f"{self.spec.base_url}/models", headers=headers)
            response.raise_for_status()
            data = response.json().get("data", [])
        ids = sorted({m["id"] for m in data if isinstance(m, dict) and isinstance(m.get("id"), str)})
        return [m for m in ids if m.endswith(FREE_SUFFIX)] if self.spec.free_suffix_required else ids

    async def health(self) -> ProviderStatus:
        if self._health and time.monotonic() - self._health[0] < HEALTH_CACHE_S:
            return self._health[1]
        status = await self._check()
        self._health = (time.monotonic(), status)
        return status

    async def _check(self) -> ProviderStatus:
        base = {"name": self.name, "is_mock": False, "model": self.model}
        label = self.spec.label
        if problem := self.model_problem():
            return ProviderStatus(available=False, detail=problem, **base)
        if not self.has_key():
            return ProviderStatus(available=False, **base,
                                  detail=f"API key {label} belum dimasukkan. Buka Settings › AI Cloud.")
        try:
            models = await self.list_models()
        except CostGuardBlocked as exc:
            return ProviderStatus(available=False, detail=str(exc), **base)
        except httpx.HTTPStatusError as exc:
            code = exc.response.status_code
            reason = "API key ditolak" if code in (401, 403) else f"HTTP {code}"
            return ProviderStatus(available=False, detail=f"{label} menolak permintaan ({reason}).", **base)
        except (httpx.HTTPError, ValueError) as exc:
            return ProviderStatus(available=False, **base,
                                  detail=f"{label} tidak dapat dihubungi ({type(exc).__name__}). Periksa internet.")
        if self.model not in models:
            return ProviderStatus(available=False, models=models, **base,
                                  detail=f"Model '{self.model}' tidak ada di daftar {label}. Periksa namanya.")
        return ProviderStatus(available=True, models=models, **base,
                              detail=f"AI cloud {label} siap (model muncul di daftar; pakai 'Uji model' untuk "
                                     "memastikan bisa dipanggil).")

    # ── percakapan ────────────────────────────────────────────────────────
    def _payload(self, messages: list[ChatMessage], tools: list[ToolSpec] | None,
                 options: ChatOptions | None) -> dict[str, Any]:
        sent = [{"role": m.role, "content": m.content} for m in messages]
        if options and options.json_schema is not None:
            # Tidak semua model cloud mendukung response_format; skema dikirim sebagai teks dan hasilnya divalidasi.
            sent.append({"role": "system", "content": "Balas HANYA dengan satu objek JSON yang mengikuti skema "
                                                      "JSON ini:\n" + json.dumps(options.json_schema,
                                                                                 ensure_ascii=False)})
        payload: dict[str, Any] = {"model": self.model, "stream": True, "messages": sent}
        if tools:
            payload["tools"] = [t.to_ollama() for t in tools]  # bentuk yang sama dengan OpenAI
        return payload

    async def chat(
        self, messages: list[ChatMessage], tools: list[ToolSpec] | None = None, timeout_s: float = 120.0,
        options: ChatOptions | None = None,
    ) -> AsyncIterator[ChatChunk]:
        label = self.spec.label
        if problem := self.model_problem():
            yield _error("config", problem)
            return
        headers = self._headers()
        if headers is None:
            yield _error("config", f"API key {label} belum dimasukkan. Buka Settings › AI Cloud.")
            return
        try:
            self.limiter.acquire()
        except LimitReached as exc:
            yield _error("rate_limit", str(exc))
            return

        timeout = httpx.Timeout(connect=10.0, read=timeout_s, write=30.0, pool=10.0)
        calls: dict[int, dict[str, str]] = {}
        stats: ChatStats | None = None
        finished = False
        started = time.monotonic()
        try:
            async with self._client(timeout) as client, client.stream(
                    "POST", f"{self.spec.base_url}/chat/completions", headers=headers,
                    json=self._payload(messages, tools, options)) as resp:
                if resp.status_code != 200:
                    body = (await resp.aread()).decode("utf-8", errors="replace")
                    yield self._http_error(resp.status_code, body)
                    return
                async for line in resp.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        finished = True
                        break
                    try:
                        event = json.loads(data)
                    except json.JSONDecodeError:
                        yield _error("server", f"{label} mengirim data yang tidak dapat dibaca.")
                        return
                    if isinstance(event.get("error"), dict):
                        yield _error("server", f"{label}: {str(event['error'].get('message', ''))[:300]}")
                        return
                    usage = event.get("usage")
                    if isinstance(usage, dict):
                        stats = ChatStats(prompt_tokens=_int(usage.get("prompt_tokens")),
                                          output_tokens=_int(usage.get("completion_tokens")),
                                          output_seconds=time.monotonic() - started)
                    for choice in event.get("choices") or []:
                        finished = finished or bool(choice.get("finish_reason"))
                        delta = choice.get("delta") or {}
                        thinking = delta.get("reasoning_content") or delta.get("reasoning")
                        if isinstance(thinking, str) and thinking:
                            yield ChatChunk(type="thinking", text=thinking)
                        if isinstance(delta.get("content"), str) and delta["content"]:
                            yield ChatChunk(type="text", text=delta["content"])
                        for raw in delta.get("tool_calls") or []:
                            slot = calls.setdefault(int(raw.get("index", 0)), {"name": "", "arguments": ""})
                            function = raw.get("function") or {}
                            slot["name"] += function.get("name") or ""
                            slot["arguments"] += function.get("arguments") or ""
                if not finished:
                    yield _error("server", f"Koneksi ke {label} terputus sebelum jawaban selesai.")
                    return
                for index in sorted(calls):
                    try:
                        arguments = json.loads(calls[index]["arguments"] or "{}")
                    except json.JSONDecodeError:
                        arguments = None
                    if not calls[index]["name"] or not isinstance(arguments, dict):
                        yield _error("server", "Format pemanggilan tool dari model tidak valid.")
                        return
                    yield ChatChunk(type="tool_call", tool_call=ToolCall(calls[index]["name"], arguments))
                yield ChatChunk(type="done", stats=stats)
        except CostGuardBlocked as exc:
            yield _error("config", str(exc))
        except httpx.TimeoutException:
            yield _error("timeout", f"timeout: {label} tidak mengirim apa pun selama {timeout_s:g} detik.")
        except httpx.HTTPError as exc:
            yield _error("unreachable", f"{label} tidak dapat dihubungi ({type(exc).__name__}). Periksa internet.")

    def _http_error(self, status: int, body: str) -> ChatChunk:
        label = self.spec.label
        try:
            parsed = json.loads(body)
            detail = parsed.get("error", parsed.get("detail", parsed.get("title", body)))
            if isinstance(detail, dict):
                detail = detail.get("message", detail)
        except (json.JSONDecodeError, AttributeError):
            detail = body
        detail = str(detail)[:300]
        if status in (401, 403):
            return _error("auth", f"{label} menolak API key ({status}). Periksa di Settings › AI Cloud.")
        if status == 402:
            return _error("payment", f"{label} meminta pembayaran ({status}). ZOI tidak memakai jalur berbayar.")
        if status == 429:
            return _error("rate_limit", f"{label}: batas permintaan gratis tercapai (429). {detail}")
        if status >= 500:
            return _error("server", f"{label} sedang bermasalah ({status}). {detail}")
        if status in (404, 410):
            return _error("model", f"{label} tidak bisa memanggil model '{self.model}' ({status}). Sebagian model "
                                   f"di daftar tidak tersedia untuk akun gratis. {detail}")
        return _error("request", f"{label} menolak permintaan ({status}): {detail}")

    # ── untuk halaman Settings › AI Cloud ────────────────────────────────
    def cloud_parts(self) -> list[OpenAICompatProvider]:
        return [self]


def _int(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


class FallbackProvider:
    """Utama → cadangan. Pindah hanya bila utama gagal SEBELUM mengirim apa pun, karena batas/galat server/jaringan.

    Tidak pindah untuk API key salah, model salah, atau permintaan ditolak — itu masalah pengaturan.
    """

    is_mock = False
    is_cloud = True

    def __init__(self, primary: OpenAICompatProvider, backup: OpenAICompatProvider) -> None:
        self.primary = primary
        self.backup = backup
        self.name = primary.name
        self.is_test = primary.is_test

    @property
    def model(self) -> str | None:
        return self.primary.model

    def set_model(self, model: str | None) -> None:  # noqa: ARG002
        return None

    async def context_tokens(self) -> int:
        return CLOUD_CONTEXT_TOKENS

    async def list_models(self) -> list[str]:
        return await self.primary.list_models()

    async def health(self) -> ProviderStatus:
        status = await self.primary.health()
        if status.available:
            return status
        backup = await self.backup.health()
        if backup.available and self.primary.has_key() and not self.primary.model_problem():
            # Utama tidak terjangkau tetapi cadangan siap → AI tetap tersedia, dan itu dikatakan terus terang.
            return ProviderStatus(name=self.name, available=True, is_mock=False, model=self.model,
                                  detail=f"{status.detail} Cadangan {self.backup.spec.label} siap dipakai.")
        return status

    async def chat(
        self, messages: list[ChatMessage], tools: list[ToolSpec] | None = None, timeout_s: float = 120.0,
        options: ChatOptions | None = None,
    ) -> AsyncIterator[ChatChunk]:
        emitted = False
        failure: ChatChunk | None = None
        async for chunk in self.primary.chat(messages, tools, timeout_s, options):
            if chunk.type == "error" and not emitted and chunk.error_kind in FALLBACK_KINDS:
                failure = chunk
                break
            emitted = True
            yield chunk
            if chunk.type in ("done", "error"):
                return
        if failure is None:
            return
        reason = failure.error or "gagal"
        note = f"Dijawab {self.backup.spec.label} (cadangan) karena {self.primary.spec.label} gagal: {reason}"
        async for chunk in self.backup.chat(messages, tools, timeout_s, options):
            if chunk.type == "error":
                yield _error(chunk.error_kind or "server",
                             f"{reason} — cadangan {self.backup.spec.label} juga gagal: {chunk.error}")
                return
            if chunk.type == "done":
                yield ChatChunk(type="done", stats=chunk.stats, served_by=self.backup.name,
                                served_model=self.backup.model, note=note)
                return
            yield chunk

    def cloud_parts(self) -> list[OpenAICompatProvider]:
        return [self.primary, self.backup]


def build_cloud(*, provider: str, fallback: str, models: dict[str, str], test_url: str, guard: CostGuard,
                db: Database, key_getter: Callable[[str], str | None]) -> LLMProvider:
    def make(name: str) -> OpenAICompatProvider:
        spec = spec_for(name, test_url)
        return OpenAICompatProvider(spec, models.get(name, ""), guard, lambda: key_getter(spec.key_name),
                                    RequestLimiter(db, spec), is_test=bool(test_url))

    primary = make(provider)
    return FallbackProvider(primary, make(fallback)) if fallback != "none" else primary
