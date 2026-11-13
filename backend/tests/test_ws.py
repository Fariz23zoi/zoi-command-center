from __future__ import annotations

import pytest
from starlette.websockets import WebSocketDisconnect

WS_URL = "ws://127.0.0.1/ws"


def test_ws_hello_and_task_events(client):
    with client.websocket_connect(WS_URL) as ws:
        hello = ws.receive_json()
        assert hello["type"] == "hello" and hello["payload"]["is_mock"] is True
        task = client.post("/api/tasks/system-check").json()
        seen = set()
        for _ in range(200):
            event = ws.receive_json()
            if event["type"] == "task.updated" and event["payload"]["id"] == task["id"]:
                seen.add(event["payload"]["status"])
                if event["payload"]["status"] == "COMPLETED":
                    break
        assert {"RUNNING", "COMPLETED"} <= seen


def test_ws_streams_chat(client):
    with client.websocket_connect(WS_URL) as ws:
        ws.receive_json()
        client.post("/api/chat", json={"message": "halo"})
        deltas, done = [], None
        for _ in range(500):
            event = ws.receive_json()
            if event["type"] == "chat.delta":
                deltas.append(event["payload"]["text"])
            if event["type"] == "chat.done":
                done = event["payload"]["message"]
                break
        assert done and "".join(deltas) == done["content"] and done["is_mock"]


def test_ws_rejects_foreign_origin(client):
    headers = {"origin": "http://jahat.example"}
    with pytest.raises(WebSocketDisconnect), client.websocket_connect(WS_URL, headers=headers) as ws:
        ws.receive_json()


def test_ws_accepts_dev_frontend_origin(client):
    with client.websocket_connect(WS_URL, headers={"origin": "http://127.0.0.1:5173"}) as ws:
        assert ws.receive_json()["type"] == "hello"
