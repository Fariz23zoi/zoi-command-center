"""Layanan suara: satu-satunya tempat yang memilih mesin suara & menegakkan aturan (batas, lisensi Piper)."""

from __future__ import annotations

import json
from functools import cache
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.db.models import AppMeta
from app.db.session import Database
from app.voice.base import (
    MAX_AUDIO_BYTES,
    MAX_TTS_CHARS,
    Language,
    SpeechToText,
    TextToSpeech,
    VoiceError,
)

PREF_KEY = "voice_preferences"
CATALOG = Path(__file__).resolve().parent / "catalog.json"


class VoicePreferences(BaseModel):
    """Preferensi suara portabel (ikut ekspor). Bukan konfigurasi mesin."""

    model_config = ConfigDict(extra="forbid")
    language: Literal["id", "en", "auto"] = "id"
    speak_replies: bool = False
    auto_send: bool = False
    tts_engine: Literal["auto", "piper", "browser"] = "auto"
    browser_voice: str | None = Field(default=None, max_length=200)
    speech_rate: float = Field(default=1.0, ge=0.5, le=2.0)
    piper_license_accepted: bool = False


@cache
def load_catalog() -> dict[str, Any]:
    return json.loads(CATALOG.read_text(encoding="utf-8"))


class VoiceService:
    def __init__(self, *, stt: SpeechToText, tts: TextToSpeech, db: Database) -> None:
        self.stt = stt
        self.tts = tts
        self.db = db

    # ── preferensi ────────────────────────────────────────────────────────
    def preferences(self) -> VoicePreferences:
        with self.db.session() as s:
            row = s.get(AppMeta, PREF_KEY)
            return VoicePreferences.model_validate_json(row.value_json) if row else VoicePreferences()

    def save_preferences(self, prefs: VoicePreferences) -> VoicePreferences:
        with self.db.session() as s:
            row = s.get(AppMeta, PREF_KEY)
            if row is None:
                s.add(AppMeta(key=PREF_KEY, value_json=prefs.model_dump_json()))
            else:
                row.value_json = prefs.model_dump_json()
        return prefs

    # ── status ────────────────────────────────────────────────────────────
    async def status(self) -> dict[str, Any]:
        stt, tts = await self.stt.status(), await self.tts.status()
        prefs = self.preferences()
        return {"stt": stt.to_dict(), "tts": tts.to_dict(), "preferences": prefs.model_dump(),
                "reply_engine": self.reply_engine(prefs, tts_available=tts.available),
                "catalog": load_catalog(), "can_download": False, "stores_recordings": False}

    def reply_engine(self, prefs: VoicePreferences, *, tts_available: bool) -> Literal["piper", "browser"]:
        """Mesin yang membacakan jawaban. Piper hanya bila tersedia dan (untuk Piper asli) lisensinya diterima."""
        piper_ok = tts_available and (self.tts.is_mock or prefs.piper_license_accepted)
        if prefs.tts_engine == "browser":
            return "browser"
        return "piper" if piper_ok else "browser"

    # ── operasi ───────────────────────────────────────────────────────────
    async def transcribe(self, audio: bytes, language: Language | None) -> dict[str, Any]:
        if not audio:
            raise VoiceError("Rekaman kosong.")
        if len(audio) > MAX_AUDIO_BYTES:
            raise VoiceError(f"Rekaman terlalu besar (maks. {MAX_AUDIO_BYTES // (1024 * 1024)} MB).")
        result = await self.stt.transcribe(audio, language or self.preferences().language)
        return result.to_dict()

    async def speak(self, text: str) -> bytes:
        text = " ".join(text.split())
        if not text:
            raise VoiceError("Tidak ada teks untuk dibacakan.")
        if len(text) > MAX_TTS_CHARS:
            raise VoiceError(f"Teks terlalu panjang untuk sekali bicara (maks. {MAX_TTS_CHARS} karakter).")
        prefs = self.preferences()
        if not self.tts.is_mock and not prefs.piper_license_accepted:
            raise VoiceError("Suara Piper belum diaktifkan: baca dan terima catatan lisensinya di Settings › Suara.")
        return await self.tts.synthesize(text, prefs.speech_rate)
