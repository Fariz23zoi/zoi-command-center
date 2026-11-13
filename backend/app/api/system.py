from __future__ import annotations

import json
import time
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select

from app import __version__
from app.context import AppContext, get_ctx
from app.db.models import AppMeta
from app.system import detectors

router = APIRouter()
STATUS_CACHE_S = 15.0


@router.get("/config")
def public_config(ctx: AppContext = Depends(get_ctx)) -> dict:
    """Konfigurasi efektif (hanya-baca). Diubah lewat file .env, bukan dari UI."""
    rt = ctx.runtime
    return {
        "version": __version__,
        "mode": rt.mode.value,
        "banner": rt.banner,
        "provider": rt.provider,
        "is_mock": ctx.provider.is_mock,
        "ollama_url": rt.ollama_url if rt.provider == "ollama" else None,
        "ollama_model": rt.ollama_model or None,
        "avatar_mode": rt.avatar_mode.value,
        "host": rt.host,
        "port": rt.port,
        "base_url": rt.base_url,
        "data_dir": str(rt.data_dir),
        "warnings": list(rt.warnings),
        "migration_backup": ctx.migration_backup,
        "config_source": "environment variable / file .env (ubah lalu restart ZOI)",
    }


@router.get("/system/status")
def system_status(ctx: AppContext = Depends(get_ctx)) -> dict:
    cached = ctx.cache.get("system_status")
    if cached and time.monotonic() - cached[0] < STATUS_CACHE_S:
        return cached[1]
    data = {
        "source": "deteksi langsung di mesin ini",
        "checked_at": detectors.now_iso(),
        "python": detectors.python_info(),
        "os": detectors.os_info(),
        "resources": detectors.resources(ctx.runtime.data_dir),
        "tools": {name: detectors.detect_tool(name) for name in detectors.TOOLS},
    }
    ctx.cache["system_status"] = (time.monotonic(), data)
    return data


@router.get("/provider/status")
async def provider_status(ctx: AppContext = Depends(get_ctx)) -> dict:
    return (await ctx.provider.health()).to_dict()


@router.get("/adapters")
def adapters(ctx: AppContext = Depends(get_ctx)) -> dict:
    return {"adapters": [a.detect().to_dict() for a in ctx.adapters]}


@router.get("/agent/state")
def agent_state(ctx: AppContext = Depends(get_ctx)) -> dict:
    return ctx.agent.snapshot()


class Preferences(BaseModel):
    """Preferensi portabel (ikut berpindah bersama database). Bukan konfigurasi mesin."""

    model_config = ConfigDict(extra="forbid")
    ui_language: Literal["id", "en"] = "id"
    avatar_mode_preference: Literal["auto", "2d", "3d"] = "auto"


PREF_KEY = "preferences"


@router.get("/preferences")
def get_preferences(ctx: AppContext = Depends(get_ctx)) -> Preferences:
    with ctx.db.session() as s:
        row = s.get(AppMeta, PREF_KEY)
        return Preferences.model_validate(json.loads(row.value_json)) if row else Preferences()


@router.put("/preferences")
def put_preferences(prefs: Preferences, ctx: AppContext = Depends(get_ctx)) -> Preferences:
    with ctx.db.session() as s:
        row = s.get(AppMeta, PREF_KEY)
        payload = prefs.model_dump_json()
        if row is None:
            s.add(AppMeta(key=PREF_KEY, value_json=payload))
        else:
            row.value_json = payload
    ctx.bus.publish("preferences.updated", prefs.model_dump())
    return prefs


@router.get("/network/audit")
def network_audit(limit: int = 50, ctx: AppContext = Depends(get_ctx)) -> dict:
    from app.db.models import NetworkAudit

    with ctx.db.session() as s:
        rows = s.scalars(select(NetworkAudit).order_by(NetworkAudit.id.desc()).limit(min(limit, 500))).all()
        return {"entries": [{"at": r.at.isoformat(), "host": r.host, "method": r.method, "path": r.path,
                             "allowed": r.allowed, "reason": r.reason} for r in rows]}
