"""App factory ZOI. Satu fungsi membangun seluruh aplikasi dari konfigurasi environment."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response

from app import __version__
from app.agent.builtin import ToolDeps, build_registry
from app.agent.service import AgentService
from app.ai import selection
from app.ai.cloud import CloudAIService
from app.ai.local import LocalAIService
from app.ai.tasks import model_eval_kind
from app.api.router import api_router, ws_router
from app.automation.service import AutomationService
from app.chat.service import ChatService
from app.config.modes import CLOUD_HOSTS, RuntimeConfig, resolve_runtime
from app.config.settings import Settings, load_settings
from app.content.service import ContentService
from app.context import AppContext
from app.core.agent_state import AgentStateTracker
from app.core.errors import ZoiError, zoi_error_handler
from app.core.events import EventBus
from app.db.migrations import upgrade_database, upgrade_engine
from app.db.models import NetworkAudit
from app.db.session import Database, db_path
from app.integrations.blueprint.adapter import BlueprintAdapter
from app.integrations.clipper.adapter import ClipperAdapter
from app.logging_setup import configure_logging, get_logger
from app.memory.service import MemoryService
from app.production.service import ProductionService
from app.providers.base import LocalModelAdmin
from app.providers.registry import build_provider
from app.security.auth import SESSION_COOKIE, AuthService
from app.security.cost_guard import CostGuard
from app.security.remote import remote_denied
from app.security.secrets_db import DbSecretStore
from app.tasks.builtin import make_run_async, system_check_kind
from app.tasks.manager import TaskManager
from app.update.service import UpdateService
from app.voice.registry import build_voice
from app.voice.service import VoiceService
from app.youtube.oauth import endpoints as youtube_endpoints
from app.youtube.public import PublicDataService
from app.youtube.secrets_store import SecretStore
from app.youtube.service import YouTubeService

log = get_logger("main")

TRUSTED_HOSTS = ["127.0.0.1", "localhost", "[::1]", "::1"]
UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
CLIENT_HEADER = "x-zoi-client"


def create_app(settings: Settings | None = None, *, return_to_idle_s: float = 2.5,
               approval_timeout_s: float = 600.0, scheduler_interval_s: float = 60.0) -> FastAPI:
    settings = settings or load_settings()
    runtime = resolve_runtime(settings)

    runtime.data_dir.mkdir(parents=True, exist_ok=True)
    configure_logging(runtime.data_dir / "logs", settings.log_level.value)
    if runtime.database_url:
        db = Database(url=runtime.database_url)
        upgrade_engine(db.engine)
        backup = None
    else:
        backup = upgrade_database(db_path(runtime.data_dir))
        db = Database(db_path(runtime.data_dir))
    bus = EventBus()
    agent = AgentStateTracker(bus, return_to_idle_s=return_to_idle_s)

    def record(host: str, method: str, path: str, allowed: bool, reason: str) -> None:
        with db.session() as s:
            s.add(NetworkAudit(host=host, method=method, path=path[:500], allowed=allowed, reason=reason))
        if not allowed:
            log.warning("cost_guard_blocked", host=host, method=method, reason=reason)

    piper_host = urlparse(runtime.piper_url).hostname
    guard = CostGuard.build(ollama_url=runtime.ollama_url,
                            extra_hosts=[*settings.extra_hosts, *([piper_host.lower()] if piper_host else [])],
                            cloud_hosts=[] if runtime.cloud_test_url else [CLOUD_HOSTS[n] for n in runtime.cloud_names],
                            recorder=record)
    secrets = DbSecretStore(db, runtime.secret_key) if runtime.is_online else SecretStore(runtime.data_dir)
    auth = AuthService(db, runtime.setup_token, enabled=runtime.is_online)
    provider = build_provider(runtime, guard, db=db, key_getter=secrets.get)
    stt, tts = build_voice(runtime, guard)
    ai_source = "none"
    if isinstance(provider, LocalModelAdmin):
        model, ai_source = selection.resolve(db, runtime.ollama_model)
        provider.set_model(model)
    adapters = [ClipperAdapter(settings.clipper_dir, settings.clipper_python),
                BlueprintAdapter(settings.blueprint_file)]
    tasks = TaskManager(db, bus, agent)
    chat = ChatService(db, bus, agent, provider)
    memory = MemoryService(db)
    chat.memory = memory
    youtube = YouTubeService(db=db, bus=bus, guard=guard, endpoints=youtube_endpoints(runtime.youtube_test_url),
                             data_dir=runtime.data_dir, store=secrets,
                             web_callback_url=f"{runtime.public_url}/api/youtube/callback"
                             if runtime.is_online else "")
    public = PublicDataService(db=db, bus=bus, youtube=youtube)
    content = ContentService(db=db, bus=bus, provider=provider, memory=memory, youtube=youtube, public=public)
    voice = VoiceService(stt=stt, tts=tts, db=db)
    production = ProductionService(data_dir=runtime.data_dir, blueprint_file=settings.blueprint_file,
                                   hyperframes_dir=settings.hyperframes_dir, voice=voice, content=content,
                                   available=not runtime.is_online, bus=bus)
    automation = AutomationService(db=db, bus=bus, tasks=tasks, youtube=youtube, public=public)
    registry = build_registry(ToolDeps(memory=memory, tasks=tasks, provider=provider, adapters=adapters,
                                       data_dir=runtime.data_dir, is_mock=lambda: provider.is_mock,
                                       youtube=youtube, automation=automation))
    agent_service = AgentService(db=db, bus=bus, agent=agent, provider=provider, registry=registry, memory=memory,
                                 tasks=tasks, chat=chat, approval_timeout_s=approval_timeout_s)
    ctx = AppContext(settings=settings, runtime=runtime, db=db, bus=bus, agent=agent, guard=guard,
                     provider=provider, adapters=adapters, tasks=tasks, chat=chat,
                     voice=voice, memory=memory, agent_service=agent_service, production=production,
                     automation=automation,
                     youtube=youtube, public=public, content=content,
                     cloud_ai=CloudAIService(provider=provider, store=secrets, bus=bus), auth=auth,
                     updates=UpdateService(guard=guard, repo=settings.update_repo, enabled=not runtime.is_online,
                                           root=Path(__file__).resolve().parents[2]),
                     local_ai=LocalAIService(provider=provider, runtime=runtime, db=db, bus=bus, tasks=tasks,
                                             source=ai_source),
                     migration_backup=str(backup) if backup else None)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        loop = asyncio.get_running_loop()
        bus.bind_loop(loop)
        agent.bind_loop(loop)
        tasks.register(system_check_kind(db=db, data_dir=runtime.data_dir, provider=provider, adapters=adapters,
                                         run_async=make_run_async(loop)))
        if isinstance(provider, LocalModelAdmin):
            tasks.register(model_eval_kind(db=db, admin=provider, run_async=make_run_async(loop)))
        tasks.register(agent_service.task_kind(make_run_async(loop)))
        for kind in content.task_kinds(make_run_async(loop)):
            tasks.register(kind)
        for kind in production.task_kinds(make_run_async(loop)):
            tasks.register(kind)
        tasks.register(automation.task_kind(make_run_async(loop)))
        public.purge_expired()
        agent_service.recover()
        automation.recover()
        recovered = tasks.recover_interrupted()
        log.info("zoi_started", version=__version__, mode=runtime.mode.value, provider=provider.name,
                 url=runtime.base_url, recovered_tasks=recovered, warnings=list(runtime.warnings))
        scheduler = asyncio.create_task(_automation_loop(automation, scheduler_interval_s))
        updater = asyncio.create_task(ctx.updates.loop()) if settings.update_check and not runtime.is_online else None
        try:
            yield
        finally:
            scheduler.cancel()
            if updater is not None:
                updater.cancel()
            await youtube.cancel_connect()
            for adapter in adapters:
                if hasattr(adapter, "stop"):
                    adapter.stop()
            await chat.wait_idle()
            tasks.shutdown()
            db.dispose()
            log.info("zoi_stopped")

    app = FastAPI(title="ZOI YouTube Intelligence", version=__version__, lifespan=lifespan,
                  docs_url="/api/docs" if runtime.is_development else None, redoc_url=None,
                  openapi_url="/api/openapi.json" if runtime.is_development else None)
    app.state.zoi = ctx
    app.add_exception_handler(ZoiError, zoi_error_handler)

    @app.middleware("http")
    async def guard_requests(request: Request, call_next):  # type: ignore[no-untyped-def]
        # CSRF: permintaan yang mengubah data wajib membawa header khusus (memaksa preflight CORS).
        if request.method in UNSAFE_METHODS and request.url.path.startswith("/api/") \
                and request.headers.get(CLIENT_HEADER) != "web":
            return JSONResponse(status_code=403, content={"error": {
                "code": "missing_client_header", "message": "Permintaan ditolak: header X-ZOI-Client tidak ada."}})
        path = request.url.path
        denied = remote_denied(runtime, request.headers)
        if denied:
            return JSONResponse(status_code=403, content={"error": {"code": "remote_denied", "message": denied}})
        if auth.enabled and path.startswith("/api/") \
                and not path.startswith(("/api/auth/", "/api/health", "/api/automation/wake")) \
                and not auth.check(request.cookies.get(SESSION_COOKIE)):
            return JSONResponse(status_code=401, content={"error": {
                "code": "belum_login", "message": "Sesi tidak ada atau kedaluwarsa. Masuk dahulu."}})
        response: Response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        if path.startswith("/api/"):
            # Data pribadi (chat, memori, data channel) tidak boleh disimpan cache browser/proxy.
            response.headers.setdefault("Cache-Control", "no-store")
        if runtime.is_online and runtime.public_url.startswith("https://"):
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000")
        return response

    hosts = list(TRUSTED_HOSTS)
    for extra in (runtime.public_host if runtime.is_online else None, runtime.remote_host):
        if extra:
            hosts.append(extra)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=hosts)
    if runtime.cors_origins:
        app.add_middleware(CORSMiddleware, allow_origins=list(runtime.cors_origins), allow_credentials=False,
                           allow_methods=["GET", "POST", "PUT"], allow_headers=["Content-Type", "X-ZOI-Client"])

    app.include_router(api_router)
    app.include_router(ws_router)

    @app.api_route("/api/{rest:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
                   include_in_schema=False)
    async def api_not_found(rest: str) -> JSONResponse:
        return JSONResponse(status_code=404, content={"error": {"code": "not_found",
                                                                "message": f"Endpoint /api/{rest} tidak ada."}})

    _mount_blueprint(app, production)
    _mount_frontend(app, runtime)
    return app


async def _automation_loop(automation: AutomationService, interval_s: float) -> None:
    """Penjadwal Phase 8: cek jadwal jatuh tempo selagi ZOI bangun. Saat pertama jalan = susulan."""
    while True:
        try:
            await asyncio.to_thread(automation.check_due, "jadwal")
        except Exception:  # noqa: BLE001 — penjadwal tidak boleh mati karena satu kegagalan
            log.exception("automation_check_failed")
        await asyncio.sleep(interval_s)


def _ws_sources(runtime: RuntimeConfig) -> str:
    if runtime.is_online and runtime.public_host:
        return f"wss://{runtime.public_host}"
    local = f"ws://127.0.0.1:{runtime.port} ws://localhost:{runtime.port}"
    return f"{local} wss://{runtime.remote_host}" if runtime.remote_host else local


# Salinan Blueprint Studio (Phase 7, ADR 0013): skrip inline milik file asli dan font Google yang memang dipakai
# file asli diizinkan HANYA di halaman ini; fetch hanya ke ZOI sendiri.
BLUEPRINT_CSP = ("default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline' "
                 "https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data: blob:; "
                 "connect-src 'self'; frame-ancestors 'self'; base-uri 'self'; form-action 'self'; object-src 'none'")


def _mount_blueprint(app: FastAPI, production: ProductionService) -> None:
    @app.get("/blueprint-studio/", include_in_schema=False)
    def blueprint_copy() -> Response:
        path = production.blueprint.copy_path
        if not production.available or not path.is_file():
            return HTMLResponse(status_code=404, content=(
                "<h1>Salinan Blueprint Studio belum dibuat</h1><p>Buka ZOI › Blueprint Studio lalu klik "
                "<b>Buat salinan</b>. Fitur ini hanya di laptop (mode local).</p>"))
        response = FileResponse(path, media_type="text/html")
        response.headers["Content-Security-Policy"] = BLUEPRINT_CSP
        response.headers["Cache-Control"] = "no-store"
        return response


def _mount_frontend(app: FastAPI, runtime: RuntimeConfig) -> None:
    if not runtime.serve_frontend:
        @app.get("/", include_in_schema=False)
        def dev_root() -> dict:
            return {"message": "ZOI backend (mode development). Buka antarmuka di http://127.0.0.1:5173",
                    "api_docs": "/api/docs"}
        return

    dist = runtime.frontend_dist
    index = dist / "index.html"
    # Pengecualian terbatas untuk avatar 3D (lihat docs/adr/0005-avatar-3d.md):
    #  blob: → AudioWorklet lip-sync & tekstur model; 'wasm-unsafe-eval' → dekompresi model (meshopt, WebAssembly).
    csp = ("default-src 'self'; script-src 'self' blob: 'wasm-unsafe-eval'; worker-src 'self' blob:; "
           "style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; media-src 'self' blob:; "
           f"connect-src 'self' blob: {_ws_sources(runtime)}; "
           "frame-ancestors 'none'; base-uri 'self'; form-action 'self'; object-src 'none'")

    @app.get("/{path:path}", include_in_schema=False)
    def frontend(path: str) -> Response:
        if not index.is_file():
            return HTMLResponse(status_code=503, content=(
                "<h1>Frontend ZOI belum di-build</h1><p>Folder <code>frontend/apps/web/dist</code> tidak "
                "ditemukan. Gunakan paket rilis yang sudah berisi frontend, atau jalankan "
                "<code>python -m app.cli doctor</code> untuk petunjuk.</p>"))
        target = (dist / path).resolve() if path else index
        if path and target.is_file() and _inside(target, dist):
            response: Response = FileResponse(target)
        else:
            response = FileResponse(index)
            response.headers["Cache-Control"] = "no-cache"  # index.html selalu dicek ulang → update langsung terlihat
        response.headers["Content-Security-Policy"] = csp
        return response


def _inside(target: Path, root: Path) -> bool:
    try:
        target.relative_to(root.resolve())
    except ValueError:
        return False
    return True
