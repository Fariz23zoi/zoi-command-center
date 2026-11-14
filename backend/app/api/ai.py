"""API AI lokal (Phase 3). Tipis: semua logika di app.ai.local.LocalAIService."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from app.ai import evaluation
from app.context import AppContext, get_ctx
from app.core.errors import NotFound, ZoiError

router = APIRouter(prefix="/ai")


class ModelName(BaseModel):
    model_config = ConfigDict(extra="forbid")
    model: str = Field(min_length=1, max_length=120)


@router.get("/status")
async def status(ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    return await ctx.local_ai.status()


@router.post("/test")
async def test_connection(ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    return await ctx.local_ai.test()


@router.get("/model")
async def model_details(name: str, ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    return await ctx.local_ai.details(name)


@router.put("/active-model")
async def set_active_model(body: ModelName, ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    return await ctx.local_ai.set_active(body.model)


@router.delete("/active-model")
def reset_active_model(ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    return ctx.local_ai.reset_active()


@router.post("/unload")
async def unload(body: ModelName, ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    return await ctx.local_ai.unload(body.model)


@router.get("/evaluations")
def list_evaluations(ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    return {"evaluations": evaluation.list_evaluations(ctx.db),
            "prompts": [{k: p[k] for k in ("id", "category", "prompt")} for p in evaluation.load_prompts()["prompts"]]}


@router.post("/evaluations", status_code=202)
async def start_evaluation(body: ModelName, ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    return await ctx.local_ai.start_evaluation(body.model)


@router.get("/evaluations/{evaluation_id}")
def get_evaluation(evaluation_id: str, ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    found = evaluation.get_evaluation(ctx.db, evaluation_id)
    if found is None:
        raise NotFound("Hasil uji tidak ditemukan.")
    return found


class Rating(BaseModel):
    model_config = ConfigDict(extra="forbid")
    prompt_id: str = Field(max_length=8)
    rating: Literal["up", "down"] | None


@router.put("/evaluations/{evaluation_id}/rating")
def rate_evaluation(evaluation_id: str, body: Rating, ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    try:
        found = evaluation.rate(ctx.db, evaluation_id, body.prompt_id, body.rating)
    except KeyError as exc:
        raise ZoiError("Hanya jawaban percakapan yang dinilai pengguna.", code="not_ratable") from exc
    if found is None:
        raise NotFound("Hasil uji tidak ditemukan.")
    return found
