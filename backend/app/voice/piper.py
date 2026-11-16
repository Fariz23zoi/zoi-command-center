"""Suara Piper lewat server HTTP Piper sendiri (proses terpisah, GPL-3.0). ZOI tidak mengimpor kode Piper.

Server dijalankan pengguna: `python -m piper.http_server -m id_ID-news_tts-medium` (port 5000).
"""

from __future__ import annotations

from typing import Any

import httpx

from app.security.cost_guard import CostGuard, CostGuardBlocked
from app.voice.base import EngineStatus, VoiceError
from app.voice.wav import is_wav

TIMEOUT = httpx.Timeout(connect=3.0, read=120.0, write=10.0, pool=3.0)
# Server Piper punya endpoint yang mengunduh suara dari internet. ZOI tidak pernah memanggilnya (keputusan K-2).
FORBIDDEN_PATHS = ("/download", "/all-voices")


class ForbiddenPiperCall(VoiceError):
    pass


async def _refuse_forbidden(request: httpx.Request) -> None:
    if request.url.path.startswith(FORBIDDEN_PATHS):
        raise ForbiddenPiperCall(f"ZOI tidak mengunduh suara ({request.url.path}). Pasang suara sendiri.")


class PiperHttpTTS:
    name = "piper"
    is_mock = False

    def __init__(self, base_url: str, guard: CostGuard, *, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.guard = guard
        self._transport = transport

    def _client(self) -> httpx.AsyncClient:
        kwargs: dict[str, Any] = {"base_url": self.base_url, "timeout": TIMEOUT,
                                  "event_hooks": {"request": [_refuse_forbidden]}}
        if self._transport is not None:
            kwargs["transport"] = self._transport
        return self.guard.async_client(**kwargs)

    async def status(self) -> EngineStatus:
        try:
            async with self._client() as client:
                response = await client.get("/voices")
                response.raise_for_status()
                voices = response.json()
        except CostGuardBlocked as exc:
            return EngineStatus(self.name, False, False, str(exc))
        except (httpx.HTTPError, ValueError) as exc:
            return EngineStatus(self.name, False, False,
                                f"Server Piper tidak dapat dihubungi di {self.base_url} ({type(exc).__name__}). "
                                "Jalankan deploy\\windows\\voice.ps1 atau python -m piper.http_server.")
        if isinstance(voices, dict):
            names = sorted(voices)
        elif isinstance(voices, list):
            names = [str(v) for v in voices]
        else:
            names = []
        return EngineStatus(self.name, False, True, "Server Piper siap.", model=", ".join(names[:3]) or None)

    async def synthesize(self, text: str, speed: float) -> bytes:
        payload = {"text": text, "length_scale": round(1.0 / max(speed, 0.25), 3)}
        try:
            async with self._client() as client:
                response = await client.post("/synthesize", json=payload)
        except CostGuardBlocked as exc:
            raise VoiceError(str(exc)) from exc
        except httpx.TimeoutException as exc:
            raise VoiceError("Piper terlalu lama membuat suara.") from exc
        except httpx.HTTPError as exc:
            raise VoiceError(f"Server Piper tidak dapat dihubungi di {self.base_url} ({type(exc).__name__}).") from exc
        if response.status_code != 200:
            raise VoiceError(f"Piper menolak permintaan ({response.status_code}).")
        if not is_wav(response.content):
            raise VoiceError("Piper tidak mengembalikan audio WAV.")
        return response.content
