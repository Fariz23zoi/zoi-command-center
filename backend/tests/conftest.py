from __future__ import annotations

import time
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.config.settings import Settings
from app.main import create_app

HEADERS = {"X-ZOI-Client": "web"}


def make_settings(tmp_path: Path, **overrides: Any) -> Settings:
    values: dict[str, Any] = {"data_dir": str(tmp_path / "data"), "mock_latency_ms": 0, "update_check": False}
    values.update(overrides)
    return Settings.model_validate(values)


@pytest.fixture
def settings_factory(tmp_path: Path) -> Callable[..., Settings]:
    return lambda **kw: make_settings(tmp_path, **kw)


@pytest.fixture
def client_factory(tmp_path: Path) -> Iterator[Callable[..., TestClient]]:
    clients: list[TestClient] = []

    def factory(**overrides: Any) -> TestClient:
        app = create_app(make_settings(tmp_path, **overrides), return_to_idle_s=0.05)
        client = TestClient(app, base_url="http://127.0.0.1", headers=HEADERS)
        client.__enter__()
        clients.append(client)
        return client

    yield factory
    for client in clients:
        client.__exit__(None, None, None)


@pytest.fixture
def client(client_factory: Callable[..., TestClient]) -> TestClient:
    return client_factory()


def wait_for(predicate: Callable[[], Any], timeout: float = 10.0, interval: float = 0.02) -> Any:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(interval)
    raise AssertionError("Kondisi tidak terpenuhi dalam batas waktu")


def wait_chat_done(client: TestClient, conversation_id: str) -> list[dict]:
    def done() -> list[dict] | None:
        msgs = client.get(f"/api/conversations/{conversation_id}/messages").json()["messages"]
        return msgs if msgs and msgs[-1]["status"] != "streaming" else None

    return wait_for(done)


def wait_task(client: TestClient, task_id: str, statuses: set[str]) -> dict:
    return wait_for(lambda: (t := client.get(f"/api/tasks/{task_id}").json())["status"] in statuses and t)
