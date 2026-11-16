"""API Settings › AI Cloud. API key hanya masuk (PUT) dan tidak pernah keluar."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from app.context import AppContext, get_ctx

router = APIRouter(prefix="/ai/cloud")


class KeyIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str = Field(min_length=10, max_length=400)


@router.get("/status")
async def status(ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    return ctx.cloud_ai.status()


@router.put("/keys/{name}")
async def put_key(name: str, body: KeyIn, ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    return ctx.cloud_ai.set_key(name, body.key)


@router.delete("/keys/{name}")
async def delete_key(name: str, ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    return ctx.cloud_ai.delete_key(name)


@router.get("/models/{name}")
async def models(name: str, ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    return await ctx.cloud_ai.models(name)


@router.post("/test/{name}")
async def test(name: str, ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    return await ctx.cloud_ai.test(name)
