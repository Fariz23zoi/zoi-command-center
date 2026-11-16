"""Pengenal suara faster-whisper (MIT). Paket opsional: `pip install -r requirements-voice.txt`.

ZOI TIDAK PERNAH mengunduh model: hanya memuat dari folder lokal (ZOI_WHISPER_MODEL_DIR) dengan
local_files_only=True. Audio diproses di memori lalu dibuang — tidak disimpan.
"""

from __future__ import annotations

import asyncio
import io
import threading
import time
from pathlib import Path
from typing import Any

from app.voice.base import MAX_AUDIO_SECONDS, EngineStatus, Language, Transcript, VoiceError

REQUIRED_FILES = ("model.bin", "config.json")


def missing_files(model_dir: Path) -> list[str]:
    return [name for name in REQUIRED_FILES if not (model_dir / name).is_file()]


class WhisperSTT:
    name = "whisper"
    is_mock = False

    def __init__(self, model_dir: Path | None, *, threads: int = 0) -> None:
        self.model_dir = model_dir
        self.threads = threads
        self._model: Any = None
        self._lock = threading.Lock()

    def _problem(self) -> str | None:
        try:
            import faster_whisper  # noqa: F401
        except ImportError:
            return ("Paket faster-whisper belum terpasang. Pasang: "
                    "backend\\.venv\\Scripts\\pip install -r backend\\requirements-voice.txt")
        if self.model_dir is None:
            return "ZOI_WHISPER_MODEL_DIR belum diisi. Lihat Settings › Suara untuk cara memasang model."
        if not self.model_dir.is_dir():
            return f"Folder model Whisper tidak ditemukan: {self.model_dir.name}"
        missing = missing_files(self.model_dir)
        if missing:
            return f"Folder model Whisper tidak lengkap (tidak ada {', '.join(missing)})."
        return None

    async def status(self) -> EngineStatus:
        problem = self._problem()
        model = self.model_dir.name if self.model_dir else None
        if problem:
            return EngineStatus(self.name, False, False, problem, model=model)
        loaded = "sudah dimuat" if self._model is not None else "dimuat saat pertama dipakai"
        return EngineStatus(self.name, False, True, f"faster-whisper siap ({loaded}).", model=model)

    def _load(self) -> Any:
        if self._model is None:
            from faster_whisper import WhisperModel

            self._model = WhisperModel(str(self.model_dir), device="cpu", compute_type="int8",
                                       cpu_threads=self.threads, local_files_only=True)
        return self._model

    def _run(self, audio: bytes, language: Language) -> Transcript:
        start = time.monotonic()
        with self._lock:  # satu transkripsi pada satu waktu: CPU lemah tidak dibebani berlipat
            model = self._load()
            segments, info = model.transcribe(io.BytesIO(audio), language=None if language == "auto" else language,
                                              beam_size=1, vad_filter=True)
            duration = float(getattr(info, "duration", 0.0) or 0.0)
            if duration > MAX_AUDIO_SECONDS + 1:
                raise VoiceError(f"Rekaman terlalu panjang ({duration:.0f} dtk). Maksimal {MAX_AUDIO_SECONDS:.0f} dtk.")
            text = " ".join(segment.text.strip() for segment in segments).strip()
        return Transcript(text, getattr(info, "language", None), round(duration, 2) or None,
                          round(time.monotonic() - start, 3), False)

    async def transcribe(self, audio: bytes, language: Language) -> Transcript:
        problem = self._problem()
        if problem:
            raise VoiceError(problem)
        try:
            return await asyncio.to_thread(self._run, audio, language)
        except VoiceError:
            raise
        except Exception as exc:  # noqa: BLE001 — format audio rusak dll. dilaporkan, tidak disembunyikan
            raise VoiceError(f"Rekaman tidak dapat dikenali ({type(exc).__name__}).") from exc
