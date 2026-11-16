"""API YouTube (Phase 6A): hubungkan akun lewat OAuth, lihat data channel sendiri, kuota, putuskan & hapus.

Tidak ada endpoint yang mengunggah/mengubah apa pun di YouTube — scope yang diminta hanya-baca.
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, ConfigDict

from app.context import AppContext, get_ctx

router = APIRouter(prefix="/youtube")


class ClientIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    config: dict[str, Any]


class RefreshIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    what: Literal["all", "channel", "videos", "analytics"] = "all"


@router.get("/status")
async def status(ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    return await ctx.youtube.status()


@router.put("/client")
async def put_client(body: ClientIn, ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    return ctx.youtube.import_client(body.config)


@router.delete("/client", status_code=204)
async def delete_client(ctx: AppContext = Depends(get_ctx)) -> None:
    ctx.youtube.delete_client()


@router.post("/connect")
async def connect(ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    return await ctx.youtube.start_connect()


@router.post("/connect/cancel", status_code=204)
async def cancel(ctx: AppContext = Depends(get_ctx)) -> None:
    await ctx.youtube.cancel_connect()


@router.get("/callback", include_in_schema=False)
async def oauth_callback(request: Request, ctx: AppContext = Depends(get_ctx)) -> RedirectResponse:
    """Alamat balik Google di mode online. Hasil (sukses/galat) terlihat di Settings › YouTube."""
    await ctx.youtube.handle_web_callback({k: v for k, v in request.query_params.items()})
    return RedirectResponse("/settings/youtube", status_code=303)


@router.post("/disconnect")
async def disconnect(ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    return await ctx.youtube.disconnect()


@router.post("/refresh")
async def refresh(body: RefreshIn, ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    yt = ctx.youtube
    if body.what == "all":
        return await yt.refresh_all()
    if body.what == "channel":
        await yt.refresh_channel()
    elif body.what == "videos":
        await yt.refresh_videos()
    else:
        await yt.refresh_analytics()
    return yt.data()


@router.post("/videos/{video_id}/retention")
async def video_retention(video_id: str, force: bool = False, ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    return await ctx.youtube.video_retention(video_id, force=force)


@router.get("/data")
async def data(ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    return ctx.youtube.data()
