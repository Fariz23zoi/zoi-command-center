"""API Produksi Konten (Phase 7) — hanya berfungsi di laptop (mode development/local)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field

from app.context import AppContext, get_ctx
from app.core.errors import ZoiError
from app.production.blueprint_ai import blueprint_json
from app.production.service import ProductionError

router = APIRouter(prefix="/production", tags=["production"])


class ImportBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    package: dict[str, Any] | None = None
    script_id: str | None = Field(default=None, max_length=64)


def _wrap(exc: ProductionError) -> ZoiError:
    return ZoiError(exc.message, status_code=exc.status_code)


@router.get("/status")
async def status(ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    return await ctx.production.status()


@router.get("/packages")
def packages(ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    return {"items": ctx.production.list() if ctx.production.available else []}


@router.post("/packages")
def import_package(body: ImportBody, ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    try:
        if body.script_id:
            return ctx.production.from_script(body.script_id)
        if body.package is None:
            raise ProductionError("Kirim paket (file JSON) atau pilih naskah.")
        return ctx.production.import_package(body.package)
    except ProductionError as exc:
        raise _wrap(exc) from exc


@router.delete("/packages/{package_id}", status_code=204)
def delete_package(package_id: str, ctx: AppContext = Depends(get_ctx)) -> None:
    try:
        ctx.production.delete(package_id)
    except ProductionError as exc:
        raise _wrap(exc) from exc


@router.get("/packages/{package_id}/files/{name}")
def package_file(package_id: str, name: str, ctx: AppContext = Depends(get_ctx)) -> FileResponse:
    try:
        path, media = ctx.production.file(package_id, name)
    except ProductionError as exc:
        raise _wrap(exc) from exc
    return FileResponse(path, media_type=media, filename=f"{package_id}-{name}")


@router.post("/packages/{package_id}/narrate")
async def narrate(package_id: str, ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    try:
        ctx.production.get(package_id)
        narration = (await ctx.production.status())["narration"]
        if not narration or not narration["available"]:
            raise ProductionError((narration or {}).get("problem") or "Narasi tidak tersedia.", 409)
    except ProductionError as exc:
        raise _wrap(exc) from exc
    return ctx.tasks.submit("production_narrate", {"package_id": package_id})


@router.post("/packages/{package_id}/render")
def render(package_id: str, ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    try:
        ctx.production.get(package_id)
        hf = ctx.production.hyperframes.status()
        if not hf["enabled"]:
            raise ProductionError("HyperFrames belum siap: " + " ".join(hf["problems"]), 409)
    except ProductionError as exc:
        raise _wrap(exc) from exc
    return ctx.tasks.submit("production_render", {"package_id": package_id})


@router.post("/packages/{package_id}/animate")
def animate(package_id: str, ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    """AI ZOI merancang adegan animasi dari paket (gaya dari Blueprint), lalu HyperFrames me-render video."""
    try:
        ctx.production.get(package_id)
        if not ctx.production.hyperframes.status()["enabled"]:
            raise ProductionError("HyperFrames belum siap — pasang dulu (lihat Content Production).", 409)
    except ProductionError as exc:
        raise _wrap(exc) from exc
    return ctx.tasks.submit("production_animate", {"package_id": package_id})


@router.post("/blueprint/build")
def build_blueprint(ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    from app.production.blueprint import BlueprintCopyError
    try:
        return ctx.production.build_blueprint()
    except (ProductionError, BlueprintCopyError) as exc:
        raise ZoiError(getattr(exc, "message", str(exc))) from exc


class BlueprintAIBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    prompt: str = Field(min_length=1, max_length=30_000)


@router.post("/blueprint/ai")
async def blueprint_ai(body: BlueprintAIBody, ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    """Pengganti `claude.use("sample").json()` di salinan Blueprint Studio: memakai AI Brain ZOI (gratis)."""
    return await blueprint_json(ctx.provider, body.prompt)
