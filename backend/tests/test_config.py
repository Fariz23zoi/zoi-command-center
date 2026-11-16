from __future__ import annotations

from pathlib import Path

import pytest

from app.config.modes import ConfigError, resolve_runtime
from app.config.settings import REPO_ROOT, Mode, Settings, find_unknown_env_names, load_settings


def rt(**values):
    return resolve_runtime(Settings.model_validate(values))


@pytest.mark.parametrize(
    ("mode", "choice", "expected"),
    [
        ("development", "auto", "mock"),
        ("development", "ollama", "ollama"),
        ("development", "none", "none"),
        ("local", "auto", "ollama"),
        ("local", "none", "none"),
    ],
)
def test_provider_matrix(mode, choice, expected):
    assert rt(mode=mode, ai_provider=choice).provider == expected


def test_local_mode_rejects_mock():
    with pytest.raises(ConfigError, match="Mode local tidak boleh memakai Mock"):
        rt(mode="local", ai_provider="mock")


def test_defaults_per_mode():
    dev, local = rt(mode="development"), rt(mode="local")
    assert (dev.port, local.port) == (8000, 80)
    assert dev.data_dir == (REPO_ROOT / "data-dev").resolve()
    assert local.data_dir == (REPO_ROOT / "data").resolve()
    assert dev.banner and local.banner is None
    assert dev.cors_origins and not local.cors_origins
    assert local.serve_frontend and not dev.serve_frontend
    assert local.base_url == "http://127.0.0.1"


def test_relative_data_dir_resolves_against_repo_root():
    assert rt(data_dir="somewhere/x").data_dir == (REPO_ROOT / "somewhere/x").resolve()


@pytest.mark.parametrize("model", ["gpt-oss:120b-cloud", "qwen3:cloud", "deepseek:671b-cloud"])
def test_cloud_models_rejected(model):
    with pytest.raises(ConfigError, match="model cloud"):
        rt(mode="local", ollama_model=model)


def test_cloud_ollama_url_rejected():
    with pytest.raises(ConfigError, match="cloud"):
        rt(ollama_url="https://ollama.com")


def test_non_loopback_host_rejected():
    with pytest.raises(ConfigError, match="belum didukung"):
        rt(host="0.0.0.0")  # noqa: S104


def test_missing_model_is_warning_not_crash():
    runtime = rt(mode="local")
    assert any("ZOI_OLLAMA_MODEL" in w for w in runtime.warnings)


def test_invalid_enum_rejected_by_loader(tmp_path: Path):
    env = tmp_path / ".env"
    env.write_text("ZOI_MODE=produksi\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="tidak valid"):
        load_settings(env, use_process_env=False)


def test_unknown_variable_rejected(tmp_path: Path):
    env = tmp_path / ".env"
    env.write_text("ZOI_MODEE=local\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="ZOI_MODEE"):
        load_settings(env, use_process_env=False)


def test_reserved_and_foreign_names_ignored():
    assert find_unknown_env_names({"ZOI_YOUTUBE_CLIENT_ID": "x", "ZOI_TTS": "piper", "PATH": "/bin"}) == []


def test_env_file_values_loaded(tmp_path: Path):
    env = tmp_path / ".env"
    env.write_text("ZOI_MODE=local\nZOI_PORT=8080\nZOI_OLLAMA_MODEL=qwen3:4b\n# komentar\n", encoding="utf-8")
    settings = load_settings(env, use_process_env=False)
    assert settings.mode is Mode.LOCAL and settings.port == 8080 and settings.ollama_model == "qwen3:4b"


def test_example_env_files_are_valid():
    for name in (".env.development.example", ".env.local.example"):
        settings = load_settings(REPO_ROOT / name, use_process_env=False)
        resolve_runtime(settings)
