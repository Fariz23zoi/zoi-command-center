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


@dataclass(frozen=True)
class CostGuard:
    extra_hosts: frozenset[str] = frozenset()
    recorder: AuditRecorder | None = None

    @classmethod
    def build(cls, *, ollama_url: str, extra_hosts: list[str], recorder: AuditRecorder | None) -> CostGuard:
        hosts = set(extra_hosts)
        ollama_host = urlparse(ollama_url).hostname
        if ollama_host:
            hosts.add(ollama_host.lower())
        return cls(extra_hosts=frozenset(hosts), recorder=recorder)

    def check(self, host: str) -> tuple[bool, str]:
        host = host.lower().strip("[]")
        if host in BLOCKED_HOSTS or host.endswith(BLOCKED_SUFFIXES):
            return False, "layanan berbayar/cloud dilarang (COST_CONTROL.md: NOT ALLOWED)"
        if host in LOCAL_HOSTS:
            return True, "localhost"
        if host in YOUTUBE_HOSTS:
            return True, "YouTube API resmi (gratis dengan kuota)"
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

        hooks = {"request": [hook]}
        return httpx.AsyncClient(event_hooks=hooks, trust_env=False, **kwargs)  # type: ignore[arg-type]

    def client(self, **kwargs: object) -> httpx.Client:
        def hook(request: httpx.Request) -> None:
            self.enforce(request.method, request.url)

        hooks = {"request": [hook]}
        return httpx.Client(event_hooks=hooks, trust_env=False, **kwargs)  # type: ignore[arg-type]
