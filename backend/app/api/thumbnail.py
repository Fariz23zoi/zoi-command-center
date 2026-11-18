"""API Thumbnail otomatis — AI ZOI menulis teks hook; gambar disusun di browser."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from app.context import AppContext, get_ctx
from app.thumbnail import thumbnail_hook

router = APIRouter(prefix="/thumbnail", tags=["thumbnail"])


class HookBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    topik: str = Field(min_length=3, max_length=6000)
    rasio: Literal["9:16", "16:9"] = "9:16"


@router.post("/hook")
async def hook(body: HookBody, ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    return await thumbnail_hook(ctx.provider, body.topik, body.rasio)
