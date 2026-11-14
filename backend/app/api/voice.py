"""API suara (Phase 4). Tipis: logika di app.voice.service.VoiceService. Rekaman tidak pernah disimpan."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field

from app.context import AppContext, get_ctx
from app.core.errors import ZoiError
from app.voice.base import MAX_AUDIO_BYTES, MAX_TTS_CHARS, VoiceError
from app.voice.service import VoicePreferences

router = APIRouter(prefix="/voice")


def _fail(exc: VoiceError) -> ZoiError:
    return ZoiError(str(exc), code="voice_error")


@router.get("/status")
async def status(ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    return await ctx.voice.status()


@router.get("/preferences")
def get_preferences(ctx: AppContext = Depends(get_ctx)) -> VoicePreferences:
    return ctx.voice.preferences()


@router.put("/preferences")
def put_preferences(prefs: VoicePreferences, ctx: AppContext = Depends(get_ctx)) -> VoicePreferences:
    saved = ctx.voice.save_preferences(prefs)
    ctx.bus.publish("voice.preferences.updated", saved.model_dump())
    return saved


@router.post("/transcribe")
async def transcribe(
    request: Request,
    language: Literal["id", "en", "auto"] | None = Query(default=None),
    ctx: AppContext = Depends(get_ctx),
) -> dict[str, Any]:
    """Badan permintaan = audio mentah (webm/ogg/wav). Diproses di memori lalu dibuang."""
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > MAX_AUDIO_BYTES:
        raise ZoiError(f"Rekaman terlalu besar (maks. {MAX_AUDIO_BYTES // (1024 * 1024)} MB).", status_code=413,
                       code="too_large")
    audio = await request.body()
    try:
        return await ctx.voice.transcribe(audio, language)
    except VoiceError as exc:
        raise _fail(exc) from exc


class SpeakRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=MAX_TTS_CHARS * 2)


@router.post("/speak")
async def speak(body: SpeakRequest, ctx: AppContext = Depends(get_ctx)) -> Response:
    try:
        audio = await ctx.voice.speak(body.text)
    except VoiceError as exc:
        raise _fail(exc) from exc
    return Response(audio, media_type="audio/wav", headers={"Cache-Control": "no-store"})
