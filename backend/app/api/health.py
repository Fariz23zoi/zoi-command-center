from __future__ import annotations

import time

from fastapi import APIRouter, Depends

from app import __version__
from app.context import AppContext, get_ctx

router = APIRouter()


@router.get("/health")
def health(ctx: AppContext = Depends(get_ctx)) -> dict:
    return {"status": "ok", "version": __version__, "mode": ctx.runtime.mode.value,
            "uptime_s": round(time.monotonic() - ctx.started_monotonic, 1)}
