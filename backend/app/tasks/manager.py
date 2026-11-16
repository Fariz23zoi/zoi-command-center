"""Task Manager: antrian tugas latar belakang dengan progress, pembatalan, dan riwayat di SQLite.

Pembatalan bersifat kooperatif: fungsi tugas memanggil ctx.progress()/ctx.check_cancelled() di antara
langkah, dan berhenti dengan TaskCancelled. Tidak ada thread yang dibunuh paksa.
"""

from __future__ import annotations

import json
import threading
import uuid
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from sqlalchemy import select

from app.core.agent_state import AgentState, AgentStateTracker
from app.core.events import EventBus
from app.db.base import utcnow
from app.db.models import Task, TaskEvent
from app.db.session import Database
from app.logging_setup import get_logger

log = get_logger("tasks")


class TaskStatus(StrEnum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


ACTIVE = {TaskStatus.QUEUED, TaskStatus.RUNNING}


class TaskCancelled(Exception):
    pass


@dataclass(frozen=True)
class TaskKind:
    kind: str
    name: str
    func: Callable[[TaskContext], dict[str, Any]]
    agent_state: AgentState = AgentState.EXECUTING


class TaskContext:
    def __init__(self, manager: TaskManager, task_id: str) -> None:
        self._manager = manager
        self.task_id = task_id
        self.cancel_event = threading.Event()

    def check_cancelled(self) -> None:
        if self.cancel_event.is_set():
            raise TaskCancelled

    def progress(self, percent: int, message: str) -> None:
        self.check_cancelled()
        self._manager._update(self.task_id, TaskStatus.RUNNING, max(0, min(99, int(percent))), message)


class TaskManager:
    def __init__(self, db: Database, bus: EventBus, agent: AgentStateTracker, max_workers: int = 1) -> None:
        self.db = db
        self.bus = bus
        self.agent = agent
        self._kinds: dict[str, TaskKind] = {}
        self._contexts: dict[str, TaskContext] = {}
        self._lock = threading.Lock()
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="zoi-task")

    def register(self, kind: TaskKind) -> None:
        self._kinds[kind.kind] = kind

    @property
    def kinds(self) -> dict[str, TaskKind]:
        return dict(self._kinds)

    def recover_interrupted(self) -> int:
        """Tugas yang masih QUEUED/RUNNING dari sesi sebelumnya ditandai gagal — jujur, bukan dilanjutkan diam-diam."""
        with self.db.session() as s:
            stale = s.scalars(select(Task).where(Task.status.in_([t.value for t in ACTIVE]))).all()
            for task in stale:
                task.status = TaskStatus.FAILED.value
                task.error = "Aplikasi dihentikan saat tugas ini berjalan."
                task.finished_at = utcnow()
                s.add(TaskEvent(task_id=task.id, status=task.status, progress=task.progress, message=task.error))
            return len(stale)

    def submit(self, kind: str) -> dict[str, Any]:
        spec = self._kinds.get(kind)
        if spec is None:
            raise KeyError(kind)
        task_id = str(uuid.uuid4())
        with self.db.session() as s:
            s.add(Task(id=task_id, name=spec.name, kind=kind, status=TaskStatus.QUEUED.value, progress=0,
                       message="Menunggu giliran"))
            s.add(TaskEvent(task_id=task_id, status=TaskStatus.QUEUED.value, progress=0, message="Menunggu giliran"))
        ctx = TaskContext(self, task_id)
        with self._lock:
            self._contexts[task_id] = ctx
        self._publish(task_id)
        self._executor.submit(self._run, spec, ctx)
        return self.get(task_id)

    def cancel(self, task_id: str) -> dict[str, Any]:
        with self._lock:
            ctx = self._contexts.get(task_id)
        task = self.get(task_id)
        if task["status"] not in {s.value for s in ACTIVE}:
            return task
        if ctx is not None:
            ctx.cancel_event.set()
        if task["status"] == TaskStatus.QUEUED.value:
            self._finish(task_id, TaskStatus.CANCELLED, "Dibatalkan sebelum mulai")
        return self.get(task_id)

    def get(self, task_id: str, with_events: bool = False) -> dict[str, Any]:
        with self.db.session() as s:
            task = s.get(Task, task_id)
            if task is None:
                raise KeyError(task_id)
            return _task_dict(task, with_events)

    def list(self, limit: int = 50) -> list[dict[str, Any]]:
        with self.db.session() as s:
            rows = s.scalars(select(Task).order_by(Task.created_at.desc()).limit(limit)).all()
            return [_task_dict(t, False) for t in rows]

    def shutdown(self) -> None:
        with self._lock:
            for ctx in self._contexts.values():
                ctx.cancel_event.set()
        self._executor.shutdown(wait=True, cancel_futures=True)

    # --- internal ---------------------------------------------------------------------------------------
    def _run(self, spec: TaskKind, ctx: TaskContext) -> None:
        if ctx.cancel_event.is_set():
            return
        with self.db.session() as s:
            task = s.get(Task, ctx.task_id)
            assert task is not None
            if task.status != TaskStatus.QUEUED.value:
                return
            task.started_at = utcnow()
        self._update(ctx.task_id, TaskStatus.RUNNING, 0, "Dimulai")
        self.agent.set(spec.agent_state, f"Menjalankan: {spec.name}")
        try:
            result = spec.func(ctx)
            ctx.check_cancelled()
        except TaskCancelled:
            self._finish(ctx.task_id, TaskStatus.CANCELLED, "Dibatalkan pengguna")
            self.agent.set(AgentState.IDLE, "Tugas dibatalkan")
        except Exception as exc:  # noqa: BLE001 — semua kegagalan dilaporkan, tidak disembunyikan
            log.exception("task_failed", task_id=ctx.task_id, kind=spec.kind)
            self._finish(ctx.task_id, TaskStatus.FAILED, "Gagal", error=f"{type(exc).__name__}: {exc}")
            self.agent.set(AgentState.FAILED, f"Gagal: {spec.name}")
        else:
            self._finish(ctx.task_id, TaskStatus.COMPLETED, "Selesai", result=result)
            self.agent.set(AgentState.COMPLETED, f"Selesai: {spec.name}")
        finally:
            with self._lock:
                self._contexts.pop(ctx.task_id, None)

    def _update(self, task_id: str, status: TaskStatus, progress: int, message: str) -> None:
        with self.db.session() as s:
            task = s.get(Task, task_id)
            assert task is not None
            task.status, task.progress, task.message = status.value, progress, message
            s.add(TaskEvent(task_id=task_id, status=status.value, progress=progress, message=message))
        self._publish(task_id)

    def _finish(self, task_id: str, status: TaskStatus, message: str, *, result: dict[str, Any] | None = None,
                error: str | None = None) -> None:
        with self.db.session() as s:
            task = s.get(Task, task_id)
            assert task is not None
            task.status, task.message, task.finished_at = status.value, message, utcnow()
            if status is TaskStatus.COMPLETED:
                task.progress = 100
            if result is not None:
                task.result_json = json.dumps(result, ensure_ascii=False, default=str)
            task.error = error
            s.add(TaskEvent(task_id=task_id, status=status.value, progress=task.progress, message=error or message))
        self._publish(task_id)

    def _publish(self, task_id: str) -> None:
        self.bus.publish("task.updated", self.get(task_id))


def _task_dict(task: Task, with_events: bool) -> dict[str, Any]:
    data: dict[str, Any] = {
        "id": task.id, "name": task.name, "kind": task.kind, "status": task.status, "progress": task.progress,
        "message": task.message,
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "started_at": task.started_at.isoformat() if task.started_at else None,
        "finished_at": task.finished_at.isoformat() if task.finished_at else None,
        "result": json.loads(task.result_json) if task.result_json else None,
        "error": task.error,
    }
    if with_events:
        data["events"] = [{"at": e.at.isoformat(), "status": e.status, "progress": e.progress, "message": e.message}
                          for e in task.events]
    return data
