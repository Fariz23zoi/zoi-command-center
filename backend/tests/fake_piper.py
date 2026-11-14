"""Server Piper TIRUAN — hanya untuk tes. Meniru bentuk API HTTP Piper (/voices, /synthesize), bukan suaranya.

- `FakePiper().transport()` → httpx.MockTransport untuk pytest.
- `python -m tests.fake_piper --port 5599` → server HTTP sungguhan untuk E2E.
"""

from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

import httpx

from app.voice.wav import tone_wav

VOICES = {"id_ID-news_tts-medium": {"language": {"code": "id_ID"}, "num_speakers": 1}}


class FakePiper:
    def __init__(self, *, broken_audio: bool = False) -> None:
        self.requests: list[dict[str, Any]] = []
        self.broken_audio = broken_audio

    def respond(self, method: str, path: str, body: dict[str, Any]) -> tuple[int, str, bytes]:
        self.requests.append({"method": method, "path": path, **body})
        if method == "GET" and path == "/voices":
            return 200, "application/json", json.dumps(VOICES).encode()
        if method == "POST" and path == "/synthesize":
            if not body.get("text"):
                return 400, "text/plain", b"text required"
            if self.broken_audio:
                return 200, "text/plain", b"bukan audio"
            seconds = min(4.0, max(0.3, len(body["text"]) / 15.0)) * float(body.get("length_scale", 1.0))
            return 200, "audio/wav", tone_wav(seconds, rate=22_050)
        return 404, "text/plain", b"not found"

    def transport(self) -> httpx.MockTransport:
        def handle(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content) if request.content else {}
            status, kind, data = self.respond(request.method, request.url.path, body)
            return httpx.Response(status, content=data, headers={"content-type": kind})

        return httpx.MockTransport(handle)


def serve(port: int) -> ThreadingHTTPServer:
    fake = FakePiper()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_: Any) -> None:
            return

        def _handle(self) -> None:
            length = int(self.headers.get("content-length") or 0)
            body = json.loads(self.rfile.read(length)) if length else {}
            status, kind, data = fake.respond(self.command, self.path.split("?")[0], body)
            self.send_response(status)
            self.send_header("content-type", kind)
            self.send_header("content-length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        do_GET = do_POST = _handle

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.daemon_threads = True
    return server


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Server Piper tiruan untuk tes E2E")
    parser.add_argument("--port", type=int, default=5599)
    args = parser.parse_args()
    print(f"Piper TIRUAN di http://127.0.0.1:{args.port}", flush=True)
    serve(args.port).serve_forever()
