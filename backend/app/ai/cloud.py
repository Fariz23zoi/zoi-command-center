"""Layanan AI cloud untuk halaman Settings › AI Cloud: status, API key, daftar model, dan uji model.

Penyedia & model ditentukan .env (keputusan K-2); di sini hanya API key yang bisa diubah. Key disimpan di
penyimpanan rahasia (keyring sistem) dan tidak pernah dikembalikan ke browser.
"""

from __future__ import annotations

from typing import Any

import httpx

from app.core.errors import ZoiError
from app.core.events import EventBus
from app.providers.base import ChatMessage, CloudAdmin, LLMProvider
from app.security.cost_guard import CostGuardBlocked
from app.youtube.secrets_store import SecretStore

# Nama, label, awalan key, dan alamat daftar. Disalin di sini agar layanan tidak mengimpor penyedia konkret.
KNOWN = {
    "nvidia": {"label": "NVIDIA NIM", "key_name": "nvidia_api_key", "key_prefix": "nvapi-",
               "signup_url": "https://build.nvidia.com"},
    "openrouter": {"label": "OpenRouter", "key_name": "openrouter_api_key", "key_prefix": "sk-or-",
                   "signup_url": "https://openrouter.ai"},
}
DATA_SENT = ["Isi chat dan permintaan agen", "Memori yang relevan dengan pertanyaan",
             "Judul video channel-mu (untuk ide konten)", "Judul dari daftar Trending/pencarian (untuk tema)",
             "Topik, catatan, dan naskah yang kamu minta dibuatkan"]
NEVER_SENT = ["Rekaman suara (suara tetap diproses di komputer ini)", "Token YouTube dan API key",
              "Angka statistik channel", "File di komputermu"]
TEST_PROMPT = "Balas dengan satu kata saja: OK"


class CloudAIService:
    def __init__(self, *, provider: LLMProvider, store: SecretStore, bus: EventBus) -> None:
        self.provider = provider
        self.store = store
        self.bus = bus

    def _parts(self) -> list[Any]:
        return self.provider.cloud_parts() if isinstance(self.provider, CloudAdmin) else []

    def _part(self, name: str) -> Any:
        for part in self._parts():
            if part.name == name:
                return part
        raise ZoiError(f"Penyedia '{name}' tidak diaktifkan di .env.", status_code=409, code="not_enabled")

    @staticmethod
    def _known(name: str) -> dict[str, str]:
        if name not in KNOWN:
            raise ZoiError("Penyedia AI cloud tidak dikenal.", status_code=404, code="not_found")
        return KNOWN[name]

    def status(self) -> dict[str, Any]:
        active = {p.name: (i, p) for i, p in enumerate(self._parts())}
        providers = []
        for name, info in KNOWN.items():
            index, part = active.get(name, (None, None))
            providers.append({
                "name": name, "label": info["label"], "signup_url": info["signup_url"],
                "key_prefix": info["key_prefix"], "has_key": self.store.get(info["key_name"]) is not None,
                "role": None if index is None else "utama" if index == 0 else "cadangan",
                "model": part.model if part else None,
                "model_problem": part.model_problem() if part else None,
                "free_only": name == "openrouter",
                "limits": part.limiter.status() if part else None,
            })
        enabled = bool(active)
        return {
            "enabled": enabled, "provider": self.provider.name,
            "test_endpoint": bool(enabled and getattr(self.provider, "is_test", False)),
            "token_storage": self.store.kind, "storage_warning": self.store.warning,
            "providers": providers, "data_sent": DATA_SENT, "never_sent": NEVER_SENT,
            "how_to_enable": ["ZOI_AI_PROVIDER=nvidia", "ZOI_NVIDIA_MODEL=<nama model dari build.nvidia.com>",
                              "ZOI_AI_FALLBACK=openrouter", "ZOI_OPENROUTER_MODEL=<model gratis berakhiran :free>"],
            "selection": "Penyedia dan model hanya bisa diubah lewat file .env, lalu ZOI dijalankan ulang.",
        }

    def _refresh(self) -> None:
        for part in self._parts():
            part.invalidate()
        self.bus.publish("provider.updated", {"active_model": self.provider.model, "active_source": "env"})

    def set_key(self, name: str, key: str) -> dict[str, Any]:
        info = self._known(name)
        key = key.strip()
        if not key.startswith(info["key_prefix"]) or len(key) < 20 or len(key) > 300 or any(c.isspace() for c in key):
            raise ZoiError(f"Itu tidak terlihat seperti API key {info['label']} (harus diawali "
                           f"'{info['key_prefix']}').", code="bad_key")
        self.store.set(info["key_name"], key)
        self._refresh()
        return self.status()

    def delete_key(self, name: str) -> dict[str, Any]:
        self.store.delete(self._known(name)["key_name"])
        self._refresh()
        return self.status()

    async def models(self, name: str) -> dict[str, Any]:
        part = self._part(name)
        if not part.has_key():
            raise ZoiError(f"Masukkan dulu API key {part.spec.label}.", status_code=409, code="no_key")
        try:
            models = await part.list_models()
        except CostGuardBlocked as exc:
            raise ZoiError(str(exc), status_code=502, code="blocked") from exc
        except httpx.HTTPStatusError as exc:
            raise ZoiError(f"{part.spec.label} menolak permintaan daftar model ({exc.response.status_code}).",
                           status_code=502, code="cloud_error") from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise ZoiError(f"{part.spec.label} tidak dapat dihubungi ({type(exc).__name__}).", status_code=502,
                           code="unreachable") from exc
        return {"name": name, "models": models, "current": part.model, "current_listed": part.model in models,
                "note": "Sebagian model di daftar tidak bisa dipanggil akun gratis. Pakai 'Uji model'."}

    async def test(self, name: str) -> dict[str, Any]:
        """Mengirim SATU permintaan kecil ke model yang dipilih di .env (terhitung di batas permintaan)."""
        part = self._part(name)
        reply: list[str] = []
        error: str | None = None
        async for chunk in part.chat([ChatMessage("user", TEST_PROMPT)], timeout_s=60.0):
            if chunk.type == "text":
                reply.append(chunk.text)
            elif chunk.type == "error":
                error = chunk.error
        text = "".join(reply).strip()
        if error is None and not text:
            error = "Model tidak mengirim teks jawaban."
        return {"name": name, "model": part.model, "ok": error is None, "reply": text[:200], "error": error,
                "limits": part.limiter.status()}
