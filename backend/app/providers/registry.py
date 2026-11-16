"""Satu-satunya tempat yang memilih provider konkret. Kode lain hanya melihat LLMProvider."""

from __future__ import annotations

from collections.abc import Callable

from app.config.modes import CLOUD_PROVIDERS, ConfigError, RuntimeConfig
from app.db.session import Database
from app.providers.base import LLMProvider, NoneProvider
from app.security.cost_guard import CostGuard


def build_provider(runtime: RuntimeConfig, guard: CostGuard, *, db: Database | None = None,
                   key_getter: Callable[[str], str | None] | None = None) -> LLMProvider:
    if runtime.provider in CLOUD_PROVIDERS:
        if db is None or key_getter is None:
            raise ConfigError("Penyedia AI cloud membutuhkan database dan penyimpanan rahasia.")
        from app.providers.cloud import build_cloud

        return build_cloud(provider=runtime.provider, fallback=runtime.ai_fallback,
                           models={"nvidia": runtime.nvidia_model, "openrouter": runtime.openrouter_model},
                           test_url=runtime.cloud_test_url, guard=guard, db=db, key_getter=key_getter)
    if runtime.provider == "mock":
        if not runtime.is_development:
            raise ConfigError("Mock Provider hanya boleh di mode development.")
        from app.providers.mock import MockProvider

        return MockProvider(latency_ms=runtime.mock_latency_ms)
    if runtime.provider == "ollama":
        from app.providers.ollama import OllamaProvider

        return OllamaProvider(runtime.ollama_url, runtime.ollama_model, guard)
    if runtime.provider == "none":
        return NoneProvider()
    raise ConfigError(f"Provider tidak dikenal: {runtime.provider}")
