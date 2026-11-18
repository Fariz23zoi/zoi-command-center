"""Thumbnail otomatis: AI Brain ZOI menulis teks hook, browser yang menyusun gambarnya.

AI hanya mengembalikan JSON terstruktur (baris teks + gaya dari daftar tetap). Komposisi (foto latar, kotak kertas,
coretan aksen) dilakukan di canvas browser — tanpa model gambar, tanpa unggah foto ke server, tanpa biaya.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.ai.structured import StructuredOutputError, chat_json
from app.core.errors import ZoiError
from app.providers.base import ChatMessage, LLMProvider

Ukuran = Literal["kecil", "sedang", "besar"]
Warna = Literal["hitam", "putih", "pink", "kuning"]
Kotak = Literal["putih", "kuning", "hitam", "tanpa"]


class HookLine(BaseModel):
    teks: str = Field(min_length=1, max_length=60)
    ukuran: Ukuran = "sedang"
    warna: Warna = "hitam"
    kotak: Kotak = "putih"


class ThumbnailHook(BaseModel):
    baris: list[HookLine] = Field(min_length=1, max_length=8)
    bubble: list[str] = Field(default_factory=list, max_length=3)
    aksen: Literal["pink", "kuning"] = "pink"


SYSTEM = """Kamu desainer thumbnail YouTube/Shorts Indonesia. Tulis TEKS HOOK yang membuat orang berhenti scroll.
Gaya contoh yang disukai pengguna:
- "Pernah nggak sih, kamu sebenarnya | NGGAK MAU, | tapi tetap bilang | IYA | karena nggak enakan?"
- "50 DANCER | KLIP?! | CERITA DI BALIK LAYAR" dengan bubble "GILA! 50 DANCER?!" dan "GAK MAIN-MAIN!"
Aturan:
- 3 sampai 6 baris, total paling banyak 16 kata. Bahasa Indonesia santai, jujur sesuai topik (tanpa klaim palsu).
- Tepat 1 atau 2 baris "besar" berisi kata kunci emosional/angka (huruf kapital, maksimal 3 kata, boleh ?! ).
- Baris "besar" pakai warna "pink" atau "kuning" dengan kotak "tanpa" atau "putih"; jangan warna sama dengan kotak.
- Baris lain "kecil"/"sedang", warna "hitam" di kotak "putih"/"kuning", atau warna "putih" di kotak "hitam".
- bubble: 0-2 seruan reaksi pendek (maksimal 4 kata) — kosongkan bila tidak cocok.
- aksen: "pink" atau "kuning".
Balas HANYA JSON: {"baris":[{"teks":"...","ukuran":"kecil|sedang|besar","warna":"hitam|putih|pink|kuning",
"kotak":"putih|kuning|hitam|tanpa"}],"bubble":["..."],"aksen":"pink|kuning"}"""


def _tidy(hook: ThumbnailHook) -> ThumbnailHook:
    """Perbaiki kombinasi yang tidak terbaca (teks sewarna kotaknya) tanpa mengubah kata dari AI."""
    lines: list[HookLine] = []
    for line in hook.baris[:6]:
        teks = " ".join(line.teks.split())[:60]
        if not teks:
            continue
        warna, kotak = line.warna, line.kotak
        if warna == kotak or (kotak == "tanpa" and warna in ("hitam", "putih")):
            warna = "putih" if kotak == "hitam" else ("pink" if kotak in ("kuning", "tanpa") else "hitam")
            if kotak == "tanpa" and line.ukuran != "besar":
                kotak = "putih"
                warna = "hitam"
        lines.append(HookLine(teks=teks, ukuran=line.ukuran, warna=warna, kotak=kotak))
    if not lines:
        raise ZoiError("AI ZOI tidak memberi teks hook.", status_code=502, code="ai_bad_json")
    bubble = [" ".join(b.split())[:30] for b in hook.bubble[:2] if b.strip()]
    return ThumbnailHook(baris=lines, bubble=bubble, aksen=hook.aksen)


async def thumbnail_hook(provider: LLMProvider, topik: str, rasio: str) -> dict[str, object]:
    bentuk = "vertikal 9:16 (Shorts/Reels)" if rasio == "9:16" else "horizontal 16:9 (video YouTube)"
    messages = [ChatMessage("system", SYSTEM),
                ChatMessage("user", f"Format thumbnail: {bentuk}.\nTopik / isi video:\n{topik.strip()}")]
    try:
        result = await chat_json(provider, messages, ThumbnailHook, timeout_s=180)
    except StructuredOutputError as exc:
        raise ZoiError(f"AI ZOI gagal membuat teks hook: {exc}", status_code=502, code="ai_failed") from exc
    hook = _tidy(result.value)
    return {**hook.model_dump(), "provider": result.served_by or provider.name,
            "is_mock": bool(getattr(provider, "is_mock", False))}
