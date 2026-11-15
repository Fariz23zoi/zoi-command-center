"""OAuth 2.0 Google untuk aplikasi desktop: PKCE (S256) + redirect loopback 127.0.0.1 di port acak.

ZOI tidak pernah melihat password Google: pengguna login di halaman Google sendiri. Scope hanya-baca.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import secrets
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qs, urlencode, urlsplit

from app.youtube.errors import YouTubeError

SCOPES = ("https://www.googleapis.com/auth/youtube.readonly",
          "https://www.googleapis.com/auth/yt-analytics.readonly")
CONNECT_TIMEOUT_S = 300.0
DONE_PAGE = (
    "<!doctype html><html lang='id'><meta charset='utf-8'><title>ZOI</title>"
    "<body style='font-family:system-ui;margin:3rem;max-width:32rem'>"
    "<h1>ZOI menerima jawaban dari Google</h1>"
    "<p>Tab ini boleh ditutup. Kembali ke tab ZOI untuk melihat hasilnya.</p></body></html>"
)


@dataclass(frozen=True)
class Endpoints:
    auth: str
    token: str
    revoke: str
    data_api: str
    analytics_api: str
    is_test: bool


def endpoints(test_url: str = "") -> Endpoints:
    if test_url:
        return Endpoints(f"{test_url}/o/oauth2/v2/auth", f"{test_url}/token", f"{test_url}/revoke",
                         f"{test_url}/youtube/v3", f"{test_url}/v2", True)
    return Endpoints("https://accounts.google.com/o/oauth2/v2/auth", "https://oauth2.googleapis.com/token",
                     "https://oauth2.googleapis.com/revoke", "https://www.googleapis.com/youtube/v3",
                     "https://youtubeanalytics.googleapis.com/v2", False)


@dataclass(frozen=True)
class ClientConfig:
    client_id: str
    client_secret: str

    @property
    def hint(self) -> str:
        return f"…{self.client_id[-28:]}" if len(self.client_id) > 28 else self.client_id


def parse_client_config(data: Any) -> ClientConfig:
    """Menerima isi file JSON client OAuth bertipe **Desktop app**. Alamat endpoint di file DIABAIKAN."""
    if not isinstance(data, dict):
        raise YouTubeError("File client OAuth tidak valid (bukan JSON objek).")
    if "web" in data and "installed" not in data:
        raise YouTubeError("Ini client OAuth bertipe 'Web application'. Buat client bertipe 'Desktop app' "
                           "di Google Cloud, lalu unduh file JSON-nya.")
    installed = data.get("installed")
    if not isinstance(installed, dict):
        raise YouTubeError("File ini bukan file client OAuth 'Desktop app' (tidak ada bagian 'installed').")
    client_id, client_secret = installed.get("client_id"), installed.get("client_secret")
    if not isinstance(client_id, str) or not isinstance(client_secret, str) or not client_id or not client_secret:
        raise YouTubeError("File client OAuth tidak lengkap (client_id / client_secret tidak ada).")
    if len(client_id) > 200 or len(client_secret) > 200:
        raise YouTubeError("File client OAuth tidak valid.")
    return ClientConfig(client_id=client_id, client_secret=client_secret)


def new_pkce() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest()).rstrip(b"=").decode()
    return verifier, challenge


def build_auth_url(ep: Endpoints, client: ClientConfig, redirect_uri: str, state: str, challenge: str) -> str:
    query = urlencode({
        "client_id": client.client_id, "redirect_uri": redirect_uri, "response_type": "code",
        "scope": " ".join(SCOPES), "state": state, "code_challenge": challenge, "code_challenge_method": "S256",
        "access_type": "offline", "prompt": "consent",
    })
    return f"{ep.auth}?{query}"


class LoopbackListener:
    """Pendengar HTTP sementara di 127.0.0.1:port-acak untuk menerima redirect Google. Sekali pakai."""

    def __init__(self) -> None:
        self.result: asyncio.Future[dict[str, str]] = asyncio.get_running_loop().create_future()
        self._server: asyncio.Server | None = None
        self.port = 0

    async def start(self) -> int:
        self._server = await asyncio.start_server(self._handle, host="127.0.0.1", port=0)
        self.port = self._server.sockets[0].getsockname()[1]
        return self.port

    @property
    def redirect_uri(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        status, body = "404 Not Found", "Tidak ditemukan."
        try:
            line = await asyncio.wait_for(reader.readline(), timeout=5)
            parts = line.decode("latin-1").split(" ")
            if len(parts) >= 2 and parts[0] == "GET":
                url = urlsplit(parts[1])
                params = {k: v[0] for k, v in parse_qs(url.query).items() if v}
                if url.path in ("", "/") and ("code" in params or "error" in params):
                    status, body = "200 OK", DONE_PAGE
                    if not self.result.done():
                        self.result.set_result(params)
        except (TimeoutError, UnicodeDecodeError, ValueError):
            status, body = "400 Bad Request", "Permintaan tidak valid."
        payload = body.encode("utf-8")
        writer.write((f"HTTP/1.1 {status}\r\nContent-Type: text/html; charset=utf-8\r\n"
                      f"Content-Length: {len(payload)}\r\nCache-Control: no-store\r\nConnection: close\r\n\r\n"
                      ).encode("ascii") + payload)
        try:
            await writer.drain()
            writer.close()
        except OSError:
            pass

    async def close(self) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
        if not self.result.done():
            self.result.cancel()
