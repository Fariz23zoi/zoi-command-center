from __future__ import annotations

import json
import threading

from app.core.agent_state import AgentState
from app.db.models import SystemCheck, Task
from app.tasks.manager import TaskContext, TaskKind, TaskStatus
from tests.conftest import wait_for, wait_task


def test_system_check_runs_for_real(client):
    task = client.post("/api/tasks/system-check").json()
    assert task["status"] in {"QUEUED", "RUNNING"}
    done = wait_task(client, task["id"], {"COMPLETED", "FAILED"})
    assert done["status"] == "COMPLETED", done["error"]
    assert done["progress"] == 100
    result = done["result"]
    assert result["source"] and result["python"]["version"]
    assert result["ai_provider"]["name"] == "mock"
    assert set(result["adapters"]) == {"zoi_ai_clipper", "blueprint_studio"}
    events = done["events"]
    assert events[0]["status"] == "QUEUED" and events[-1]["status"] == "COMPLETED"
    with client.app.state.zoi.db.session() as s:
        stored = s.query(SystemCheck).all()
        assert len(stored) == 1 and json.loads(stored[0].payload_json)["checked_at"]


def test_cancel_running_task(client):
    manager = client.app.state.zoi.tasks
    started, release = threading.Event(), threading.Event()

    def slow(ctx: TaskContext) -> dict:
        ctx.progress(10, "langkah pertama")
        started.set()
        release.wait(5)
        ctx.progress(50, "langkah kedua")
        return {}

    manager.register(TaskKind(kind="uji_lambat", name="Uji lambat", func=slow))
    task = manager.submit("uji_lambat")
    assert started.wait(5)
    assert client.post(f"/api/tasks/{task['id']}/cancel").status_code == 200
    release.set()
    done = wait_task(client, task["id"], {"CANCELLED", "COMPLETED", "FAILED"})
    assert done["status"] == "CANCELLED"


def test_failure_is_reported(client):
    manager = client.app.state.zoi.tasks

    def broken(ctx: TaskContext) -> dict:
        raise ValueError("rusak")

    manager.register(TaskKind(kind="uji_gagal", name="Uji gagal", func=broken))
    task = manager.submit("uji_gagal")
    done = wait_task(client, task["id"], {"FAILED", "COMPLETED"})
    assert done["status"] == "FAILED" and "rusak" in done["error"]


def test_interrupted_tasks_marked_failed_on_restart(client):
    ctx = client.app.state.zoi
    with ctx.db.session() as s:
        s.add(Task(id="t-lama", name="lama", kind="x", status=TaskStatus.RUNNING.value, progress=40, message=""))
    assert ctx.tasks.recover_interrupted() == 1
    task = client.get("/api/tasks/t-lama").json()
    assert task["status"] == "FAILED" and "dihentikan" in task["error"]


def test_agent_state_follows_real_task(client):
    states: list[str] = []
    queue = client.app.state.zoi.bus.subscribe()
    task = client.post("/api/tasks/system-check").json()
    wait_task(client, task["id"], {"COMPLETED"})

    def collect():
        while not queue.empty():
            event = queue.get_nowait()
            if event["type"] == "agent.state":
                states.append(event["payload"]["state"])
        return AgentState.IDLE.value in states

    wait_for(collect, timeout=5)
    assert states[:2] == ["ANALYZING", "COMPLETED"] and states[-1] == "IDLE"


def test_unknown_task_404(client):
    assert client.get("/api/tasks/tidak-ada").status_code == 404
    assert client.post("/api/tasks/tidak-ada/cancel").status_code == 404
