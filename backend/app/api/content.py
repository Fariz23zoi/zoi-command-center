"""API draf konten (Phase 6B): ide dan naskah & storyboard oleh AI lokal. Tidak ada yang dipublikasikan."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends

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


@router.delete("/items/{item_id}", status_code=204)
async def delete_item(item_id: str, ctx: AppContext = Depends(get_ctx)) -> None:
    if not ctx.content.delete(item_id):
        raise ZoiError("Draf tidak ditemukan.", status_code=404, code="not_found")
