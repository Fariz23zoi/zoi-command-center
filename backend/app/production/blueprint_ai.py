"""AI untuk salinan Blueprint Studio (ADR 0018).

Blueprint Studio asli memanggil `claude.use("sample").json(prompt)` — hanya tersedia di dalam Claude. Di salinan ZOI,
fungsi itu diganti shim yang memanggil endpoint ini, lalu dijawab AI Brain ZOI (NVIDIA NIM / OpenRouter :free /
Ollama, sesuai .env). Prompt dari Blueprint tidak diubah; jawaban harus JSON (objek/array) — selain itu error jujur,
sehingga Blueprint memakai jalur cadangan bawaannya.
"""

from __future__ import annotations

import json
from typing import Any

from app.ai.structured import extract_json
from app.core.errors import ZoiError
from app.providers.base import ChatMessage, LLMProvider

TIMEOUT_S = 180.0
SYSTEM = ("Kamu membantu aplikasi Blueprint Studio. Ikuti instruksi pengguna persis. "
          "Balas HANYA dengan JSON yang valid (objek atau array), tanpa teks lain dan tanpa ```.")


async def blueprint_json(provider: LLMProvider, prompt: str) -> dict[str, Any]:
    messages = [ChatMessage("system", SYSTEM), ChatMessage("user", prompt)]
    last = "tidak ada jawaban"
    for _ in range(2):
        parts: list[str] = []
        served: str | None = None
        async for chunk in provider.chat(messages, timeout_s=TIMEOUT_S):
            if chunk.type == "text":
                parts.append(chunk.text)
            elif chunk.type == "error":
                raise ZoiError(chunk.error or "AI ZOI gagal menjawab.", status_code=502, code="ai_failed")
            elif chunk.type == "done":
                served = chunk.served_by
                break
        raw = "".join(parts)
        candidate = extract_json(raw)
        if candidate is not None:
            return {"result": json.loads(candidate), "provider": served or provider.name,
                    "is_mock": bool(getattr(provider, "is_mock", False))}
        last = "jawaban tidak berisi JSON"
        messages = [*messages, ChatMessage("assistant", raw[:2000]),
                    ChatMessage("user", "Jawaban tadi bukan JSON. Balas HANYA JSON yang diminta.")]
    raise ZoiError(f"AI ZOI tidak memberi JSON yang valid ({last}).", status_code=502, code="ai_bad_json")
