"""Server Google/YouTube TIRUAN — hanya untuk tes. Meniru BENTUK OAuth 2.0 (PKCE), YouTube Data API v3 dan
YouTube Analytics API v2; semua angkanya karangan untuk tes dan tidak pernah berasal dari YouTube.

- `FakeGoogle().start()` → server HTTP di 127.0.0.1:port-acak (pytest).
- `python -m tests.fake_google --port 5600` → server untuk E2E.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import secrets
import threading
from datetime import date, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlencode, urlsplit

SCOPES = "https://www.googleapis.com/auth/youtube.readonly https://www.googleapis.com/auth/yt-analytics.readonly"
CHANNEL_ID = "UCfakeChannel000000000001"
UPLOADS = "UUfakeChannel000000000001"
VIDEOS = [
    {"id": "vidAAAAAAA1", "title": "Video uji pertama", "views": "1200", "likes": "80", "comments": "12",
     "duration": "PT8M12S", "privacy": "public", "published": "2026-11-01T10:00:00Z"},
    {"id": "vidAAAAAAA2", "title": "Video uji kedua", "views": "340", "likes": "21", "comments": "3",
     "duration": "PT45S", "privacy": "public", "published": "2026-10-20T10:00:00Z"},
    {"id": "vidAAAAAAA3", "title": "Draf pribadi", "views": "0", "likes": "0", "comments": "0",
     "duration": "PT2M", "privacy": "private", "published": "2026-10-10T10:00:00Z"},
]
METRICS = ["views", "estimatedMinutesWatched", "averageViewDuration", "subscribersGained", "subscribersLost"]
VIDEO_METRICS = ["views", "estimatedMinutesWatched", "averageViewDuration", "averageViewPercentage"]
# Data PUBLIK tiruan (channel lain, Trending, pencarian) — karangan untuk tes.
OTHER_ID = "UCotherChannel0000000002"
OTHER_UPLOADS = "UUotherChannel0000000002"
OTHER_VIDEOS = [
    {"id": "othAAAAAAA1", "title": "Resep kopi susu gula aren", "views": "90100", "likes": "4100", "comments": "230",
     "duration": "PT6M", "privacy": "public", "published": "2026-11-10T03:00:00Z"},
    {"id": "othAAAAAAA2", "title": "Review grinder kopi murah", "views": "15800", "likes": "700", "comments": "64",
     "duration": "PT11M", "privacy": "public", "published": "2026-11-03T03:00:00Z"},
]
TRENDING = [
    {"id": "trdAAAAAAA1", "title": "Cara seduh kopi V60 untuk pemula", "channel": "Kopi Harian", "category": "26"},
    {"id": "trdAAAAAAA2", "title": "Resep kopi susu ala kafe", "channel": "Dapur Kopi", "category": "26"},
    {"id": "trdAAAAAAA3", "title": "Highlight final bulu tangkis", "channel": "Olahraga ID", "category": "17"},
    {"id": "trdAAAAAAA4", "title": "Tips belajar coding dari nol", "channel": "Kode Santai", "category": "27"},
]
CATEGORIES = [("17", "Olahraga", True), ("26", "Cara & Gaya", True), ("27", "Pendidikan", True),
              ("44", "Trailer", False)]


class FakeGoogle:
    def __init__(self) -> None:
        self.requests: list[dict[str, Any]] = []
        self.codes: dict[str, dict[str, str]] = {}
        self.access_tokens: set[str] = set()
        self.refresh_tokens: set[str] = set()
        self.revoked: set[str] = set()
        # Sakelar skenario
        self.deny = False
        self.no_refresh_token = False
        self.granted_scope = SCOPES
        self.no_channel = False
        self.quota_exceeded = False
        self.analytics_forbidden = False
        self.subscribers = "1530"
        self.by_video_forbidden = False
        self.server: ThreadingHTTPServer | None = None

    # ── util ──────────────────────────────────────────────────────────────
    def count(self, path: str) -> int:
        return sum(1 for r in self.requests if r["path"] == path)

    def expire_access_tokens(self) -> None:
        self.access_tokens.clear()

    def revoke_all(self) -> None:
        self.revoked |= self.refresh_tokens
        self.access_tokens.clear()

    def _new_access(self) -> dict[str, Any]:
        token = "at-" + secrets.token_hex(8)
        self.access_tokens.add(token)
        return {"access_token": token, "expires_in": 3600, "token_type": "Bearer", "scope": self.granted_scope}

    # ── inti ──────────────────────────────────────────────────────────────
    def respond(self, method: str, path: str, query: dict[str, str], form: dict[str, str],
                headers: dict[str, str]) -> tuple[int, dict[str, str], bytes]:
        self.requests.append({"method": method, "path": path, "query": query, "form": dict(form)})

        def js(status: int, body: Any) -> tuple[int, dict[str, str], bytes]:
            return status, {"content-type": "application/json"}, json.dumps(body).encode()

        if method == "GET" and path == "/healthz":
            return js(200, {"fake": True})

        if method == "GET" and path == "/o/oauth2/v2/auth":
            redirect = query.get("redirect_uri", "")
            problems = [name for name, ok in {
                "response_type": query.get("response_type") == "code",
                "code_challenge_method": query.get("code_challenge_method") == "S256",
                "code_challenge": len(query.get("code_challenge", "")) >= 43,
                "redirect_uri": redirect.startswith(("http://127.0.0.1:", "https://")),
                "access_type": query.get("access_type") == "offline",
                "scope": "youtube.readonly" in query.get("scope", ""),
                "state": bool(query.get("state")),
                "client_id": bool(query.get("client_id")),
            }.items() if not ok]
            if problems:
                return 400, {"content-type": "text/plain"}, f"bad auth request: {problems}".encode()
            if self.deny:
                target = f"{redirect}/?{urlencode({'error': 'access_denied', 'state': query['state']})}"
            else:
                code = "code-" + secrets.token_hex(8)
                self.codes[code] = {"challenge": query["code_challenge"], "redirect_uri": redirect,
                                    "client_id": query["client_id"]}
                answer = {'code': code, 'state': query['state'], 'scope': self.granted_scope}
                target = f"{redirect}/?{urlencode(answer)}"
            return 302, {"location": target}, b""

        if method == "POST" and path == "/token":
            if form.get("grant_type") == "authorization_code":
                issued = self.codes.pop(form.get("code", ""), None)
                if issued is None:
                    return js(400, {"error": "invalid_grant"})
                digest = hashlib.sha256(form.get("code_verifier", "").encode()).digest()
                challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
                if challenge != issued["challenge"] or form.get("redirect_uri") != issued["redirect_uri"] \
                        or form.get("client_id") != issued["client_id"] or not form.get("client_secret"):
                    return js(400, {"error": "invalid_request"})
                body = self._new_access()
                if not self.no_refresh_token:
                    refresh = "rt-" + secrets.token_hex(8)
                    self.refresh_tokens.add(refresh)
                    body["refresh_token"] = refresh
                return js(200, body)
            if form.get("grant_type") == "refresh_token":
                refresh = form.get("refresh_token", "")
                if refresh not in self.refresh_tokens or refresh in self.revoked:
                    return js(400, {"error": "invalid_grant"})
                return js(200, self._new_access())
            return js(400, {"error": "unsupported_grant_type"})

        if method == "POST" and path == "/revoke":
            token = form.get("token", "")
            if token not in self.refresh_tokens:
                return js(400, {"error": "invalid_token"})
            self.revoked.add(token)
            self.access_tokens.clear()
            return js(200, {})

        if method == "GET" and (path.startswith("/youtube/v3/") or path == "/v2/reports"):
            bearer = headers.get("authorization", "").removeprefix("Bearer ").strip()
            if bearer not in self.access_tokens:
                return js(401, {"error": {"code": 401, "message": "Invalid Credentials",
                                          "errors": [{"reason": "authError"}]}})
            if self.quota_exceeded and path.startswith("/youtube/v3/"):
                return js(403, {"error": {"code": 403, "message": "quota exceeded",
                                          "errors": [{"reason": "quotaExceeded"}]}})
            if path == "/youtube/v3/channels":
                if query.get("id") == OTHER_ID or query.get("forHandle") == "@kopilain":
                    return js(200, {"items": [{
                        "id": OTHER_ID,
                        "snippet": {"title": "Kopi Lain", "customUrl": "@kopilain",
                                    "publishedAt": "2022-03-01T00:00:00Z", "country": "ID"},
                        "statistics": {"viewCount": "880000", "subscriberCount": "12400",
                                       "hiddenSubscriberCount": False, "videoCount": "140"},
                        "contentDetails": {"relatedPlaylists": {"uploads": OTHER_UPLOADS}}}]})
                if "id" in query or "forHandle" in query:
                    return js(200, {"items": []})
                if query.get("mine") != "true":
                    return js(400, {"error": {"code": 400, "message": "mine required", "errors": []}})
                if self.no_channel:
                    return js(200, {"items": []})
                return js(200, {"items": [{
                    "id": CHANNEL_ID,
                    "snippet": {"title": "Channel Uji ZOI", "customUrl": "@channelujizoi",
                                "publishedAt": "2024-01-05T00:00:00Z", "country": "ID"},
                    "statistics": {"viewCount": "45210", "subscriberCount": self.subscribers,
                                   "hiddenSubscriberCount": False, "videoCount": "37"},
                    "contentDetails": {"relatedPlaylists": {"uploads": UPLOADS}}}]})
            if path == "/youtube/v3/playlistItems":
                if query.get("playlistId") == OTHER_UPLOADS:
                    return js(200, {"items": [{"contentDetails": {"videoId": v["id"]}} for v in OTHER_VIDEOS]})
                if query.get("playlistId") != UPLOADS:
                    return js(404, {"error": {"code": 404, "message": "playlist not found", "errors": []}})
                return js(200, {"items": [{"contentDetails": {"videoId": v["id"]}} for v in VIDEOS]})
            if path == "/youtube/v3/videoCategories":
                return js(200, {"items": [{"id": cid, "snippet": {"title": title, "assignable": ok}}
                                          for cid, title, ok in CATEGORIES]})
            if path == "/youtube/v3/search":
                if query.get("type") != "video" or not query.get("q"):
                    return js(400, {"error": {"code": 400, "message": "bad search", "errors": []}})
                return js(200, {"items": [{
                    "id": {"kind": "youtube#video", "videoId": v["id"]},
                    "snippet": {"title": v["title"], "channelTitle": v["channel"], "channelId": "UCx" + v["id"],
                                "publishedAt": "2026-11-12T00:00:00Z"}}
                    for v in TRENDING if query["q"].lower().split()[0] in v["title"].lower()]})
            if path == "/youtube/v3/videos" and query.get("chart") == "mostPopular":
                if query.get("regionCode") != "ID":
                    return js(400, {"error": {"code": 400, "message": "region", "errors": []}})
                category = query.get("videoCategoryId")
                return js(200, {"items": [{
                    "id": v["id"],
                    "snippet": {"title": v["title"], "channelTitle": v["channel"], "channelId": "UCx" + v["id"],
                                "publishedAt": "2026-11-12T00:00:00Z", "categoryId": v["category"]},
                    "statistics": {"viewCount": str(500000 - 1000 * i), "likeCount": "9000", "commentCount": "410"},
                    "contentDetails": {"duration": "PT9M"}}
                    for i, v in enumerate(TRENDING) if category in (None, v["category"])]})
            if path == "/youtube/v3/videos":
                wanted = query.get("id", "").split(",")
                return js(200, {"items": [{
                    "id": v["id"], "snippet": {"title": v["title"], "publishedAt": v["published"]},
                    "statistics": {"viewCount": v["views"], "likeCount": v["likes"], "commentCount": v["comments"]},
                    "contentDetails": {"duration": v["duration"]}, "status": {"privacyStatus": v["privacy"]},
                } for v in [*VIDEOS, *OTHER_VIDEOS] if v["id"] in wanted]})
            if path == "/v2/reports":
                if self.analytics_forbidden:
                    return js(403, {"error": {"code": 403, "message": "Forbidden",
                                              "errors": [{"reason": "forbidden"}]}})
                if query.get("dimensions") == "video":
                    if self.by_video_forbidden:
                        return js(403, {"error": {"code": 403, "message": "Forbidden",
                                                  "errors": [{"reason": "forbidden"}]}})
                    if query.get("metrics", "").split(",") != VIDEO_METRICS or query.get("sort") != "-views":
                        return js(400, {"error": {"code": 400, "message": "bad video report", "errors": []}})
                    columns = [{"name": "video", "columnType": "DIMENSION"},
                               *[{"name": m, "columnType": "METRIC"} for m in VIDEO_METRICS]]
                    return js(200, {"columnHeaders": columns,
                                    "rows": [["vidAAAAAAA1", 900, 2700, 180, 42.5], ["vidAAAAAAA2", 210, 120, 34, 76.1],
                                             ["vidHAPUS0001", 12, 9, 45, 20.0]]})
                if query.get("dimensions") in ("insightTrafficSourceType", "deviceType"):
                    if query.get("metrics") != "views" or query.get("sort") != "-views":
                        return js(400, {"error": {"code": 400, "message": "bad breakdown", "errors": []}})
                    dim = query["dimensions"]
                    traffic = [["YT_SEARCH", 500], ["SUGGESTED", 300], ["EXT_URL", 50]]
                    rows = traffic if dim == "insightTrafficSourceType" else [["MOBILE", 700], ["DESKTOP", 150]]
                    return js(200, {"columnHeaders": [{"name": dim, "columnType": "DIMENSION"},
                                                      {"name": "views", "columnType": "METRIC"}], "rows": rows})
                if query.get("ids") != "channel==MINE" or query.get("metrics", "").split(",") != METRICS:
                    return js(400, {"error": {"code": 400, "message": "bad report query", "errors": []}})
                start, end = date.fromisoformat(query["startDate"]), date.fromisoformat(query["endDate"])
                days = (end - start).days + 1
                headers_out = [{"name": m, "columnType": "METRIC"} for m in METRICS]
                if query.get("dimensions") == "day":
                    headers_out.insert(0, {"name": "day", "columnType": "DIMENSION"})
                    rows = [[(start + timedelta(days=i)).isoformat(), 100 + i, 300 + 2 * i, 180, 3, 1]
                            for i in range(days)]
                else:
                    rows = [[days * 110, days * 330, 181, days * 3, days]]
                return js(200, {"kind": "youtubeAnalytics#resultTable", "columnHeaders": headers_out, "rows": rows})
        return js(404, {"error": {"code": 404, "message": "not found", "errors": []}})

    # ── server HTTP ───────────────────────────────────────────────────────
    def start(self, port: int = 0) -> str:
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_: Any) -> None:
                return

            def _handle(self) -> None:
                url = urlsplit(self.path)
                query = {k: v[0] for k, v in parse_qs(url.query).items()}
                length = int(self.headers.get("content-length") or 0)
                raw = self.rfile.read(length).decode() if length else ""
                form = {k: v[0] for k, v in parse_qs(raw).items()}
                status, headers, data = fake.respond(self.command, url.path, query, form,
                                                     {k.lower(): v for k, v in self.headers.items()})
                self.send_response(status)
                for key, value in headers.items():
                    self.send_header(key, value)
                self.send_header("content-length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            do_GET = do_POST = _handle  # noqa: N815

        self.server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        return f"http://127.0.0.1:{self.server.server_address[1]}"

    def stop(self) -> None:
        if self.server is not None:
            self.server.shutdown()
            self.server.server_close()
            self.server = None


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=5600)
    google = FakeGoogle()
    print(f"Google TIRUAN (tes) di {google.start(parser.parse_args().port)}", flush=True)
    threading.Event().wait()
