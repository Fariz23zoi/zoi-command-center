"""API otomatisasi & notifikasi (Phase 8)."""

from __future__ import annotations

import hmac
from typing import Any, Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field

from app.automation.service import KINDS, AutomationError
from app.context import AppContext, get_ctx
from app.core.errors import ZoiError

router = APIRouter(prefix="/automation", tags=["automation"])


class ScheduleBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    frequency: Literal["daily", "weekly"] = "daily"
    hour: int = Field(default=7, ge=0, le=23)
    minute: int = Field(default=0, ge=0, le=59)
    weekday: int = Field(default=0, ge=0, le=6)


class CreateBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: str
    name: str = Field(default="", max_length=120)
    schedule: ScheduleBody = ScheduleBody()
    params: dict[str, Any] = {}


class UpdateBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool | None = None
    name: str | None = Field(default=None, max_length=120)
    schedule: ScheduleBody | None = None
    params: dict[str, Any] | None = None


def _wrap(exc: AutomationError) -> ZoiError:
    return ZoiError(exc.message, status_code=exc.status_code)


@router.get("")
def overview(ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    rt = ctx.runtime
    return {"items": ctx.automation.list(), "kinds": KINDS, "runs": ctx.automation.runs(limit=30),
            "wake_enabled": bool(ctx.settings.wake_token), "online": rt.is_online,
            "timezone": "Asia/Jakarta (WIB)"}


@router.post("")
def create(body: CreateBody, ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    try:
        return ctx.automation.create(body.kind, body.name, body.schedule.model_dump(), body.params)
    except AutomationError as exc:
        raise _wrap(exc) from exc


@router.patch("/{automation_id}")
def update(automation_id: str, body: UpdateBody, ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    try:
        return ctx.automation.update(automation_id, enabled=body.enabled, name=body.name,
                                     schedule=body.schedule.model_dump() if body.schedule else None,
                                     params=body.params)
    except AutomationError as exc:
        raise _wrap(exc) from exc


@router.delete("/{automation_id}", status_code=204)
def remove(automation_id: str, ctx: AppContext = Depends(get_ctx)) -> None:
    try:
        ctx.automation.delete(automation_id)
    except AutomationError as exc:
        raise _wrap(exc) from exc


@router.post("/{automation_id}/run")
def run_now(automation_id: str, ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    try:
        return ctx.automation.run_now(automation_id)
    except AutomationError as exc:
        raise _wrap(exc) from exc


@router.get("/{automation_id}/runs")
def runs(automation_id: str, ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    return {"items": ctx.automation.runs(automation_id)}


@router.post("/wake", include_in_schema=False)
def wake(request: Request, ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    """Dipanggil workflow GitHub Actions untuk membangunkan ZOI. Token Bearer, bukan sesi login."""
    token = ctx.settings.wake_token
    header = request.headers.get("authorization", "")
    given = header.removeprefix("Bearer ").strip() if header.startswith("Bearer ") else ""
    if not token or not given or not hmac.compare_digest(given, token):
        raise ZoiError("Token bangun tidak valid.", status_code=401, code="wake_denied")
    started = ctx.automation.check_due("bangun")
    return {"ok": True, "started": len(started)}


notifications_router = APIRouter(prefix="/notifications", tags=["notifications"])


@notifications_router.get("")
def notifications(ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    return ctx.automation.notifications()


@notifications_router.post("/read")
def mark_all_read(ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    ctx.automation.mark_read()
    return ctx.automation.notifications()


@notifications_router.post("/{notification_id}/read")
def mark_read(notification_id: str, ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    ctx.automation.mark_read(notification_id)
    return ctx.automation.notifications()
