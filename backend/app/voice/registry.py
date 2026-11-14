"""Satu-satunya tempat yang membuat mesin suara konkret."""

from __future__ import annotations

from app.config.modes import RuntimeConfig
from app.security.cost_guard import CostGuard
from app.voice.base import DisabledSTT, DisabledTTS, SpeechToText, TextToSpeech
from app.voice.mock import MockSTT, MockTTS
from app.voice.piper import PiperHttpTTS
from app.voice.whisper import WhisperSTT


def build_voice(runtime: RuntimeConfig, guard: CostGuard) -> tuple[SpeechToText, TextToSpeech]:
    stt: SpeechToText
    tts: TextToSpeech
    if runtime.stt == "mock":
        stt = MockSTT(min(runtime.mock_latency_ms, 1000))
    elif runtime.stt == "whisper":
        stt = WhisperSTT(runtime.whisper_model_dir)
    else:
        stt = DisabledSTT()
    if runtime.tts == "mock":
        tts = MockTTS()
    elif runtime.tts == "piper":
        tts = PiperHttpTTS(runtime.piper_url, guard)
    else:
        tts = DisabledTTS()
    return stt, tts
