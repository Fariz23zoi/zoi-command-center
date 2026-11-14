"""Kontrak suara. Kode di luar app/voice hanya mengenal Protocol ini, bukan mesin konkretnya."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal, Protocol

Language = Literal["id", "en", "auto"]

# Batas agar satu permintaan tidak menghabiskan RAM/CPU mesin lemah.
MAX_AUDIO_BYTES = 10 * 1024 * 1024
MAX_AUDIO_SECONDS = 60.0
MAX_TTS_CHARS = 600


class VoiceError(RuntimeError):
    """Kegagalan yang dilaporkan apa adanya ke pengguna (Bahasa Indonesia)."""


@dataclass(frozen=True)
class EngineStatus:
    name: str
    is_mock: bool
    available: bool
    detail: str
    model: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Transcript:
    text: str
    language: str | None
    audio_seconds: float | None
    elapsed_seconds: float
    is_mock: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SpeechToText(Protocol):
    name: str
    is_mock: bool

    async def status(self) -> EngineStatus: ...

    async def transcribe(self, audio: bytes, language: Language) -> Transcript: ...


class TextToSpeech(Protocol):
    name: str
    is_mock: bool

    async def status(self) -> EngineStatus: ...

    async def synthesize(self, text: str, speed: float) -> bytes:
        """WAV. `speed` 1.0 = normal, 1.5 = lebih cepat."""
        ...


class DisabledSTT:
    name = "none"
    is_mock = False

    async def status(self) -> EngineStatus:
        return EngineStatus(self.name, False, False, "Input suara dinonaktifkan (ZOI_STT=none).")

    async def transcribe(self, audio: bytes, language: Language) -> Transcript:
        raise VoiceError("Input suara dinonaktifkan (ZOI_STT=none).")


class DisabledTTS:
    name = "none"
    is_mock = False

    async def status(self) -> EngineStatus:
        return EngineStatus(self.name, False, False,
                            "Suara Piper dinonaktifkan (ZOI_TTS=none). Suara Windows tetap bisa dipakai.")

    async def synthesize(self, text: str, speed: float) -> bytes:
        raise VoiceError("Suara Piper dinonaktifkan (ZOI_TTS=none).")
