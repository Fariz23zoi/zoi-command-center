"""Ollama Provider — dipakai di ZOI_MODE=local (atau ollama di LAN).

- Semua koneksi lewat Cost Guard.
- TIDAK PERNAH memanggil /api/pull atau mengunduh model. Model wajib dipilih pengguna (ZOI_OLLAMA_MODEL).
- Model cloud Ollama (tag ':cloud' / '-cloud') ditolak.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.providers.base import ChatChunk, ChatMessage, ProviderStatus, ToolCall, ToolSpec
from app.security.cost_guard import CostGuard, CostGuardBlocked


def is_cloud_model(model: str) -> bool:
    return ":cloud" in model or model.endswith("-cloud")


class OllamaProvider:
    name = "ollama"
    is_mock = False

    def __init__(
        self,
        base_url: str,
        model: str,
        guard: CostGuard,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        health_timeout_s: float = 3.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model or None
        self.guard = guard
        self._transport = transport
        self._health_timeout_s = health_timeout_s

    def _client(self, timeout: float) -> httpx.AsyncClient:
        kwargs: dict[str, Any] = {"base_url": self.base_url, "timeout": timeout}
        if self._transport is not None:
            kwargs["transport"] = self._transport
        return self.guard.async_client(**kwargs)

    async def list_models(self) -> list[str]:
        async with self._client(self._health_timeout_s) as client:
            response = await client.get("/api/tags")
            response.raise_for_status()
            return sorted(m["name"] for m in response.json().get("models", []) if "name" in m)

    async def health(self) -> ProviderStatus:
        base = {"name": self.name, "is_mock": False, "model": self.model}
        try:
            async with self._client(self._health_timeout_s) as client:
                version = (await client.get("/api/version")).json().get("version")
            models = await self.list_models()
        except CostGuardBlocked as exc:
            return ProviderStatus(available=False, detail=str(exc), **base)
        except (httpx.HTTPError, ValueError) as exc:
            return ProviderStatus(
                available=False, **base,
                detail=f"Ollama tidak dapat dihubungi di {self.base_url} ({type(exc).__name__}). "
                       "Pastikan aplikasi Ollama berjalan.",
            )
        if not self.model:
            return ProviderStatus(available=False, models=models, **base,
                                  detail=f"Ollama {version} aktif, tetapi ZOI_OLLAMA_MODEL belum diisi.")
        if is_cloud_model(self.model):
            return ProviderStatus(available=False, models=models, **base,
                                  detail="Model cloud Ollama tidak diizinkan. Pilih model lokal.")
        if self.model not in models:
            return ProviderStatus(
                available=False, models=models, **base,
                detail=f"Model '{self.model}' belum terpasang di Ollama. ZOI tidak mengunduh model otomatis; "
                       f"jalankan sendiri: ollama pull {self.model}",
            )
        return ProviderStatus(available=True, models=models, **base, detail=f"Ollama {version} siap.")

    async def chat(
        self, messages: list[ChatMessage], tools: list[ToolSpec] | None = None, timeout_s: float = 120.0
    ) -> AsyncIterator[ChatChunk]:
        if not self.model:
            yield ChatChunk(type="error", error="AI tidak tersedia: ZOI_OLLAMA_MODEL belum diisi.")
            return
        if is_cloud_model(self.model):
            yield ChatChunk(type="error", error="Model cloud Ollama tidak diizinkan.")
            return

        payload: dict[str, Any] = {
            "model": self.model,
            "stream": True,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
        }
        if tools:
            payload["tools"] = [t.to_ollama() for t in tools]

        try:
            async with self._client(timeout_s) as client, client.stream("POST", "/api/chat", json=payload) as resp:
                if resp.status_code != 200:
                    body = (await resp.aread()).decode("utf-8", errors="replace")
                    try:
                        detail = json.loads(body).get("error", body)
                    except json.JSONDecodeError:
                        detail = body
                    yield ChatChunk(type="error",
                                    error=f"Ollama menolak permintaan ({resp.status_code}): {detail[:300]}")
                    return
                async for line in resp.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        yield ChatChunk(type="error", error="Ollama mengirim data yang tidak dapat dibaca.")
                        return
                    if data.get("error"):
                        yield ChatChunk(type="error", error=f"Ollama: {data['error']}")
                        return
                    message = data.get("message") or {}
                    for raw in message.get("tool_calls") or []:
                        call = _parse_tool_call(raw)
                        if call is None:
                            yield ChatChunk(type="error", error="Format pemanggilan tool dari model tidak valid.")
                            return
                        yield ChatChunk(type="tool_call", tool_call=call)
                    if message.get("content"):
                        yield ChatChunk(type="text", text=message["content"])
                    if data.get("done"):
                        yield ChatChunk(type="done")
                        return
                yield ChatChunk(type="error", error="Koneksi ke Ollama terputus sebelum jawaban selesai.")
        except CostGuardBlocked as exc:
            yield ChatChunk(type="error", error=str(exc))
        except httpx.TimeoutException:
            yield ChatChunk(type="error", error=f"timeout: Ollama tidak menjawab dalam {timeout_s:g} detik.")
        except httpx.HTTPError as exc:
            yield ChatChunk(type="error", error=f"Ollama tidak dapat dihubungi ({type(exc).__name__}).")


def _parse_tool_call(raw: Any) -> ToolCall | None:
    if not isinstance(raw, dict):
        return None
    function = raw.get("function")
    if not isinstance(function, dict) or not isinstance(function.get("name"), str):
        return None
    arguments = function.get("arguments", {})
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except json.JSONDecodeError:
            return None
    if not isinstance(arguments, dict):
        return None
    return ToolCall(name=function["name"], arguments=arguments)
