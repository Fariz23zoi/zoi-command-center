"""Server AI cloud TIRUAN (bentuk OpenAI: NVIDIA NIM di /nvidia/v1, OpenRouter di /openrouter/api/v1) — untuk tes.

Jawabannya karangan dan selalu diawali "[uji <penyedia>]"; tidak pernah berasal dari NVIDIA/OpenRouter.
"""

from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from tests.fake_ollama import _example

NV_KEY = "nvapi-" + "u" * 30
OR_KEY = "sk-or-v1-" + "u" * 30
NV_MODEL = "meta/llama-uji"
OR_MODEL = "uji/model:free"
MODELS = {"nvidia": [NV_MODEL, "nvidia/tidak-bisa-dipanggil"], "openrouter": [OR_MODEL, "uji/berbayar"]}
KEYS = {"nvidia": NV_KEY, "openrouter": OR_KEY}
PREFIX = {"/nvidia/v1": "nvidia", "/openrouter/api/v1": "openrouter"}
SCHEMA_MARK = "skema JSON ini:\n"


class FakeCloud:
    def __init__(self) -> None:
        self.requests: list[dict[str, Any]] = []
        self.status: dict[str, int] = {}        # mis. {"nvidia": 429} → chat selalu gagal dengan status itu
        self.hang_s: dict[str, float] = {}      # jeda sebelum menjawab
        self.cut: set[str] = set()              # putus di tengah aliran (setelah satu potongan teks)
        self.garbage: set[str] = set()          # kirim data yang bukan JSON
        self.server: ThreadingHTTPServer | None = None
        self.url = ""

    def chats(self, name: str) -> list[dict[str, Any]]:
        return [r for r in self.requests if r["provider"] == name and r["path"].endswith("/chat/completions")]

    def _events(self, name: str, body: dict[str, Any]) -> list[dict[str, Any]]:
        messages = body.get("messages") or []
        last_user = next((m["content"] for m in reversed(messages) if m.get("role") == "user"), "")
        schema = next((m["content"].split(SCHEMA_MARK, 1)[1] for m in messages
                       if m.get("role") == "system" and SCHEMA_MARK in m.get("content", "")), None)

        def delta(**fields: Any) -> dict[str, Any]:
            return {"choices": [{"index": 0, "delta": fields}]}

        events: list[dict[str, Any]] = []
        if "/pikir" in last_user:
            events.append(delta(reasoning_content="menimbang jawaban"))
        if body.get("tools") and "/tool" in last_user:
            tool = body["tools"][0]["function"]["name"]
            events += [delta(tool_calls=[{"index": 0, "function": {"name": tool, "arguments": '{"kata'}}]),
                       delta(tool_calls=[{"index": 0, "function": {"arguments": '": "kopi"}'}}])]
        elif schema is not None:
            text = json.dumps(_example(json.loads(schema)), ensure_ascii=False)
            events += [delta(content="```json\n"), delta(content=text), delta(content="\n```")]
        else:
            events += [delta(content=f"[uji {name}] "), delta(content="jawaban untuk: "), delta(content=last_user)]
        events.append({"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                       "usage": {"prompt_tokens": 12, "completion_tokens": 7}})
        return events

    def start(self, port: int = 0) -> str:
        fake = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.0"

            def log_message(self, *_: Any) -> None:
                return

            def _json(self, status: int, body: Any) -> None:
                data = json.dumps(body).encode()
                self.send_response(status)
                self.send_header("content-type", "application/json")
                self.send_header("content-length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def _handle(self) -> None:
                if self.path == "/healthz":
                    return self._json(200, {"fake": True})
                name = next((n for p, n in PREFIX.items() if self.path.startswith(p + "/")), None)
                length = int(self.headers.get("content-length") or 0)
                body = json.loads(self.rfile.read(length) or b"{}") if length else {}
                authorized = self.headers.get("authorization") == f"Bearer {KEYS.get(name or '', '')}"
                fake.requests.append({"provider": name, "method": self.command, "path": self.path,
                                      "authorized": authorized, "body": body})
                if name is None:
                    return self._json(404, {"error": {"message": "not found"}})
                if not authorized:
                    return self._json(401, {"error": {"message": "invalid api key"}})
                if self.command == "GET" and self.path.endswith("/models"):
                    return self._json(200, {"data": [{"id": m} for m in MODELS[name]]})
                if self.command != "POST" or not self.path.endswith("/chat/completions"):
                    return self._json(404, {"error": {"message": "not found"}})
                if fake.hang_s.get(name):
                    time.sleep(fake.hang_s[name])
                if name in fake.status:
                    return self._json(fake.status[name], {"error": {"message": f"galat uji {fake.status[name]}"}})
                if body.get("model") not in MODELS[name]:
                    return self._json(404, {"status": 404, "title": "Not Found", "detail": "Function not found"})
                if body.get("model") == "nvidia/tidak-bisa-dipanggil":
                    return self._json(410, {"error": {"message": "Gone"}})
                self.send_response(200)
                self.send_header("content-type", "text/event-stream")
                self.end_headers()
                if name in fake.garbage:
                    self.wfile.write(b"data: {bukan json\n\n")
                    return None
                for index, event in enumerate(fake._events(name, body)):
                    self.wfile.write(f"data: {json.dumps(event)}\n\n".encode())
                    self.wfile.flush()
                    if name in fake.cut and index == 0:
                        self.connection.shutdown(2)
                        return None
                self.wfile.write(b"data: [DONE]\n\n")
                return None

            do_GET = do_POST = _handle  # noqa: N815

        self.server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        return self.url

    def stop(self) -> None:
        if self.server is not None:
            self.server.shutdown()
            self.server.server_close()
            self.server = None
