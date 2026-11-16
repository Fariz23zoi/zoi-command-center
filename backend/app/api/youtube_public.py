"""API data publik YouTube (Phase 6B): channel pantauan, Trending resmi, pencarian, rangkuman tema."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from app.context import AppContext, get_ctx

router = APIRouter(prefix="/youtube/public")


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CompetitorIn(_Strict):
    ref: str = Field(min_length=3, max_length=300)
    note: str = Field(default="", max_length=200)


class TrendingIn(_Strict):
    category_id: str | None = Field(default=None, max_length=4)


class SearchIn(_Strict):
    query: str = Field(min_length=2, max_length=100)


class KeyIn(_Strict):
    key: str = Field(min_length=3, max_length=120)


@router.get("/competitors")
async def competitors(ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    return ctx.public.competitors()


@router.post("/competitors")
async def add_competitor(body: CompetitorIn, ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    return await ctx.public.add_competitor(body.ref, body.note)


@router.post("/competitors/{channel_id}/refresh")
async def refresh_competitor(channel_id: str, ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    return await ctx.public.refresh_competitor(channel_id)


@router.delete("/competitors/{channel_id}")
async def remove_competitor(channel_id: str, ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    return ctx.public.remove_competitor(channel_id)


@router.get("/viral")
async def viral(ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    return ctx.public.viral()


@router.post("/trending")
async def trending(body: TrendingIn, ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    return await ctx.public.refresh_trending(body.category_id)


@router.post("/search")
async def search(body: SearchIn, ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    return await ctx.public.search(body.query)


@router.post("/lists/remove")
async def remove_list(body: KeyIn, ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    return ctx.public.remove_list(body.key)


@router.post("/themes")
async def themes(body: KeyIn, ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    """Memulai tugas: AI lokal merangkum tema dari JUDUL satu daftar tersimpan."""
    ctx.public.titles(body.key)  # gagal cepat bila daftar tidak ada
    return ctx.tasks.submit("trend_themes", {"key": body.key})
