"""Konfigurasi ZOI — HANYA dari environment variable (dan file .env opsional).

Path khusus mesin (CLIPPER, Blueprint, Ollama) tidak pernah disimpan di database.
"""

from __future__ import annotations

import os
from enum import StrEnum
from pathlib import Path

from dotenv import dotenv_values
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]

ENV_PREFIX = "ZOI_"

# Variabel yang dicadangkan untuk fase berikutnya: dibiarkan, tidak dianggap salah ketik.
RESERVED_PREFIXES: tuple[str, ...] = ()
META_VARS = {"ZOI_ENV_FILE"}


class Mode(StrEnum):
    DEVELOPMENT = "development"
    LOCAL = "local"
    ONLINE = "online"  # di server hosting (Render) dengan login, database Postgres, dan AI cloud


class ProviderChoice(StrEnum):
    AUTO = "auto"
    MOCK = "mock"
    OLLAMA = "ollama"
    NVIDIA = "nvidia"
    OPENROUTER = "openrouter"
    NONE = "none"


class FallbackChoice(StrEnum):
    NONE = "none"
    OPENROUTER = "openrouter"


class SttChoice(StrEnum):
    AUTO = "auto"
    MOCK = "mock"
    WHISPER = "whisper"
    NONE = "none"


class TtsChoice(StrEnum):
    AUTO = "auto"
    MOCK = "mock"
    PIPER = "piper"
    NONE = "none"


class AvatarMode(StrEnum):
    AUTO = "auto"
    TWO_D = "2d"
    THREE_D = "3d"


class LogLevel(StrEnum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix=ENV_PREFIX,
        case_sensitive=False,
        extra="ignore",
        env_ignore_empty=True,
    )

    mode: Mode = Mode.DEVELOPMENT
    host: str = "127.0.0.1"
    port: int | None = Field(default=None, ge=1, le=65535)
    data_dir: Path | None = None
    log_level: LogLevel = LogLevel.INFO

    ai_provider: ProviderChoice = ProviderChoice.AUTO
    ollama_url: str = "http://127.0.0.1:11434"
    ollama_model: str = ""
    mock_latency_ms: int = Field(default=300, ge=0, le=10_000)

    # AI cloud GRATIS (keputusan pengguna 15 Nov 2026, ADR 0011). Penyedia & model HANYA lewat .env; API key TIDAK
    # di .env — dimasukkan lewat Settings › AI Cloud dan disimpan di penyimpanan kunci sistem.
    nvidia_model: str = ""
    openrouter_model: str = ""
    ai_fallback: FallbackChoice = FallbackChoice.NONE
    # HANYA untuk tes: arahkan NVIDIA & OpenRouter ke server tiruan di komputer ini.
    cloud_test_url: str = ""

    avatar_mode: AvatarMode = AvatarMode.AUTO

    # Suara (Phase 4). ZOI tidak mengunduh model: folder Whisper & server Piper disiapkan pengguna sendiri.
    stt: SttChoice = SttChoice.AUTO
    whisper_model_dir: Path | None = None
    tts: TtsChoice = TtsChoice.AUTO
    piper_url: str = "http://127.0.0.1:5000"

    # YouTube (Phase 6). HANYA untuk tes: arahkan semua endpoint Google ke server tiruan di komputer ini.
    # Kosong = Google sungguhan. Bila diisi, UI menandai semua data sebagai "ENDPOINT UJI".
    youtube_test_url: str = ""

    clipper_dir: Path | None = None
    clipper_python: Path | None = None
    blueprint_file: Path | None = None
    # Folder tempat pengguna sendiri menjalankan `npm install hyperframes` (opsional, Phase 7).
    hyperframes_dir: Path | None = None

    extra_allowed_hosts: str = ""

    # Phase 8: token Bearer (≥24 karakter) untuk POST /api/automation/wake dari GitHub Actions. Kosong = nonaktif.
    wake_token: str = ""

    # ── Mode online (ADR 0012). Semua nilai di bawah ini RAHASIA: hanya di pengaturan layanan hosting. ──
    # Alamat Postgres (Neon): postgresql://user:sandi@host/db
    database_url: str = ""
    # Kunci induk (≥32 karakter) untuk mengenkripsi rahasia yang disimpan di database.
    secret_key: str = ""
    # Kode sekali pakai (≥16 karakter) untuk membuat atau mengganti kata sandi login.
    setup_token: str = ""
    # Alamat publik ZOI, mis. https://zoi-saya.onrender.com (di Render terisi otomatis dari RENDER_EXTERNAL_URL).
    public_url: str = ""

    # Lokasi frontend hasil build (mode local). Bisa dioverride untuk keperluan tes.
    frontend_dist: Path | None = None

    @field_validator("log_level", mode="before")
    @classmethod
    def _upper_log_level(cls, value: object) -> object:
        return value.upper() if isinstance(value, str) else value

    @field_validator("ollama_model", "nvidia_model", "openrouter_model")
    @classmethod
    def _strip_model(cls, value: str) -> str:
        return value.strip()

    @property
    def extra_hosts(self) -> list[str]:
        return [h.strip().lower() for h in self.extra_allowed_hosts.split(",") if h.strip()]


def known_env_names() -> set[str]:
    return {f"{ENV_PREFIX}{name.upper()}" for name in Settings.model_fields}


def find_unknown_env_names(env: dict[str, str | None]) -> list[str]:
    """Nama ZOI_* yang tidak dikenal (kemungkinan salah ketik) → harus ditolak, bukan ditebak."""
    known = known_env_names() | META_VARS
    unknown = []
    for key in env:
        upper = key.upper()
        if not upper.startswith(ENV_PREFIX) or upper in known:
            continue
        if upper.startswith(RESERVED_PREFIXES):
            continue
        unknown.append(key)
    return sorted(unknown)


def default_env_file() -> Path:
    override = os.environ.get("ZOI_ENV_FILE")
    return Path(override) if override else REPO_ROOT / ".env"


def load_settings(env_file: Path | None = None, *, use_process_env: bool = True) -> Settings:
    """Baca konfigurasi. Prioritas: environment proses > file .env > default."""
    from app.config.modes import ConfigError

    env_file = env_file if env_file is not None else default_env_file()
    file_values: dict[str, str | None] = {}
    if env_file.is_file():
        file_values = dotenv_values(env_file, encoding="utf-8")

    combined: dict[str, str | None] = dict(file_values)
    if use_process_env:
        combined.update({k: v for k, v in os.environ.items() if k.upper().startswith(ENV_PREFIX)})

    unknown = find_unknown_env_names(combined)
    if unknown:
        raise ConfigError(
            "Variabel konfigurasi tidak dikenal: "
            + ", ".join(unknown)
            + ". Periksa ejaannya (lihat .env.development.example / .env.local.example)."
        )

    values = {
        k[len(ENV_PREFIX):].lower(): v
        for k, v in combined.items()
        if k.upper() in known_env_names() and v not in (None, "")
    }
    try:
        # model_validate tidak membaca environment lagi → satu sumber kebenaran: `values`.
        return Settings.model_validate(values)
    except Exception as exc:  # pydantic.ValidationError → pesan ramah
        raise ConfigError(f"Konfigurasi tidak valid: {exc}") from exc
