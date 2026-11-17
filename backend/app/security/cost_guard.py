"""Cost Guard — satu-satunya pintu keluar jaringan ZOI.

Hanya host di allowlist yang boleh dihubungi. Layanan AI berbayar diblokir eksplisit,
bahkan jika ditambahkan ke ZOI_EXTRA_ALLOWED_HOSTS. Setiap percobaan dicatat.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx

LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}

# Host resmi YouTube/Google yang gratis (dipakai mulai Phase 6). Daftar EKSAK, bukan wildcard
# googleapis.com — karena generativelanguage.googleapis.com (Gemini API) juga berada di domain itu.
YOUTUBE_HOSTS = {
    "www.googleapis.com",
    "youtube.googleapis.com",
    "youtubeanalytics.googleapis.com",
    "oauth2.googleapis.com",
    "accounts.google.com",
}

# Update ZOI dari GitHub Releases (gratis, publik). Hanya dipakai layanan update (ADR 0017).
UPDATE_HOSTS = {"api.github.com", "github.com", "objects.githubusercontent.com",
                "release-assets.githubusercontent.com"}

# Diblokir selalu (layanan AI/voice/clipping berbayar & model cloud).
BLOCKED_HOSTS = {
    "api.openai.com",
    "api.anthropic.com",
    "generativelanguage.googleapis.com",
    "aiplatform.googleapis.com",
    "api.elevenlabs.io",
    "api.deepgram.com",
    "api.muapi.ai",
    "api.groq.com",
    "api.mistral.ai",
    "api.cohere.ai",
    "openrouter.ai",
    "ollama.com",
    "api.ollama.com",
}
BLOCKED_SUFFIXES = (
    ".cognitiveservices.azure.com",
    ".openai.azure.com",
    ".tts.speech.microsoft.com",
    ".stt.speech.microsoft.com",
)

AuditRecorder = Callable[[str, str, str, bool, str], None]  # host, method, path, allowed, reason


class CostGuardBlocked(Exception):
    def __init__(self, host: str, reason: str) -> None:
        super().__init__(f"Cost Guard memblokir koneksi ke {host}: {reason}")
        self.host = host
        self.reason = reason


# AI cloud GRATIS yang diizinkan pengguna (ADR 0011). Host ini HANYA dibuka bila penyedianya dipilih di .env;
# selain itu tetap diblokir. Tidak bisa ditambah lewat ZOI_EXTRA_ALLOWED_HOSTS.
CLOUD_AI_HOSTS = {"integrate.api.nvidia.com", "openrouter.ai"}


@dataclass(frozen=True)
class CostGuard:
    extra_hosts: frozenset[str] = frozenset()
    cloud_hosts: frozenset[str] = frozenset()
    recorder: AuditRecorder | None = None

    @classmethod
    def build(cls, *, ollama_url: str, extra_hosts: list[str], recorder: AuditRecorder | None,
              cloud_hosts: list[str] | None = None) -> CostGuard:
        hosts = set(extra_hosts)
        ollama_host = urlparse(ollama_url).hostname
        if ollama_host:
            hosts.add(ollama_host.lower())
        unknown = set(cloud_hosts or []) - CLOUD_AI_HOSTS
        if unknown:
            raise ValueError(f"Host AI cloud tidak dikenal: {sorted(unknown)}")
        return cls(extra_hosts=frozenset(hosts), cloud_hosts=frozenset(cloud_hosts or []), recorder=recorder)

    def check(self, host: str) -> tuple[bool, str]:
        host = host.lower().strip("[]")
        if host in self.cloud_hosts:
            return True, "AI cloud gratis yang dipilih pengguna di .env (ADR 0011)"
        if host in CLOUD_AI_HOSTS:
            return False, "AI cloud tidak diaktifkan di .env (ZOI_AI_PROVIDER / ZOI_AI_FALLBACK)"
        if host in BLOCKED_HOSTS or host.endswith(BLOCKED_SUFFIXES):
            return False, "layanan berbayar/cloud dilarang (COST_CONTROL.md: NOT ALLOWED)"
        if host in LOCAL_HOSTS:
            return True, "localhost"
        if host in YOUTUBE_HOSTS:
            return True, "YouTube API resmi (gratis dengan kuota)"
        if host in UPDATE_HOSTS:
            return True, "update ZOI dari GitHub Releases (gratis)"
        if host in self.extra_hosts:
            return True, "diizinkan lewat konfigurasi"
        return False, "host tidak ada di allowlist"

    def enforce(self, method: str, url: httpx.URL | str) -> None:
        parsed = httpx.URL(str(url))
        host = parsed.host or ""
        allowed, reason = self.check(host)
        if self.recorder is not None:
            self.recorder(host, method.upper(), parsed.path or "/", allowed, reason)
        if not allowed:
            raise CostGuardBlocked(host, reason)

    def async_client(self, **kwargs: object) -> httpx.AsyncClient:
        async def hook(request: httpx.Request) -> None:
            self.enforce(request.method, request.url)

        # Hook Cost Guard selalu dijalankan PERTAMA; hook tambahan dari pemanggil tidak bisa menggantikannya.
        extra = kwargs.pop("event_hooks", None) or {}
        hooks = {"request": [hook, *extra.get("request", [])], "response": list(extra.get("response", []))}  # type: ignore[union-attr]
        return httpx.AsyncClient(event_hooks=hooks, trust_env=False, **kwargs)  # type: ignore[arg-type]

    def client(self, **kwargs: object) -> httpx.Client:
        def hook(request: httpx.Request) -> None:
            self.enforce(request.method, request.url)

        hooks = {"request": [hook]}
        return httpx.Client(event_hooks=hooks, trust_env=False, **kwargs)  # type: ignore[arg-type]
