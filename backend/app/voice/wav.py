"""Utilitas WAV kecil (tanpa dependensi)."""

from __future__ import annotations

import io
import math
import struct
import wave


def is_wav(data: bytes) -> bool:
    return len(data) > 44 and data[:4] == b"RIFF" and data[8:12] == b"WAVE"


def wav_seconds(data: bytes) -> float | None:
    try:
        with wave.open(io.BytesIO(data)) as w:
            return w.getnframes() / float(w.getframerate())
    except (wave.Error, EOFError, ZeroDivisionError):
        return None


def tone_wav(seconds: float, rate: int = 16_000) -> bytes:
    """Nada naik-turun (bukan suara manusia) — dipakai Mock TTS agar lip-sync & antrean audio bisa diuji."""
    frames = max(1, int(rate * seconds))
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        samples = bytearray()
        for i in range(frames):
            t = i / rate
            envelope = abs(math.sin(t * math.pi * 3.0))
            value = int(math.sin(2 * math.pi * 220 * t) * envelope * 9000)
            samples += struct.pack("<h", value)
        w.writeframes(bytes(samples))
    return buffer.getvalue()
