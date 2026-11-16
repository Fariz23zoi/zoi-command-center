"""Layanan AI lokal: satu-satunya tempat yang tahu provider konkretnya Ollama. API hanya memanggil layanan ini.

ZOI hanya MEMBACA dari Ollama dan memilih model; tidak pernah mengunduh atau menghapus model.
"""

from __future__ import annotations

import time
from typing import Any
from urllib.parse import urlparse

import httpx

from app.ai import selection
from app.ai.catalog import load_catalog
from app.ai.tasks import KIND as EVAL_KIND
from app.config.modes import RuntimeConfig
from app.core.errors import NotFound, ZoiError
from app.core.events import EventBus
from app.db.session import Database
from app.providers.base import LLMProvider, LocalModelAdmin, is_cloud_model
from app.security.cost_guard import CostGuardBlocked
from app.tasks.manager import TaskManager

LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}
NETWORK_ERRORS = (httpx.HTTPError, ValueError, CostGuardBlocked)


class LocalAIService:
    def __init__(self, *, provider: LLMProvider, runtime: RuntimeConfig, db: Database, bus: EventBus,
                 tasks: TaskManager, source: str) -> None:
        self.provider = provider
        self.runtime = runtime
        self.db = db
        self.bus = bus
        self.tasks = tasks
        self.source = source

    # ── bantuan ────────────────────────────────────────────────────────────
    def _ollama(self) -> LocalModelAdmin:
        if not isinstance(self.provider, LocalModelAdmin):
            raise ZoiError("Fitur ini hanya untuk Ollama (ZOI_AI_PROVIDER=ollama).", status_code=409,
                           code="not_ollama")
        return self.provider

    @staticmethod
    def _unreachable(provider: LocalModelAdmin, exc: Exception) -> ZoiError:
        if isinstance(exc, CostGuardBlocked):
            return ZoiError(str(exc), status_code=502, code="blocked")
        return ZoiError(f"Ollama tidak dapat dihubungi di {provider.base_url} ({type(exc).__name__}).",
                        status_code=502, code="ollama_unreachable")

    async def _validated(self, model: str) -> LocalModelAdmin:
        provider = self._ollama()
        try:
            problem = await provider.validate_choice(model)
        except NETWORK_ERRORS as exc:
            raise self._unreachable(provider, exc) from exc
        if problem:
            raise ZoiError(problem, code="model_rejected")
        return provider

    def _publish(self) -> None:
        self.bus.publish("provider.updated", {"active_model": self.provider.model, "active_source": self.source})

    # ── operasi ───────────────────────────────────────────────────────────
    async def status(self) -> dict[str, Any]:
        provider = self.provider
        base: dict[str, Any] = {
            "provider": provider.name, "is_mock": provider.is_mock, "active_model": provider.model,
            "active_source": self.source, "env_model": self.runtime.ollama_model or None,
            "catalog": load_catalog(), "can_download": False, "ready": False,
            "url": None, "location": None, "version": None, "installed": [], "running": [],
        }
        if not isinstance(provider, LocalModelAdmin):
            detail = ("Mode development memakai Mock Provider — tidak ada model sungguhan di sini."
                      if provider.is_mock else "AI dinonaktifkan (ZOI_AI_PROVIDER=none).")
            return {**base, "reachable": False, "detail": detail}
        host = urlparse(provider.base_url).hostname or ""
        base |= {"url": provider.base_url, "location": "lokal" if host in LOCAL_HOSTS else "jaringan"}
        try:
            version = await provider.version()
            installed = await provider.installed()
            running = await provider.running()
        except NETWORK_ERRORS as exc:
            return {**base, "reachable": False, "detail": self._unreachable(provider, exc).message}
        health = await provider.health()
        return {**base, "reachable": True, "version": version, "detail": health.detail, "ready": health.available,
                "installed": [m.to_dict() for m in installed], "running": [m.to_dict() for m in running]}

    async def test(self) -> dict[str, Any]:
        provider = self._ollama()
        start = time.monotonic()
        try:
            version = await provider.version()
        except NETWORK_ERRORS as exc:
            return {"ok": False, "detail": self._unreachable(provider, exc).message, "latency_ms": None}
        return {"ok": True, "detail": f"Ollama {version} menjawab.", "version": version,
                "latency_ms": round((time.monotonic() - start) * 1000)}

    async def details(self, name: str) -> dict[str, Any]:
        provider = self._ollama()
        if is_cloud_model(name):
            raise ZoiError("Model cloud Ollama tidak diizinkan.", code="cloud_model")
        try:
            return (await provider.show(name)).to_dict()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                raise NotFound(f"Model '{name}' tidak ada di Ollama.") from exc
            raise self._unreachable(provider, exc) from exc
        except NETWORK_ERRORS as exc:
            raise self._unreachable(provider, exc) from exc

    async def set_active(self, model: str) -> dict[str, Any]:
        provider = await self._validated(model)
        selection.save_model(self.db, model)
        provider.set_model(model)
        self.source = "ui"
        self._publish()
        return {"active_model": provider.model, "active_source": self.source}

    def reset_active(self) -> dict[str, Any]:
        provider = self._ollama()
        selection.save_model(self.db, None)
        model, self.source = selection.resolve(self.db, self.runtime.ollama_model)
        provider.set_model(model)
        self._publish()
        return {"active_model": provider.model, "active_source": self.source}

    async def unload(self, model: str) -> dict[str, Any]:
        provider = self._ollama()
        try:
            await provider.unload(model)
            running = await provider.running()
        except NETWORK_ERRORS as exc:
            raise self._unreachable(provider, exc) from exc
        return {"running": [m.to_dict() for m in running]}

    async def start_evaluation(self, model: str) -> dict[str, Any]:
        await self._validated(model)
        return self.tasks.submit(EVAL_KIND, {"model": model}, name=f"Uji model AI: {model}")
