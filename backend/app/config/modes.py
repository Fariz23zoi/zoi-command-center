"""Aturan dua mode ZOI: development (Mock Provider) dan local (layanan di local server).

Semua keputusan mode dihitung di satu tempat agar tidak ada bagian lain yang menebak.
"""

from __future__ import annotations

import ipaddress
import os
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

from app.config.settings import (
    REPO_ROOT,
    AvatarMode,
    FallbackChoice,
    Mode,
    ProviderChoice,
    Settings,
    SttChoice,
    TtsChoice,
)

DEV_FRONTEND_ORIGINS = ("http://127.0.0.1:5173", "http://localhost:5173")
DEFAULT_PORTS = {Mode.DEVELOPMENT: 8000, Mode.LOCAL: 80, Mode.ONLINE: 10000}
DEFAULT_DATA_DIRS = {Mode.DEVELOPMENT: "data-dev", Mode.LOCAL: "data", Mode.ONLINE: "data-online"}
MIN_SECRET_KEY = 32
MIN_SETUP_TOKEN = 16
LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}
CLOUD_OLLAMA_HOSTS = {"ollama.com", "www.ollama.com", "api.ollama.com"}

DEV_BANNER = "DEVELOPMENT MODE — jawaban AI adalah MOCK, bukan AI sungguhan"
DEV_BANNER_REAL = "DEVELOPMENT MODE"
CLOUD_PROVIDERS = ("nvidia", "openrouter")
CLOUD_HOSTS = {"nvidia": "integrate.api.nvidia.com", "openrouter": "openrouter.ai"}


class ConfigError(Exception):
    """Konfigurasi tidak valid. Pesan selalu berbahasa Indonesia dan menyebut cara memperbaikinya."""


