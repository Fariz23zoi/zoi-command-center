"""API memori (Phase 5): lihat, cari, tambah, ubah, hapus. Memori dari pengguna langsung tidak butuh izin."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field

from app.context import AppContext, get_ctx
from app.core.errors import ZoiError

router = APIRouter(prefix="/memories")
CONFIRM_DELETE_ALL = "HAPUS SEMUA"


class MemoryIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    content: str = Field(min_length=1, max_length=1000)
    kind: Literal["fakta", "preferensi", "proyek"] = "fakta"


class MemoryPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    content: str | None = Field(default=None, min_length=1, max_length=1000)
    kind: Literal["fakta", "preferensi", "proyek"] | None = None


@router.get("")
def list_memories(q: str | None = Query(default=None, max_length=200), limit: int = Query(default=50, ge=1, le=200),
                  offset: int = Query(default=0, ge=0), ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    return ctx.memory.list(query=q, limit=limit, offset=offset)


@router.post("", status_code=201)
def create_memory(body: MemoryIn, ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    item = ctx.memory.create(body.content, kind=body.kind, source="pengguna", is_mock=False)
    ctx.bus.publish("memory.updated", {"id": item["id"]})
    return item


@router.put("/{memory_id}")
def update_memory(memory_id: str, body: MemoryPatch, ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    item = ctx.memory.update(memory_id, content=body.content, kind=body.kind)
    ctx.bus.publish("memory.updated", {"id": memory_id})
    return item


@router.delete("/{memory_id}", status_code=204)
def delete_memory(memory_id: str, ctx: AppContext = Depends(get_ctx)) -> None:
    ctx.memory.delete(memory_id)
    ctx.bus.publish("memory.updated", {"id": memory_id})


@router.delete("")
def delete_all(confirm: str = Query(default=""), ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    if confirm != CONFIRM_DELETE_ALL:
        raise ZoiError(f"Ketik '{CONFIRM_DELETE_ALL}' untuk menghapus semua memori.", code="confirm_required")
    deleted = ctx.memory.delete_all()
    ctx.bus.publish("memory.updated", {"id": None})
    return {"deleted": deleted}
