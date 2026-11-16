"""Tugas bawaan Phase 1 — semuanya melakukan pekerjaan NYATA (tidak ada tugas demo)."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from app.core.agent_state import AgentState
from app.db.models import SystemCheck
from app.db.portability import strip_machine_paths
from app.db.session import Database
from app.integrations.base import ExternalAppAdapter
from app.providers.base import LLMProvider
from app.system import detectors
from app.tasks.manager import TaskContext, TaskKind


def system_check_kind(
    *, db: Database, data_dir: Path, provider: LLMProvider, adapters: list[ExternalAppAdapter],
    run_async: Callable[[Any], Any],
) -> TaskKind:
    def run(ctx: TaskContext) -> dict[str, Any]:
        report: dict[str, Any] = {"source": "deteksi langsung di mesin ini"}
        ctx.progress(5, "Memeriksa Python & sistem operasi")
        report["python"] = detectors.python_info()
        report["os"] = detectors.os_info()

        ctx.progress(20, "Memeriksa CPU, RAM, dan disk")
        report["resources"] = detectors.resources(data_dir)

        tools = list(detectors.TOOLS)
        report["tools"] = {}
        for index, name in enumerate(tools):
            ctx.progress(30 + index * 10, f"Mencari {name}")
            report["tools"][name] = detectors.detect_tool(name)

        ctx.progress(75, "Memeriksa penyedia AI")
        report["ai_provider"] = run_async(provider.health()).to_dict()

        ctx.progress(85, "Memeriksa aplikasi terintegrasi (read-only)")
        report["adapters"] = {a.name: a.detect().to_dict() for a in adapters}

        ctx.progress(95, "Menyimpan hasil")
        report["checked_at"] = detectors.now_iso()
        # Yang disimpan tidak boleh berisi path khusus mesin agar database tetap portabel.
        stored = strip_machine_paths(report)
        assert isinstance(stored, dict)
        with db.session() as s:
            s.add(SystemCheck(payload_json=json.dumps(stored, ensure_ascii=False)))
        return stored

    return TaskKind(kind="system_check", name="Pemeriksaan sistem", func=run, agent_state=AgentState.ANALYZING)


def make_run_async(loop: asyncio.AbstractEventLoop) -> Callable[[Any], Any]:
    """Jalankan coroutine di event loop utama dari thread worker."""

    def run_async(coro: Any) -> Any:
        return asyncio.run_coroutine_threadsafe(coro, loop).result(timeout=30)

    return run_async
