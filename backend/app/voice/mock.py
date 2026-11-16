"""Suara Mock (hanya ZOI_MODE=development). Selalu berlabel MOCK, tanpa angka, tanpa audio sungguhan."""

from __future__ import annotations

import asyncio
import time

from app.voice.base import EngineStatus, Language, Transcript, VoiceError
from app.voice.wav import is_wav, tone_wav, wav_seconds

MOCK_TRANSCRIPT = "[MOCK] transkrip suara tiruan, bukan hasil pengenal suara"


class MockSTT:
    name = "mock"
    is_mock = True

    def __init__(self, latency_ms: int = 0) -> None:
        self.latency_s = latency_ms / 1000

    async def status(self) -> EngineStatus:
        return EngineStatus(self.name, True, True, "Mode development: transkrip adalah MOCK, bukan pengenal suara.",
                            model="mock")

    async def transcribe(self, audio: bytes, language: Language) -> Transcript:
        if not audio:
            raise VoiceError("Rekaman kosong.")
        start = time.monotonic()
        await asyncio.sleep(self.latency_s)
        seconds = wav_seconds(audio) if is_wav(audio) else None
        return Transcript(MOCK_TRANSCRIPT, None if language == "auto" else language, seconds,
                          round(time.monotonic() - start, 3), True)


class MockTTS:
    name = "mock"
    is_mock = True

    async def status(self) -> EngineStatus:
        return EngineStatus(self.name, True, True, "Mode development: suara adalah nada MOCK, bukan suara manusia.",
                            model="mock")

    async def synthesize(self, text: str, speed: float) -> bytes:
        # Durasi kira-kira sebanding panjang teks, agar antrean & lip-sync terasa wajar saat diuji.
        seconds = min(6.0, max(0.4, len(text) / 15.0)) / max(speed, 0.25)
        return tone_wav(seconds)
