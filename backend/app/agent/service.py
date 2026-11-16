"""Layanan agen: rencana → persetujuan → eksekusi (tugas Task Manager) → izin per langkah → ringkasan.

Aturan:
- Rencana selalu ditampilkan dan harus disetujui pengguna sebelum dijalankan (keputusan K-2).
- Langkah `read` berjalan otomatis setelah rencana disetujui; `write_local` minta izin per langkah kecuali
  pengguna mengizinkan tool itu secara otomatis; `external` SELALU minta izin.
- Langkah gagal / izin ditolak / izin kedaluwarsa menghentikan sisa langkah — dilaporkan apa adanya.
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from collections.abc import Callable
from typing import Any, Literal

from sqlalchemy import select

from app.agent.evaluator import summarize
from app.agent.mock_plans import mock_plan
from app.agent.planner import Rencana, check_plan, make_plan
from app.agent.tools import Permission, ToolError, ToolRegistry
from app.chat.service import ChatService
from app.core.agent_state import AgentState, AgentStateTracker
from app.core.errors import NotFound, ZoiError
from app.core.events import EventBus
from app.db.base import utcnow
from app.db.models import AgentRun, AppMeta, Approval
from app.db.session import Database
from app.logging_setup import get_logger
from app.memory.service import MemoryService
from app.providers.base import LLMProvider
from app.tasks.manager import TaskCancelled, TaskContext, TaskKind, TaskManager

log = get_logger("agent")

KIND = "agent_run"
PERMISSIONS_KEY = "agent_tool_permissions"
MAX_REQUEST_CHARS = 2000
APPROVAL_TIMEOUT_S = 600.0
STEP_TIMEOUT_S = 120.0
OUTPUT_LIMIT = 4000
ACTIVE = {"planning", "planned", "running", "waiting_approval"}
Decision = Literal["approve", "reject"]


def _dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


class AgentService:
    def __init__(self, *, db: Database, bus: EventBus, agent: AgentStateTracker, provider: LLMProvider,
                 registry: ToolRegistry, memory: MemoryService, tasks: TaskManager, chat: ChatService,
                 approval_timeout_s: float = APPROVAL_TIMEOUT_S) -> None:
        self.db = db
        self.bus = bus
        self.agent = agent
        self.provider = provider
        self.registry = registry
        self.memory = memory
        self.tasks = tasks
        self.chat = chat
        self.approval_timeout_s = approval_timeout_s
        self._background: set[asyncio.Task[None]] = set()

    # ── ketersediaan ──────────────────────────────────────────────────────
    async def availability(self) -> tuple[bool, str]:
        if self.provider.name == "none":
            return False, "AI dinonaktifkan (ZOI_AI_PROVIDER=none) — agen membutuhkan AI untuk menyusun rencana."
        status = await self.provider.health()
        if not status.available:
            return False, f"Agen tidak tersedia: {status.detail}"
        return True, "Agen siap." + (" (Mode development: rencana MOCK dari kata kunci.)" if status.is_mock else "")

    # ── rencana ───────────────────────────────────────────────────────────
    async def request_plan(self, request: str, conversation_id: str | None) -> dict[str, Any]:
        request = " ".join(request.split())
        if not request:
            raise ZoiError("Permintaan kosong.", code="empty_request")
        if len(request) > MAX_REQUEST_CHARS:
            raise ZoiError(f"Permintaan terlalu panjang (maks. {MAX_REQUEST_CHARS} karakter).", code="too_long")
        available, detail = await self.availability()
        if not available:
            raise ZoiError(detail, status_code=409, code="agent_unavailable")
        with self.db.session() as s:
            busy = s.scalar(select(AgentRun.id).where(AgentRun.status.in_(["planning", "running",
                                                                            "waiting_approval"])).limit(1))
        if busy:
            raise ZoiError("Agen sedang mengerjakan permintaan lain. Tunggu selesai atau batalkan.", status_code=409,
                           code="agent_busy")
        run_id = str(uuid.uuid4())
        message = self.chat.add_message(conversation_id=conversation_id, role="user", content=request,
                                        agent_run_id=run_id)
        with self.db.session() as s:
            s.add(AgentRun(id=run_id, conversation_id=message["conversation_id"], request=request, status="planning",
                           provider=self.provider.name, is_mock=self.provider.is_mock))
        self._publish(run_id)
        task = asyncio.create_task(self._plan(run_id))
        self._background.add(task)
        task.add_done_callback(self._background.discard)
        return {"run": self.get(run_id), "user_message": message}

    async def _plan(self, run_id: str) -> None:
        self.agent.set(AgentState.PLANNING, "Menyusun rencana")
        run = self.get(run_id)
        try:
            if self.provider.is_mock:
                plan: Rencana | None = mock_plan(run["request"])
                errors = check_plan(plan, self.registry)
            else:
                plan, errors = await make_plan(self.provider, self.registry, run["request"],
                                               self.memory.prompt_block(run["request"]))
        except Exception as exc:  # noqa: BLE001 — dilaporkan, tidak disembunyikan
            log.exception("agent_plan_failed", run_id=run_id)
            plan, errors = None, [f"Kesalahan internal saat menyusun rencana: {type(exc).__name__}"]
        status = "invalid" if errors or plan is None else "planned"
        self._update(run_id, status=status, plan_json=plan.model_dump_json() if plan else None,
                     errors_json=_dumps(errors))
        if status == "planned":
            self.agent.set(AgentState.WAITING_APPROVAL, "Menunggu persetujuan rencana")
        else:
            self.agent.set(AgentState.FAILED, "Rencana tidak valid")

    def approve(self, run_id: str) -> dict[str, Any]:
        run = self._require(run_id, {"planned"})
        # Status diubah SEBELUM tugas dikirim: tugas bisa langsung maju ke "waiting_approval", dan status itu
        # tidak boleh tertimpa "running" dari sini.
        self._update(run_id, status="running")
        task = self.tasks.submit(KIND, {"run_id": run_id}, name=f"Agen: {run['plan']['tujuan'][:100]}")
        self._update(run_id, task_id=task["id"])
        return self.get(run_id)

    def reject(self, run_id: str) -> dict[str, Any]:
        self._require(run_id, {"planned", "invalid"})
        self._update(run_id, status="rejected")
        self.agent.set(AgentState.IDLE, "Rencana dibatalkan")
        return self.get(run_id)

    def cancel(self, run_id: str) -> dict[str, Any]:
        run = self._require(run_id, {"running", "waiting_approval"})
        if run["task_id"]:
            try:
                self.tasks.cancel(run["task_id"])
            except (KeyError, ZoiError):
                pass
        return self.get(run_id)

    # ── izin ──────────────────────────────────────────────────────────────
    def decide(self, approval_id: str, decision: Decision) -> dict[str, Any]:
        with self.db.session() as s:
            approval = s.get(Approval, approval_id)
            if approval is None:
                raise NotFound("Permintaan izin tidak ditemukan.")
            if approval.status != "pending":
                raise ZoiError(f"Permintaan izin ini sudah {approval.status}.", code="already_decided")
            approval.status = "approved" if decision == "approve" else "rejected"
            approval.decided_at = utcnow()
            run_id = approval.run_id
        self._publish(run_id)
        return self.get(run_id)

    def tool_permissions(self) -> dict[str, str]:
        with self.db.session() as s:
            row = s.get(AppMeta, PERMISSIONS_KEY)
            return json.loads(row.value_json) if row else {}

    def set_tool_permission(self, name: str, mode: Literal["ask", "auto"]) -> list[dict[str, Any]]:
        tool = self.registry.get(name)
        if tool is None:
            raise NotFound(f"Tool '{name}' tidak ada.")
        if tool.permission is not Permission.WRITE_LOCAL:
            raise ZoiError("Hanya tool yang mengubah data lokal yang bisa diizinkan otomatis.", code="not_allowed")
        current = self.tool_permissions()
        current[name] = mode
        with self.db.session() as s:
            row = s.get(AppMeta, PERMISSIONS_KEY)
            if row is None:
                s.add(AppMeta(key=PERMISSIONS_KEY, value_json=_dumps(current)))
            else:
                row.value_json = _dumps(current)
        return self.tools()

    def tools(self) -> list[dict[str, Any]]:
        modes = self.tool_permissions()
        result = []
        for tool in self.registry.all():
            mode = "auto" if tool.permission is Permission.READ else (
                modes.get(tool.name, "ask") if tool.permission is Permission.WRITE_LOCAL else "ask")
            result.append({**tool.spec(), "mode": mode})
        return result

    def approvals_log(self, limit: int = 100) -> list[dict[str, Any]]:
        with self.db.session() as s:
            rows = s.scalars(select(Approval).order_by(Approval.created_at.desc()).limit(limit)).all()
            return [_approval_dict(a) for a in rows]

    # ── baca ──────────────────────────────────────────────────────────────
    def get(self, run_id: str) -> dict[str, Any]:
        with self.db.session() as s:
            run = s.get(AgentRun, run_id)
            if run is None:
                raise NotFound("Permintaan agen tidak ditemukan.")
            approvals = s.scalars(select(Approval).where(Approval.run_id == run_id)
                                  .order_by(Approval.created_at)).all()
            return _run_dict(run, approvals, self.registry)

    def list(self, conversation_id: str | None = None, limit: int = 30) -> list[dict[str, Any]]:
        with self.db.session() as s:
            query = select(AgentRun.id).order_by(AgentRun.created_at.desc()).limit(limit)
            if conversation_id:
                query = query.where(AgentRun.conversation_id == conversation_id)
            ids = list(s.scalars(query))
        return [self.get(i) for i in ids]

    def recover(self) -> int:
        """Setelah restart: permintaan yang terputus ditandai jujur, bukan dilanjutkan diam-diam."""
        with self.db.session() as s:
            rows = s.scalars(select(AgentRun).where(AgentRun.status.in_(list(ACTIVE)))).all()
            for run in rows:
                run.status = "failed" if run.status in {"running", "waiting_approval"} else "invalid"
                run.errors_json = _dumps(["Terputus karena ZOI dimulai ulang."])
                run.updated_at = utcnow()
            for approval in s.scalars(select(Approval).where(Approval.status == "pending")):
                approval.status = "expired"
                approval.decided_at = utcnow()
            return len(rows)

    # ── eksekusi (berjalan di thread Task Manager) ────────────────────────
    def task_kind(self, run_async: Callable[..., Any]) -> TaskKind:
        def execute(ctx: TaskContext) -> dict[str, Any]:
            run_id = ctx.params["run_id"]
            try:
                return self._execute(ctx, run_id, run_async)
            except TaskCancelled:
                raise
            except Exception as exc:
                # Kesalahan tak terduga: permintaan ditutup jujur, bukan dibiarkan "berjalan" selamanya.
                log.exception("agent_run_failed", run_id=run_id)
                self._expire_pending(run_id)
                self._finish(run_id, "failed", self.get(run_id)["results"],
                             f"Agen berhenti karena kesalahan internal ({type(exc).__name__}).", [])
                self.agent.set(AgentState.FAILED, "Agen gagal")
                raise

        return TaskKind(kind=KIND, name="Agen", func=execute, lane="agent")

    def _execute(self, ctx: TaskContext, run_id: str, run_async: Callable[..., Any]) -> dict[str, Any]:
        run = self.get(run_id)
        with self.db.session() as s:
            stored = s.get(AgentRun, run_id)
            assert stored is not None and stored.plan_json
            plan = Rencana.model_validate_json(stored.plan_json)  # rencana asli, bukan versi tampilan
        modes = self.tool_permissions()
        results: list[dict[str, Any]] = []
        final = "completed"
        total = len(plan.langkah)
        try:
            for index, step in enumerate(plan.langkah):
                ctx.check_cancelled()
                ctx.progress(int(index / total * 100), f"Langkah {index + 1}/{total}: {step.tool}")
                tool = self.registry.get(step.tool)
                problem = self.registry.check_step(step.tool, step.argumen)
                if tool is None or problem:  # registry bisa berubah sejak rencana dibuat
                    results.append(_result(index, step, "error", error=problem or "tool tidak ada"))
                    final = "failed"
                    break
                needs_approval = tool.permission is Permission.EXTERNAL or (
                    tool.permission is Permission.WRITE_LOCAL and modes.get(tool.name, "ask") != "auto")
                if tool.permission is Permission.WRITE_LOCAL and not needs_approval:
                    self._record_auto(run_id, index, step.tool, step.argumen)
                if needs_approval:
                    decision = self._wait_for_approval(ctx, run_id, index, step.tool, step.argumen)
                    if decision != "approved":
                        label = "ditolak" if decision == "rejected" else "kedaluwarsa"
                        results.append(_result(index, step, "rejected",
                                               error=f"Izin {label} — langkah tidak dijalankan."))
                        final = "stopped"
                        break
                self._update(run_id, status="running", results_json=_dumps(results))
                self.agent.set(AgentState.EXECUTING, f"Langkah {index + 1}/{total}: {step.tool}")
                try:
                    output = run_async(tool.run(tool.validate(step.argumen)), timeout=STEP_TIMEOUT_S)
                except ToolError as exc:
                    results.append(_result(index, step, "error", error=str(exc)))
                    final = "failed"
                    break
                except TimeoutError:
                    results.append(_result(index, step, "error", error=f"Melebihi batas {STEP_TIMEOUT_S:.0f} dtk."))
                    final = "failed"
                    break
                results.append(_result(index, step, "ok", output=output))
                self._update(run_id, results_json=_dumps(results))
        except TaskCancelled:
            self._expire_pending(run_id)
            self._finish(run_id, "cancelled", results,
                         "Dibatalkan (oleh pengguna, atau karena ZOI dihentikan) — sisa langkah tidak dijalankan.", [])
            self.agent.set(AgentState.IDLE, "Permintaan agen dibatalkan")
            raise
        ctx.progress(100, "Menyusun ringkasan")
        self.agent.set(AgentState.THINKING, "Menyusun ringkasan hasil")
        summary, warnings = run_async(summarize(self.provider, run["request"], results), timeout=STEP_TIMEOUT_S * 3)
        self._finish(run_id, final, results, summary, warnings)
        self.agent.set(AgentState.COMPLETED if final == "completed" else AgentState.FAILED,
                       {"completed": "Permintaan agen selesai", "failed": "Langkah agen gagal",
                        "stopped": "Agen dihentikan: izin tidak diberikan"}[final])
        return {"run_id": run_id, "status": final, "steps": len(results)}

    def _wait_for_approval(self, ctx: TaskContext, run_id: str, index: int, tool: str,
                           args: dict[str, Any]) -> str:
        approval_id = str(uuid.uuid4())
        with self.db.session() as s:
            s.add(Approval(id=approval_id, run_id=run_id, step_index=index, tool=tool, args_json=_dumps(args),
                           status="pending", is_mock=self.provider.is_mock))
        self._update(run_id, status="waiting_approval")
        self.agent.set(AgentState.WAITING_APPROVAL, f"Menunggu izin: {tool}")
        deadline = time.monotonic() + self.approval_timeout_s
        while True:
            ctx.check_cancelled()
            with self.db.session() as s:
                status = s.get(Approval, approval_id).status  # type: ignore[union-attr]
            if status != "pending":
                return status
            if time.monotonic() > deadline:
                with self.db.session() as s:
                    approval = s.get(Approval, approval_id)
                    assert approval is not None
                    approval.status = "expired"
                    approval.decided_at = utcnow()
                self._publish(run_id)
                return "expired"
            time.sleep(0.1)

    def _record_auto(self, run_id: str, index: int, tool: str, args: dict[str, Any]) -> None:
        with self.db.session() as s:
            s.add(Approval(id=str(uuid.uuid4()), run_id=run_id, step_index=index, tool=tool, args_json=_dumps(args),
                           status="auto", is_mock=self.provider.is_mock, decided_at=utcnow()))

    def _expire_pending(self, run_id: str) -> None:
        with self.db.session() as s:
            for approval in s.scalars(select(Approval).where(Approval.run_id == run_id,
                                                             Approval.status == "pending")):
                approval.status = "expired"
                approval.decided_at = utcnow()

    def _finish(self, run_id: str, status: str, results: list[dict[str, Any]], summary: str,
                warnings: list[str]) -> None:
        self._update(run_id, status=status, results_json=_dumps(results), summary=summary,
                     warnings_json=_dumps(warnings))
        run = self.get(run_id)
        text = summary + ("\n" + "\n".join(warnings) if warnings else "")
        try:
            self.chat.add_message(conversation_id=run["conversation_id"], role="assistant", content=text,
                                  agent_run_id=run_id)
        except (NotFound, ZoiError):
            log.warning("agent_summary_not_posted", run_id=run_id)

    # ── penyimpanan ───────────────────────────────────────────────────────
    def _update(self, run_id: str, **fields: Any) -> None:
        with self.db.session() as s:
            run = s.get(AgentRun, run_id)
            assert run is not None
            for key, value in fields.items():
                setattr(run, key, value)
            run.updated_at = utcnow()
        self._publish(run_id)

    def _publish(self, run_id: str) -> None:
        self.bus.publish("agent.run.updated", {"run": self.get(run_id)})

    def _require(self, run_id: str, allowed: set[str]) -> dict[str, Any]:
        run = self.get(run_id)
        if run["status"] not in allowed:
            raise ZoiError(f"Permintaan agen berstatus '{run['status']}' — tindakan ini tidak bisa dilakukan.",
                           status_code=409, code="bad_state")
        return run


def _result(index: int, step: Any, status: str, *, output: Any = None, error: str | None = None) -> dict[str, Any]:
    text = _dumps(output) if output is not None else None
    if text and len(text) > OUTPUT_LIMIT:
        output = {"dipotong": True, "awal": text[:OUTPUT_LIMIT]}
    return {"index": index, "tool": step.tool, "args": step.argumen, "status": status, "output": output,
            "error": error}


def _approval_dict(a: Approval) -> dict[str, Any]:
    return {"id": a.id, "run_id": a.run_id, "step_index": a.step_index, "tool": a.tool,
            "args": json.loads(a.args_json), "status": a.status, "is_mock": a.is_mock,
            "created_at": a.created_at.isoformat(), "decided_at": a.decided_at.isoformat() if a.decided_at else None}


def _run_dict(run: AgentRun, approvals: list[Approval], registry: ToolRegistry) -> dict[str, Any]:
    plan = json.loads(run.plan_json) if run.plan_json else None
    if plan:
        for step in plan["langkah"]:
            tool = registry.get(step["tool"])
            step["permission"] = tool.permission.value if tool else None
    return {
        "id": run.id, "conversation_id": run.conversation_id, "request": run.request, "status": run.status,
        "plan": plan, "errors": json.loads(run.errors_json), "results": json.loads(run.results_json),
        "summary": run.summary, "warnings": json.loads(run.warnings_json), "task_id": run.task_id,
        "provider": run.provider, "is_mock": run.is_mock, "created_at": run.created_at.isoformat(),
        "updated_at": run.updated_at.isoformat(), "approvals": [_approval_dict(a) for a in approvals],
    }
