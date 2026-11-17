from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from app.context import AppContext, get_ctx

router = APIRouter(prefix="/update", tags=["update"])


@router.get("/status")
def update_status(ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    return ctx.updates.status()


@router.post("/check")
async def update_check(ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    return await ctx.updates.check()


@router.post("/install")
async def update_install(ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    return await ctx.updates.install()
