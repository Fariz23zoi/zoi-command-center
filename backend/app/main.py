"""App factory ZOI. Satu fungsi membangun seluruh aplikasi dari konfigurasi environment."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response

from app import __version__
from app.api.router import api_router, ws_router
from app.chat.service import ChatService
from app.config.modes import RuntimeConfig, resolve_runtime
from app.config.settings import Settings, load_settings
from app.context import AppContext
from app.core.agent_state import AgentStateTracker
from app.core.errors import ZoiError, zoi_error_handler
from app.core.events import EventBus
from app.db.migrations import upgrade_database
from app.db.models import NetworkAudit
from app.db.session import Database, db_path
from app.integrations.blueprint.adapter import BlueprintAdapter
from app.integrations.clipper.adapter import ClipperAdapter
from app.logging_setup import configure_logging, get_logger
from app.providers.registry import build_provider
from app.security.cost_guard import CostGuard
from app.tasks.builtin import make_run_async, system_check_kind
from app.tasks.manager import TaskManager

log = get_logger("main")

TRUSTED_HOSTS = ["127.0.0.1", "localhost", "[::1]", "::1"]
UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
CLIENT_HEADER = "x-zoi-client"


def create_app(settings: Settings | None = None, *, return_to_idle_s: float = 2.5) -> FastAPI:
    settings = settings or load_settings()
    runtime = resolve_runtime(settings)

    runtime.data_dir.mkdir(parents=True, exist_ok=True)
    configure_logging(runtime.data_dir / "logs", settings.log_level.value)
    backup = upgrade_database(db_path(runtime.data_dir))
    db = Database(db_path(runtime.data_dir))
    bus = EventBus()
    agent = AgentStateTracker(bus, return_to_idle_s=return_to_idle_s)

    def record(host: str, method: str, path: str, allowed: bool, reason: str) -> None:
        with db.session() as s:
            s.add(NetworkAudit(host=host, method=method, path=path[:500], allowed=allowed, reason=reason))
        if not allowed:
            log.warning("cost_guard_blocked", host=host, method=method, reason=reason)

    guard = CostGuard.build(ollama_url=runtime.ollama_url, extra_hosts=settings.extra_hosts, recorder=record)
    provider = build_provider(runtime, guard)
    adapters = [ClipperAdapter(settings.clipper_dir, settings.clipper_python),
                BlueprintAdapter(settings.blueprint_file)]
    tasks = TaskManager(db, bus, agent)
    chat = ChatService(db, bus, agent, provider)
    ctx = AppContext(settings=settings, runtime=runtime, db=db, bus=bus, agent=agent, guard=guard,
                     provider=provider, adapters=adapters, tasks=tasks, chat=chat,
                     migration_backup=str(backup) if backup else None)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        loop = asyncio.get_running_loop()
        bus.bind_loop(loop)
        agent.bind_loop(loop)
        tasks.register(system_check_kind(db=db, data_dir=runtime.data_dir, provider=provider, adapters=adapters,
                                         run_async=make_run_async(loop)))
        recovered = tasks.recover_interrupted()
        log.info("zoi_started", version=__version__, mode=runtime.mode.value, provider=provider.name,
                 url=runtime.base_url, recovered_tasks=recovered, warnings=list(runtime.warnings))
        try:
            yield
        finally:
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
        response: Response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        return response

    app.add_middleware(TrustedHostMiddleware, allowed_hosts=TRUSTED_HOSTS)
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

    _mount_frontend(app, runtime)
    return app


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
           f"connect-src 'self' blob: ws://127.0.0.1:{runtime.port} ws://localhost:{runtime.port}; "
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
        response.headers["Content-Security-Policy"] = csp
        return response


def _inside(target: Path, root: Path) -> bool:
    try:
        target.relative_to(root.resolve())
    except ValueError:
        return False
    return True
