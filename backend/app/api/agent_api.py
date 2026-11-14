"""API agen (Phase 5). Tipis: logika di app.agent.service.AgentService."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field

from app.context import AppContext, get_ctx

router = APIRouter(prefix="/agent")


class PlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request: str = Field(min_length=1, max_length=4000)
    conversation_id: str | None = None


class DecisionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["approve", "reject"]


class PermissionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: Literal["ask", "auto"]


@router.get("/status")
async def status(ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    available, detail = await ctx.agent_service.availability()
    return {"available": available, "detail": detail, "tools": ctx.agent_service.tools(), "can_publish": False}


@router.post("/plan", status_code=202)
async def plan(body: PlanRequest, ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    return await ctx.agent_service.request_plan(body.request, body.conversation_id)


@router.get("/runs")
def runs(conversation_id: str | None = Query(default=None), ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    return {"runs": ctx.agent_service.list(conversation_id)}


@router.get("/runs/{run_id}")
def run(run_id: str, ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    return ctx.agent_service.get(run_id)


@router.post("/runs/{run_id}/approve")
def approve(run_id: str, ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    return ctx.agent_service.approve(run_id)


@router.post("/runs/{run_id}/reject")
def reject(run_id: str, ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    return ctx.agent_service.reject(run_id)


@router.post("/runs/{run_id}/cancel")
def cancel(run_id: str, ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    return ctx.agent_service.cancel(run_id)


@router.post("/approvals/{approval_id}")
def decide(approval_id: str, body: DecisionIn, ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    return ctx.agent_service.decide(approval_id, body.decision)


@router.get("/approvals")
def approvals(ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    return {"approvals": ctx.agent_service.approvals_log()}


@router.put("/tools/{name}/permission")
def set_permission(name: str, body: PermissionIn, ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    return {"tools": ctx.agent_service.set_tool_permission(name, body.mode)}