@dataclass(frozen=True)
class RuntimeConfig:
    mode: Mode
    host: str
    port: int
    data_dir: Path
    provider: str  # "mock" | "ollama" | "nvidia" | "openrouter" | "none"
    ollama_url: str
    ollama_model: str
    mock_latency_ms: int
    avatar_mode: AvatarMode
    stt: str  # "mock" | "whisper" | "none"
    whisper_model_dir: Path | None
    tts: str  # "mock" | "piper" | "none"
    piper_url: str
    youtube_test_url: str
    cors_origins: tuple[str, ...]
    serve_frontend: bool
    frontend_dist: Path
    banner: str | None
    warnings: tuple[str, ...] = field(default_factory=tuple)
    nvidia_model: str = ""
    openrouter_model: str = ""
    ai_fallback: str = "none"
    cloud_test_url: str = ""
    # Mode online
    database_url: str = ""
    secret_key: str = ""
    setup_token: str = ""
    public_url: str = ""

    @property
    def is_online(self) -> bool:
        return self.mode is Mode.ONLINE

    @property
    def public_host(self) -> str | None:
        return urlparse(self.public_url).hostname if self.public_url else None

    @property
    def cloud_names(self) -> tuple[str, ...]:
        """Penyedia cloud yang benar-benar dipakai (utama + cadangan). Kosong = tidak ada data ke cloud."""
        if self.provider not in CLOUD_PROVIDERS:
            return ()
        return (self.provider,) if self.ai_fallback == "none" else (self.provider, self.ai_fallback)

    @property
    def is_development(self) -> bool:
        return self.mode is Mode.DEVELOPMENT

    @property
    def base_url(self) -> str:
        if self.is_online:
            return self.public_url
        host = f"[{self.host}]" if ":" in self.host else self.host
        return f"http://{host}" if self.port == 80 else f"http://{host}:{self.port}"

    @property
    def self_origins(self) -> tuple[str, ...]:
        if self.is_online:
            return (self.public_url,)
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

    online = settings.mode is Mode.ONLINE
    if not online and not _is_loopback(settings.host):
        raise ConfigError(
            f"ZOI_HOST={settings.host} belum didukung di Phase 1. Gunakan 127.0.0.1 — membuka akses "
            "ke jaringan rumah baru tersedia di Phase 10 dengan token keamanan."
        )

    # Provider AI
    choice = settings.ai_provider
    if choice is ProviderChoice.AUTO:
        provider = {Mode.DEVELOPMENT: "mock", Mode.LOCAL: "ollama", Mode.ONLINE: "none"}[settings.mode]
    else:
        provider = choice.value

    if settings.mode is Mode.LOCAL and provider == "mock":
        raise ConfigError(
            "Mode local tidak boleh memakai Mock Provider (ZOI_AI_PROVIDER=mock). "
            "Pakai ZOI_AI_PROVIDER=ollama atau none. Mock hanya untuk ZOI_MODE=development."
        )
    if online and provider not in (*CLOUD_PROVIDERS, "none"):
        raise ConfigError(
            f"Mode online tidak bisa memakai ZOI_AI_PROVIDER={provider}: server hosting tidak menjalankan "
            "model sendiri. Pakai nvidia, openrouter, atau none."
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

    cloud_test = settings.cloud_test_url.strip().rstrip("/")
    fallback = settings.ai_fallback.value
    if provider in CLOUD_PROVIDERS:
        if provider == "nvidia" and not settings.nvidia_model:
            warnings.append("ZOI_NVIDIA_MODEL belum diisi — AI berstatus 'tidak tersedia'. Lihat daftar model di "
                            "Settings › AI Cloud, isi nama model, lalu jalankan ulang.")
        if provider == "openrouter" and fallback != "none":
            raise ConfigError("ZOI_AI_FALLBACK hanya dipakai bersama ZOI_AI_PROVIDER=nvidia.")
        if "openrouter" in (provider, fallback):
            if not settings.openrouter_model:
                warnings.append("ZOI_OPENROUTER_MODEL belum diisi — OpenRouter belum bisa dipakai. Pilih model "
                                "gratis (berakhiran ':free') dari daftar di Settings › AI Cloud.")
            elif not settings.openrouter_model.endswith(":free"):
                raise ConfigError(f"ZOI_OPENROUTER_MODEL={settings.openrouter_model} bukan model gratis. Hanya "
                                  "model berakhiran ':free' yang diizinkan (aturan ZERO PAID API).")
        names = " dan ".join("NVIDIA NIM" if n == "nvidia" else "OpenRouter"
                             for n in ((provider,) if fallback == "none" else (provider, fallback)))
        warnings.append(f"AI CLOUD aktif — isi chat, memori, judul video, dan naskah dikirim ke {names}. "
                        "Rekaman suara, token YouTube, dan API key tidak pernah dikirim.")
    elif fallback != FallbackChoice.NONE.value:
        raise ConfigError("ZOI_AI_FALLBACK hanya dipakai bersama ZOI_AI_PROVIDER=nvidia.")
    if cloud_test:
        cloud_host = urlparse(cloud_test).hostname
        if urlparse(cloud_test).scheme != "http" or not cloud_host or not _is_loopback(cloud_host):
            raise ConfigError("ZOI_CLOUD_TEST_URL hanya boleh menunjuk server uji di komputer ini "
                              "(http://127.0.0.1:PORT). Kosongkan untuk memakai layanan sungguhan.")
        warnings.append("ZOI_CLOUD_TEST_URL aktif — jawaban 'AI cloud' berasal dari SERVER UJI, bukan "
                        "NVIDIA/OpenRouter.")

    if settings.wake_token and len(settings.wake_token) < 24:
        raise ConfigError("ZOI_WAKE_TOKEN terlalu pendek — pakai teks acak minimal 24 karakter, atau kosongkan.")

    database_url = settings.database_url.strip()
    public_url = (settings.public_url.strip() or (os.environ.get("RENDER_EXTERNAL_URL", "") if online else "")
                  ).rstrip("/")
    if database_url:
        db = urlparse(database_url)
        if db.scheme not in {"postgresql", "postgres"} or not db.hostname or not db.path.strip("/"):
            raise ConfigError("ZOI_DATABASE_URL tidak valid. Bentuknya: postgresql://pengguna:sandi@host/namadb "
                              "(salin 'connection string' dari dasbor Neon).")
    if online:
        if not database_url:
            raise ConfigError("Mode online membutuhkan ZOI_DATABASE_URL (alamat Postgres dari Neon). File di "
                              "server hosting gratis tidak permanen, jadi data harus di database.")
        if len(settings.secret_key) < MIN_SECRET_KEY:
            raise ConfigError(f"Mode online membutuhkan ZOI_SECRET_KEY acak minimal {MIN_SECRET_KEY} karakter "
                              "(kunci enkripsi API key dan token). Jangan pernah menaruhnya di repo.")
        if len(settings.setup_token) < MIN_SETUP_TOKEN:
            raise ConfigError(f"Mode online membutuhkan ZOI_SETUP_TOKEN acak minimal {MIN_SETUP_TOKEN} karakter "
                              "(kode untuk membuat kata sandi login).")
        parsed_public = urlparse(public_url)
        if not parsed_public.hostname or parsed_public.scheme not in {"https", "http"} or (
                parsed_public.scheme == "http" and not _is_loopback(parsed_public.hostname)):
            raise ConfigError("Mode online membutuhkan ZOI_PUBLIC_URL berawalan https:// (alamat ZOI di internet). "
                              "Di Render nilainya terisi otomatis.")
        if settings.stt not in (SttChoice.AUTO, SttChoice.NONE) or settings.tts not in (TtsChoice.AUTO, TtsChoice.NONE):
            raise ConfigError("Mode online tidak menjalankan Whisper/Piper. Hapus ZOI_STT dan ZOI_TTS; suara "
                              "memakai suara bawaan browser.")
        warnings.append("MODE ONLINE — ZOI bisa dijangkau dari internet. Data dan rahasia (terenkripsi) tersimpan "
                        "di database online; login wajib.")
        stt = tts = "none"
    else:
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

    youtube_test = settings.youtube_test_url.strip().rstrip("/")
    if youtube_test:
        test_host = urlparse(youtube_test).hostname
        if urlparse(youtube_test).scheme != "http" or not test_host or not _is_loopback(test_host):
            raise ConfigError("ZOI_YOUTUBE_TEST_URL hanya boleh menunjuk server uji di komputer ini "
                              "(http://127.0.0.1:PORT). Kosongkan untuk memakai YouTube sungguhan.")
        warnings.append("ZOI_YOUTUBE_TEST_URL aktif — data YouTube berasal dari SERVER UJI, bukan YouTube.")

    port = settings.port or (_env_port() if online else None) or DEFAULT_PORTS[settings.mode]
    data_dir = _resolve_dir(settings.data_dir, DEFAULT_DATA_DIRS[settings.mode])
    frontend_dist = _resolve_dir(settings.frontend_dist, "frontend/apps/web/dist")

    is_dev = settings.mode is Mode.DEVELOPMENT
    return RuntimeConfig(
        mode=settings.mode,
        host="0.0.0.0" if online else settings.host,  # noqa: S104 — server hosting butuh semua antarmuka
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
        youtube_test_url=youtube_test,
        cors_origins=DEV_FRONTEND_ORIGINS if is_dev else (),
        serve_frontend=not is_dev,
        frontend_dist=frontend_dist,
        banner=(DEV_BANNER if provider == "mock" else DEV_BANNER_REAL) if is_dev else None,
        warnings=tuple(warnings),
        nvidia_model=settings.nvidia_model,
        openrouter_model=settings.openrouter_model,
        ai_fallback=fallback,
        cloud_test_url=cloud_test,
        database_url=database_url,
        secret_key=settings.secret_key if online else "",
        setup_token=settings.setup_token if online else "",
        public_url=public_url if online else "",
    )


def _env_port() -> int | None:
    """Layanan hosting (Render) memberi tahu port lewat variabel PORT."""
    value = os.environ.get("PORT", "")
    return int(value) if value.isdigit() and 0 < int(value) < 65536 else None


def _voice_choice(choice: SttChoice | TtsChoice, enum: type, real: str, mode: Mode, name: str) -> str:
    """auto → mock di development, mesin asli di local. Mock tidak boleh di mode local (sama seperti AI)."""
    value = ("mock" if mode is Mode.DEVELOPMENT else real) if choice is enum.AUTO else choice.value
    if mode is Mode.LOCAL and value == "mock":
        raise ConfigError(f"Mode local tidak boleh memakai suara Mock ({name}=mock). Pakai {real} atau none.")
    return value
