"""API draf konten (Phase 6B): ide dan naskah & storyboard oleh AI lokal. Tidak ada yang dipublikasikan."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, Response

from app.content.package import PackageError, build_package, package_bytes, package_filename
from app.content.service import IdeaRequest, ScriptRequest
from app.context import AppContext, get_ctx
from app.core.errors import ZoiError

router = APIRouter(prefix="/content")


@router.get("/items")
async def items(kind: Literal["ideas", "script"], ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    provider = ctx.content.provider
    return {"items": ctx.content.items(kind), "is_mock": provider.is_mock, "provider": provider.name}


@router.post("/ideas")
async def ideas(body: IdeaRequest, ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    return ctx.tasks.submit("content_ideas", body.model_dump())


@router.post("/scripts")
async def scripts(body: ScriptRequest, ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    return ctx.tasks.submit("content_script", body.model_dump())


@router.get("/items/{item_id}/package")
async def download_package(item_id: str, ctx: AppContext = Depends(get_ctx)) -> Response:
    """Unduh paket produksi (zoi.paket/v1) dari sebuah naskah — untuk Blueprint Studio di laptop."""
    item = ctx.content.item(item_id)
    if item is None:
        raise ZoiError("Draf tidak ditemukan.", status_code=404, code="not_found")
    try:
        package = build_package(item)
    except PackageError as exc:
        raise ZoiError(str(exc)) from exc
    return Response(package_bytes(package), media_type="application/json", headers={
        "Content-Disposition": f'attachment; filename="{package_filename(package)}"'})


@router.delete("/items/{item_id}", status_code=204)
async def delete_item(item_id: str, ctx: AppContext = Depends(get_ctx)) -> None:
    if not ctx.content.delete(item_id):
        raise ZoiError("Draf tidak ditemukan.", status_code=404, code="not_found")
