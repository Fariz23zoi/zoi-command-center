"""Aturan dua mode ZOI: development (Mock Provider) dan local (layanan di local server).

Semua keputusan mode dihitung di satu tempat agar tidak ada bagian lain yang menebak.
"""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

from app.config.settings import REPO_ROOT, AvatarMode, Mode, ProviderChoice, Settings, SttChoice, TtsChoice

DEV_FRONTEND_ORIGINS = ("http://127.0.0.1:5173", "http://localhost:5173")
DEFAULT_PORTS = {Mode.DEVELOPMENT: 8000, Mode.LOCAL: 80}
DEFAULT_DATA_DIRS = {Mode.DEVELOPMENT: "data-dev", Mode.LOCAL: "data"}
LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}
CLOUD_OLLAMA_HOSTS = {"ollama.com", "www.ollama.com", "api.ollama.com"}

DEV_BANNER = "DEVELOPMENT MODE — jawaban AI adalah MOCK, bukan AI sungguhan"


class ConfigError(Exception):
    """Konfigurasi tidak valid. Pesan selalu berbahasa Indonesia dan menyebut cara memperbaikinya."""


@dataclass(frozen=True)
class RuntimeConfig:
    mode: Mode
    host: str
    port: int
    data_dir: Path
    provider: str  # "mock" | "ollama" | "none"
    ollama_url: str
    ollama_model: str
    mock_latency_ms: int
    avatar_mode: AvatarMode
    stt: str  # "mock" | "whisper" | "none"
    whisper_model_dir: Path | None
    tts: str  # "mock" | "piper" | "none"
    piper_url: str
    cors_origins: tuple[str, ...]
    serve_frontend: bool
    frontend_dist: Path
    banner: str | None
    warnings: tuple[str, ...] = field(default_factory=tuple)

    @property
    def is_development(self) -> bool:
        return self.mode is Mode.DEVELOPMENT

    @property
    def base_url(self) -> str:
        host = f"[{self.host}]" if ":" in self.host else self.host
        return f"http://{host}" if self.port == 80 else f"http://{host}:{self.port}"

    @property
    def self_origins(self) -> tuple[str, ...]:
        suffix = "" if self.port == 80 else f":{self.port}"
        return (f"http://127.0.0.1{suffix}", f"http://localhost{suffix}")


def _resolve_dir(path: Path | None, default_name: str) -> Path:
    candidate = path if path is not None else Path(default_name)
    if not candidate.is_absolute():
        candidate = REPO_ROOT / candidate
    return candidate.resolve()


def _is_loopback(host: str) -> bool:
    if host.lower() in LOOPBACK_HOSTS:
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def resolve_runtime(settings: Settings) -> RuntimeConfig:
    warnings: list[str] = []

    if not _is_loopback(settings.host):
        raise ConfigError(
            f"ZOI_HOST={settings.host} belum didukung di Phase 1. Gunakan 127.0.0.1 — membuka akses "
            "ke jaringan rumah baru tersedia di Phase 10 dengan token keamanan."
        )

    # Provider AI
    choice = settings.ai_provider
    if choice is ProviderChoice.AUTO:
        provider = "mock" if settings.mode is Mode.DEVELOPMENT else "ollama"
    else:
        provider = choice.value

    if settings.mode is Mode.LOCAL and provider == "mock":
        raise ConfigError(
            "Mode local tidak boleh memakai Mock Provider (ZOI_AI_PROVIDER=mock). "
            "Pakai ZOI_AI_PROVIDER=ollama atau none. Mock hanya untuk ZOI_MODE=development."
        )

    parsed = urlparse(settings.ollama_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ConfigError(f"ZOI_OLLAMA_URL tidak valid: {settings.ollama_url!r} (contoh: http://127.0.0.1:11434)")
    if parsed.hostname.lower() in CLOUD_OLLAMA_HOSTS:
        raise ConfigError("ZOI_OLLAMA_URL menunjuk ke layanan cloud Ollama. ZOI hanya memakai Ollama lokal/LAN.")

    model = settings.ollama_model
    if model and (":cloud" in model or model.endswith("-cloud")):
        raise ConfigError(
            f"ZOI_OLLAMA_MODEL={model} adalah model cloud Ollama (berbayar/terhubung internet). "
            "Pakai model lokal, mis. qwen3:4b."
        )
    if provider == "ollama" and not model:
        warnings.append(
            "ZOI_OLLAMA_MODEL belum diisi — fitur AI akan berstatus 'tidak tersedia' sampai model dipilih."
        )

    stt = _voice_choice(settings.stt, SttChoice, "whisper", settings.mode, "ZOI_STT")
    tts = _voice_choice(settings.tts, TtsChoice, "piper", settings.mode, "ZOI_TTS")
    piper = urlparse(settings.piper_url)
    if piper.scheme not in {"http", "https"} or not piper.hostname:
        raise ConfigError(f"ZOI_PIPER_URL tidak valid: {settings.piper_url!r} (contoh: http://127.0.0.1:5000)")
    whisper_dir = settings.whisper_model_dir
    if whisper_dir is not None and not whisper_dir.is_absolute():
        whisper_dir = (REPO_ROOT / whisper_dir).resolve()
    if stt == "whisper" and whisper_dir is None:
        warnings.append("ZOI_WHISPER_MODEL_DIR belum diisi — input suara berstatus 'tidak tersedia'.")

    port = settings.port or DEFAULT_PORTS[settings.mode]
    data_dir = _resolve_dir(settings.data_dir, DEFAULT_DATA_DIRS[settings.mode])
    frontend_dist = _resolve_dir(settings.frontend_dist, "frontend/apps/web/dist")

    is_dev = settings.mode is Mode.DEVELOPMENT
    return RuntimeConfig(
        mode=settings.mode,
        host=settings.host,
        port=port,
        data_dir=data_dir,
        provider=provider,
        ollama_url=settings.ollama_url.rstrip("/"),
        ollama_model=model,
        mock_latency_ms=settings.mock_latency_ms,
        avatar_mode=settings.avatar_mode,
        stt=stt,
        whisper_model_dir=whisper_dir,
        tts=tts,
        piper_url=settings.piper_url.rstrip("/"),
        cors_origins=DEV_FRONTEND_ORIGINS if is_dev else (),
        serve_frontend=not is_dev,
        frontend_dist=frontend_dist,
        banner=DEV_BANNER if is_dev else None,
        warnings=tuple(warnings),
    )


def _voice_choice(choice: SttChoice | TtsChoice, enum: type, real: str, mode: Mode, name: str) -> str:
    """auto → mock di development, mesin asli di local. Mock tidak boleh di mode local (sama seperti AI)."""
    value = ("mock" if mode is Mode.DEVELOPMENT else real) if choice is enum.AUTO else choice.value
    if mode is Mode.LOCAL and value == "mock":
        raise ConfigError(f"Mode local tidak boleh memakai suara Mock ({name}=mock). Pakai {real} atau none.")
    return value
