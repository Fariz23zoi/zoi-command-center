"""Tool awal Phase 5 — hanya kemampuan yang benar-benar ada. Tidak ada tool tiruan."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.agent.tools import NoArgs, Permission, Tool, ToolError, ToolRegistry
from app.core.errors import NotFound, ZoiError
from app.integrations.base import ExternalAppAdapter
from app.memory.service import MemoryService
from app.providers.base import LLMProvider
from app.system import detectors
from app.tasks.manager import TaskManager


@dataclass
class ToolDeps:
    memory: MemoryService
    tasks: TaskManager
    provider: LLMProvider
    adapters: list[ExternalAppAdapter]
    data_dir: Any
    is_mock: Callable[[], bool]


class SearchArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kata_kunci: str = Field(min_length=2, max_length=200, description="Kata kunci yang dicari di memori")


class SaveArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    isi: str = Field(min_length=2, max_length=1000, description="Isi memori yang disimpan")
    jenis: Literal["fakta", "preferensi", "proyek"] = "fakta"


class UpdateArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=8, max_length=36, description="ID memori (dari cari_memori)")
    isi: str = Field(min_length=2, max_length=1000)


class DeleteArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=8, max_length=36, description="ID memori (dari cari_memori)")


class TaskListArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    jumlah: int = Field(default=5, ge=1, le=20)


def build_registry(deps: ToolDeps) -> ToolRegistry:
    registry = ToolRegistry()

    def add(name: str, description: str, permission: Permission, args: type[BaseModel] = NoArgs):
        def wrap(func):
            async def run(parsed: Any) -> dict[str, Any]:
                try:
                    return await func(parsed)
                except (NotFound, ZoiError) as exc:
                    raise ToolError(exc.message) from exc

            registry.register(Tool(name, description, permission, args, run))
            return func

        return wrap

    @add("waktu_sekarang", "Tanggal dan jam saat ini di komputer ini.", Permission.READ)
    async def _now(_: NoArgs) -> dict[str, Any]:
        now = datetime.now().astimezone()
        return {"waktu": now.isoformat(timespec="seconds"), "zona": now.tzname()}

    @add("cari_memori", "Mencari catatan di memori jangka panjang berdasarkan kata kunci.", Permission.READ,
         SearchArgs)
    async def _search(args: SearchArgs) -> dict[str, Any]:
        found = deps.memory.search(args.kata_kunci, limit=10)
        return {"jumlah": len(found), "memori": [{k: m[k] for k in ("id", "kind", "content")} for m in found]}

    @add("simpan_memori", "Menyimpan catatan baru ke memori jangka panjang.", Permission.WRITE_LOCAL, SaveArgs)
    async def _save(args: SaveArgs) -> dict[str, Any]:
        item = deps.memory.create(args.isi, kind=args.jenis, source="agen", is_mock=deps.is_mock())
        return {"disimpan": {k: item[k] for k in ("id", "kind", "content")}}

    @add("ubah_memori", "Mengubah isi catatan memori yang sudah ada.", Permission.WRITE_LOCAL, UpdateArgs)
    async def _update(args: UpdateArgs) -> dict[str, Any]:
        item = deps.memory.update(args.id, content=args.isi)
        return {"diubah": {k: item[k] for k in ("id", "kind", "content")}}

    @add("hapus_memori", "Menghapus satu catatan memori.", Permission.WRITE_LOCAL, DeleteArgs)
    async def _delete(args: DeleteArgs) -> dict[str, Any]:
        before = deps.memory.get(args.id)
        deps.memory.delete(args.id)
        return {"dihapus": {k: before[k] for k in ("id", "content")}}

    @add("status_sistem", "Kondisi komputer ini saat ini: Python, sistem operasi, RAM, disk, dan alat yang terpasang.",
         Permission.READ)
    async def _system(_: NoArgs) -> dict[str, Any]:
        return {"sumber": "deteksi langsung di mesin ini", "python": detectors.python_info(),
                "os": detectors.os_info(), "sumber_daya": detectors.resources(deps.data_dir),
                "alat": {name: detectors.detect_tool(name) for name in detectors.TOOLS}}

    @add("jalankan_pemeriksaan_sistem", "Menjalankan tugas pemeriksaan sistem lengkap di Task Manager.",
         Permission.WRITE_LOCAL)
    async def _check(_: NoArgs) -> dict[str, Any]:
        task = deps.tasks.submit("system_check")
        return {"tugas": {"id": task["id"], "nama": task["name"], "status": task["status"]}}

    @add("status_ai", "Status penyedia AI lokal dan model yang aktif.", Permission.READ)
    async def _ai(_: NoArgs) -> dict[str, Any]:
        status = await deps.provider.health()
        return {"penyedia": status.name, "tersedia": status.available, "mock": status.is_mock,
                "model": status.model, "keterangan": status.detail}

    @add("status_aplikasi", "Status ZOI AI CLIPPER dan Blueprint Studio (hanya baca, tidak mengubah apa pun).",
         Permission.READ)
    async def _apps(_: NoArgs) -> dict[str, Any]:
        return {"aplikasi": [a.detect().to_dict() for a in deps.adapters]}

    @add("daftar_tugas", "Tugas terbaru di Task Manager beserta statusnya.", Permission.READ, TaskListArgs)
    async def _tasks(args: TaskListArgs) -> dict[str, Any]:
        return {"tugas": [{k: t[k] for k in ("id", "name", "status", "progress", "message")}
                          for t in deps.tasks.list(limit=args.jumlah)]}

    return registry
