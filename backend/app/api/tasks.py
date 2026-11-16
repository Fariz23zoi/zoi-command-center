from __future__ import annotations

from fastapi import APIRouter, Depends

from app.context import AppContext, get_ctx
from app.core.errors import NotFound

router = APIRouter()


@router.get("/tasks")
def list_tasks(ctx: AppContext = Depends(get_ctx)) -> dict:
    return {"tasks": ctx.tasks.list()}


@router.get("/tasks/{task_id}")
def get_task(task_id: str, ctx: AppContext = Depends(get_ctx)) -> dict:
    try:
        return ctx.tasks.get(task_id, with_events=True)
    except KeyError as exc:
        raise NotFound("Tugas tidak ditemukan.") from exc


@router.post("/tasks/system-check", status_code=202)
def run_system_check(ctx: AppContext = Depends(get_ctx)) -> dict:
    return ctx.tasks.submit("system_check")


@router.post("/tasks/{task_id}/cancel")
def cancel_task(task_id: str, ctx: AppContext = Depends(get_ctx)) -> dict:
    try:
        return ctx.tasks.cancel(task_id)
    except KeyError as exc:
        raise NotFound("Tugas tidak ditemukan.") from exc
