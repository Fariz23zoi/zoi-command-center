"""Satu-satunya tempat yang memilih provider konkret. Kode lain hanya melihat LLMProvider."""

from __future__ import annotations

from app.config.modes import ConfigError, RuntimeConfig
from app.providers.base import LLMProvider, NoneProvider
from app.security.cost_guard import CostGuard


def build_provider(runtime: RuntimeConfig, guard: CostGuard) -> LLMProvider:
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
