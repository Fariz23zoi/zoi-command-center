"""Server Ollama TIRUAN (httpx.MockTransport) untuk menguji OllamaProvider tanpa Ollama sungguhan."""

from __future__ import annotations

import json

import httpx

from app.providers.mock import TRIGGER_BAD_TOOL, TRIGGER_ERROR, TRIGGER_TIMEOUT, TRIGGER_TOOL

INSTALLED = ["qwen3:4b"]


class FakeOllama:
    def __init__(self, installed: list[str] | None = None) -> None:
        self.installed = installed if installed is not None else INSTALLED
        self.paths: list[str] = []

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handle)

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.paths.append(f"{request.method} {request.url.path}")
        if request.url.path == "/api/version":
            return httpx.Response(200, json={"version": "0.0.0-tiruan"})
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": n} for n in self.installed]})
        if request.url.path == "/api/chat":
            body = json.loads(request.content)
            last = next(m["content"] for m in reversed(body["messages"]) if m["role"] == "user")
            if TRIGGER_ERROR in last:
                return httpx.Response(500, json={"error": "simulasi error"})
            if TRIGGER_TIMEOUT in last:
                raise httpx.ReadTimeout("simulasi timeout", request=request)
            if TRIGGER_BAD_TOOL in last:
                lines = [{"message": {"role": "assistant", "content": "",
                                      "tool_calls": [{"function": {"name": "x", "arguments": "{bukan json"}}]},
                          "done": False}]
            elif TRIGGER_TOOL in last:
                name = body["tools"][0]["function"]["name"] if body.get("tools") else "tanpa_tool"
                lines = [{"message": {"role": "assistant", "content": "",
                                      "tool_calls": [{"function": {"name": name, "arguments": {}}}]},
                          "done": False},
                         {"message": {"role": "assistant", "content": ""}, "done": True}]
            else:
                lines = [{"message": {"role": "assistant", "content": w}, "done": False}
                         for w in ["Jawaban", " dari", " model", " lokal."]]
                lines.append({"message": {"role": "assistant", "content": ""}, "done": True})
            content = "\n".join(json.dumps(line) for line in lines).encode()
            return httpx.Response(200, content=content, headers={"content-type": "application/x-ndjson"})
        return httpx.Response(404, json={"error": f"tidak ada {request.url.path}"})
