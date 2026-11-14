"""Server Ollama TIRUAN — hanya untuk tes. Meniru bentuk respons API Ollama, bukan kemampuan model.

Dua cara pakai:
- `FakeOllama().transport()` → httpx.MockTransport untuk pytest.
- `python -m tests.fake_ollama --port 11500` → server HTTP sungguhan untuk E2E Playwright (mode local).

Angka di sini (ukuran, token) adalah data uji yang jelas tiruan; tidak pernah dipakai di luar tes.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import threading
import time
from collections.abc import AsyncIterator, Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

import httpx

from app.providers.mock import TRIGGER_BAD_TOOL, TRIGGER_ERROR, TRIGGER_TIMEOUT, TRIGGER_TOOL

TRIGGER_SLOW = "/uji-lambat"
TRIGGER_THINK_TAG = "/uji-tag-think"
INSTALLED = ["qwen3:4b"]

# Model tiruan yang dikenal server ini.
KNOWN: dict[str, dict[str, Any]] = {
    "qwen3:4b": {"family": "qwen3", "parameter_size": "4.0B", "quantization_level": "Q4_K_M", "size": 2_500_000_000,
                 "capabilities": ["completion", "tools", "thinking"], "context": 40960},
    "uji-kecil:1b": {"family": "llama", "parameter_size": "1.0B", "quantization_level": "Q4_K_M",
                     "size": 800_000_000, "capabilities": ["completion"], "context": 8192},
    "uji-embed:latest": {"family": "bert", "parameter_size": "137M", "quantization_level": "F16",
                         "size": 270_000_000, "capabilities": ["embedding"], "context": 2048},
    "uji-awan:cloud": {"family": "cloud", "parameter_size": "?", "quantization_level": "?", "size": 400,
                       "capabilities": ["completion"], "context": 8192, "remote_host": "https://ollama.com:443"},
}
WORDS = ["Jawaban", " dari", " model", " lokal."]


class Paced:
    """Baris NDJSON dengan jeda. Sinkron untuk server HTTP (thread), asinkron untuk MockTransport."""

    def __init__(self, lines: list[dict[str, Any]], delay: float) -> None:
        self.lines, self.delay = lines, delay

    def __iter__(self) -> Iterator[dict[str, Any]]:
        for line in self.lines:
            if self.delay:
                time.sleep(self.delay)
            yield line

    async def aiter_bytes(self) -> AsyncIterator[bytes]:
        for line in self.lines:
            if self.delay:
                await asyncio.sleep(self.delay)
            yield (json.dumps(line) + "\n").encode()


class FakeOllama:
    def __init__(self, installed: list[str] | None = None) -> None:
        self.installed = list(installed if installed is not None else INSTALLED)
        self.running: dict[str, int] = {}
        self.paths: list[str] = []
        self.bodies: list[dict[str, Any]] = []
        self.word_delay_s = 0.0

    # ── inti: (status, json | iterator ndjson) ────────────────────────────
    def respond(self, method: str, path: str, body: dict[str, Any]) -> tuple[int, Any]:
        self.paths.append(f"{method} {path}")
        if body:
            self.bodies.append({"path": path, **body})
        if path == "/api/version":
            return 200, {"version": "0.0.0-tiruan"}
        if path == "/api/tags":
            return 200, {"models": [self._tag(n) for n in self.installed]}
        if path == "/api/ps":
            return 200, {"models": [{"name": n, "model": n, "size": KNOWN.get(n, {}).get("size", 1),
                                     "size_vram": 0, "context_length": ctx, "expires_at": "2026-11-14T10:00:00Z"}
                                    for n, ctx in self.running.items()]}
        if path == "/api/show":
            name = body.get("model", "")
            if name not in self.installed:
                return 404, {"error": f"model '{name}' not found"}
            info = KNOWN.get(name, KNOWN["qwen3:4b"])
            arch = info["family"]
            return 200, {"license": "Apache License\nVersion 2.0", "capabilities": info["capabilities"],
                         "details": {"family": arch, "parameter_size": info["parameter_size"],
                                     "quantization_level": info["quantization_level"]},
                         "model_info": {"general.architecture": arch, f"{arch}.context_length": info["context"]}}
        if path == "/api/generate" and body.get("keep_alive") == 0:
            self.running.pop(body.get("model", ""), None)
            return 200, {"done": True, "done_reason": "unload"}
        if path == "/api/chat":
            return self._chat(body)
        return 404, {"error": f"tidak ada {path}"}

    def _tag(self, name: str) -> dict[str, Any]:
        info = KNOWN.get(name, {})
        tag: dict[str, Any] = {"name": name, "model": name, "modified_at": "2026-11-01T00:00:00Z",
                               "size": info.get("size"),
                               "details": {"family": info.get("family"), "parameter_size": info.get("parameter_size"),
                                           "quantization_level": info.get("quantization_level")}}
        if info.get("remote_host"):
            tag |= {"remote_model": name, "remote_host": info["remote_host"]}
        return tag

    def _chat(self, body: dict[str, Any]) -> tuple[int, Any]:
        model = body.get("model", "")
        if model not in self.installed:
            return 404, {"error": f"model '{model}' not found"}
        self.running[model] = 4096
        last = next((m["content"] for m in reversed(body["messages"]) if m["role"] == "user"), "")
        if TRIGGER_ERROR in last:
            return 500, {"error": "simulasi error"}
        if TRIGGER_TIMEOUT in last:
            return 0, None  # MockTransport → ReadTimeout
        done = {"message": {"role": "assistant", "content": ""}, "done": True,
                "prompt_eval_count": 12, "eval_count": 40, "eval_duration": 2_000_000_000}
        if TRIGGER_BAD_TOOL in last:
            return 200, Paced([{"message": {"role": "assistant", "content": "",
                                            "tool_calls": [{"function": {"name": "x", "arguments": "{bukan json"}}]},
                                "done": False}], 0)
        if TRIGGER_TOOL in last or (body.get("tools") and "tugas" in last.lower()):
            name = body["tools"][0]["function"]["name"] if body.get("tools") else "tanpa_tool"
            args = {"judul": last[:40]} if name == "buat_tugas" else {}
            return 200, Paced([{"message": {"role": "assistant", "content": "",
                                            "tool_calls": [{"function": {"name": name, "arguments": args}}]},
                                "done": False}, done], 0)
        if body.get("format") is not None:
            return 200, Paced([{"message": {"role": "assistant", "content": json.dumps(_example(body["format"]))},
                                "done": False}, done], 0)
        lines: list[dict[str, Any]] = []
        if body.get("think"):
            lines.append({"message": {"role": "assistant", "content": "", "thinking": "Menimbang jawaban."},
                          "done": False})
        if TRIGGER_THINK_TAG in last:
            pieces = ["<thi", "nk>Berpikir di", " dalam tag</th", "ink>Jawaban", " akhir."]
        elif TRIGGER_SLOW in last:
            pieces = [f" kata{i}" for i in range(200)]
        else:
            pieces = WORDS
        lines += [{"message": {"role": "assistant", "content": w}, "done": False} for w in pieces]
        lines.append(done)
        slow = TRIGGER_SLOW in last
        return 200, self._paced(lines, 0.05 if slow else self.word_delay_s)

    @staticmethod
    def _paced(lines: list[dict[str, Any]], delay: float) -> Paced:
        return Paced(lines, delay)

    # ── httpx MockTransport ───────────────────────────────────────────────
    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handle)

    def handle(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content) if request.content else {}
        status, payload = self.respond(request.method, request.url.path, body)
        if status == 0:
            raise httpx.ReadTimeout("simulasi timeout", request=request)
        if isinstance(payload, Paced):
            return httpx.Response(status, content=payload.aiter_bytes(),
                                  headers={"content-type": "application/x-ndjson"})
        return httpx.Response(status, json=payload)


def _example(schema: dict[str, Any], defs: dict[str, Any] | None = None) -> Any:
    """Contoh yang lolos skema (untuk tes keluaran terstruktur)."""
    defs = defs if defs is not None else schema.get("$defs", {})
    if "$ref" in schema:
        return _example(defs[schema["$ref"].split("/")[-1]], defs)
    if "enum" in schema:
        return schema["enum"][0]
    kind = schema.get("type")
    if kind == "object":
        return {k: _example(v, defs) for k, v in schema.get("properties", {}).items()}
    if kind == "array":
        return [_example(schema.get("items", {"type": "string"}), defs) for _ in range(schema.get("minItems", 1))]
    if kind in ("integer", "number"):
        return 1
    if kind == "boolean":
        return True
    return "contoh teks"


# ── server HTTP sungguhan untuk E2E ────────────────────────────────────────
def serve(port: int, fake: FakeOllama | None = None) -> ThreadingHTTPServer:
    fake = fake or FakeOllama(["qwen3:4b", "uji-kecil:1b", "uji-embed:latest", "uji-awan:cloud"])
    lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *_: Any) -> None:
            return

        def _handle(self) -> None:
            length = int(self.headers.get("content-length") or 0)
            raw = self.rfile.read(length) if length else b""
            body = json.loads(raw) if raw else {}
            with lock:
                status, payload = fake.respond(self.command, self.path.split("?")[0], body)
            if status == 0:
                time.sleep(3600)
                return
            if isinstance(payload, Paced):
                self.send_response(status)
                self.send_header("content-type", "application/x-ndjson")
                self.send_header("transfer-encoding", "chunked")
                self.end_headers()
                try:
                    for line in payload:
                        data = (json.dumps(line) + "\n").encode()
                        self.wfile.write(f"{len(data):x}\r\n".encode() + data + b"\r\n")
                        self.wfile.flush()
                    self.wfile.write(b"0\r\n\r\n")
                except (BrokenPipeError, ConnectionResetError):
                    pass  # klien menghentikan jawaban (tombol Berhenti)
                return
            data = json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        do_GET = do_POST = do_DELETE = _handle

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.daemon_threads = True
    server.fake = fake  # type: ignore[attr-defined]
    return server


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Server Ollama tiruan untuk tes E2E")
    parser.add_argument("--port", type=int, default=11500)
    args = parser.parse_args()
    print(f"Ollama TIRUAN di http://127.0.0.1:{args.port}", flush=True)
    serve(args.port).serve_forever()
