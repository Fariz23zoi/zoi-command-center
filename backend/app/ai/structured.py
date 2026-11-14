"""Keluaran terstruktur: JSON schema dikirim ke penyedia AI, hasil divalidasi Pydantic, 1× percobaan ulang.

Model kecil sering membungkus JSON dengan teks atau ```json; parser toleran mengambil objek JSON pertama yang utuh.
Tidak ada nilai yang ditebak: bila tetap tidak valid, hasilnya error yang jujur.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from pydantic import BaseModel, ValidationError

from app.providers.base import ChatMessage, ChatOptions, ChatStats, LLMProvider

MAX_ATTEMPTS = 2


class StructuredOutputError(RuntimeError):
    pass


@dataclass
class StructuredResult[T: BaseModel]:
    value: T
    attempts: int
    raw: str
    stats: ChatStats | None


def extract_json(text: str) -> str | None:
    """Objek/array JSON pertama yang utuh di dalam teks (mengabaikan pagar ``` dan teks di sekitarnya)."""
    decoder = json.JSONDecoder()
    for index, char in enumerate(text):
        if char in "{[":
            try:
                _, end = decoder.raw_decode(text, index)
            except json.JSONDecodeError:
                continue
            return text[index:end]
    return None


async def chat_json[T: BaseModel](
    provider: LLMProvider, messages: list[ChatMessage], schema: type[T], *, timeout_s: float = 300.0,
) -> StructuredResult[T]:
    options = ChatOptions(json_schema=schema.model_json_schema())
    conversation = list(messages)
    last_error = "tidak ada jawaban"
    for attempt in range(1, MAX_ATTEMPTS + 1):
        parts: list[str] = []
        stats: ChatStats | None = None
        async for chunk in provider.chat(conversation, timeout_s=timeout_s, options=options):
            if chunk.type == "text":
                parts.append(chunk.text)
            elif chunk.type == "error":
                raise StructuredOutputError(chunk.error or "Penyedia AI gagal.")
            elif chunk.type == "done":
                stats = chunk.stats
                break
        raw = "".join(parts)
        candidate = extract_json(raw)
        if candidate is None:
            last_error = "jawaban tidak berisi JSON"
        else:
            try:
                return StructuredResult(schema.model_validate_json(candidate), attempt, raw, stats)
            except ValidationError as exc:
                last_error = "; ".join(
                    f"{'.'.join(map(str, e['loc'])) or '(akar)'}: {e['msg']}" for e in exc.errors()[:5])
        conversation = [*conversation, ChatMessage("assistant", raw[:2000]),
                        ChatMessage("user", f"Jawaban sebelumnya tidak valid ({last_error}). "
                                            "Balas HANYA dengan JSON yang sesuai skema.")]
    raise StructuredOutputError(f"Keluaran JSON tidak valid setelah {MAX_ATTEMPTS} percobaan: {last_error}")
