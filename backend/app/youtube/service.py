"""Layanan YouTube: koneksi akun, data channel SENDIRI, kuota, dan aturan penyimpanan.

Kepatuhan (YouTube API Developer Policies, dicek 14 Nov 2026):
- Hanya data berizin OAuth milik channel pengguna yang disimpan di sini; boleh >30 hari (III.E.4.b) selama izin
  dicek ulang tiap 30 hari → bila tidak terverifikasi >30 hari, data dihapus (`enforce_retention`).
- Angka ditampilkan persis seperti dikirim YouTube; ZOI tidak membuat metrik turunan (III.E.4.h).
- "Putuskan & hapus data" menghapus token dan seluruh data YouTube seketika (III.E.4.g).
"""

from __future__ import annotations

import asyncio
import json
import secrets
import time
from collections.abc import Callable
from datetime import date, datetime, timedelta
from functools import cache
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import delete, select

from app.core.events import EventBus
from app.db.base import utcnow
from app.db.models import AppMeta, YouTubeCache, YouTubeSnapshot
from app.db.session import Database
from app.logging_setup import get_logger
from app.security.cost_guard import CostGuard, CostGuardBlocked
from app.youtube.errors import NeedsReauth, QuotaExceeded, YouTubeError
from app.youtube.oauth import (
    CONNECT_TIMEOUT_S,
    SCOPES,
    ClientConfig,
    Endpoints,
    LoopbackListener,
    build_auth_url,
    new_pkce,
    parse_client_config,
)
from app.youtube.quota import QuotaTracker
from app.youtube.secrets_store import SecretStore

log = get_logger("youtube")

ACCOUNT_KEY = "youtube_account"
CLIENT_NAME = "youtube_client"  # nama entri file client di penyimpanan rahasia (mode online)
WEB_CONNECT_TIMEOUT_S = 300.0
TOKEN_NAME = "youtube_refresh_token"  # noqa: S105 — nama entri, bukan rahasia
REVERIFY_DAYS = 30
RECENT_VIDEOS = 25
ANALYTICS_METRICS = "views,estimatedMinutesWatched,averageViewDuration,subscribersGained,subscribersLost"
# Laporan per video: persentase tonton dihitung YOUTUBE (averageViewPercentage), bukan ZOI.
VIDEO_METRICS = "views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage"
TIMEOUT = httpx.Timeout(connect=10.0, read=30.0, write=10.0, pool=10.0)
YPP_FILE = Path(__file__).resolve().parent / "ypp.json"


@cache
def ypp_requirements() -> dict[str, Any]:
    return json.loads(YPP_FILE.read_text(encoding="utf-8"))


def _int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


class YouTubeService:
    def __init__(self, *, db: Database, bus: EventBus, guard: CostGuard, endpoints: Endpoints, data_dir: Path,
                 store: SecretStore | None = None, transport: httpx.AsyncBaseTransport | None = None,
                 connect_timeout_s: float = CONNECT_TIMEOUT_S, web_callback_url: str = "") -> None:
        self.db = db
        self.bus = bus
        self.guard = guard
        self.ep = endpoints
        self.store = store or SecretStore(data_dir)
        self.quota = QuotaTracker(db)
        self.client_file = data_dir / "secrets" / "youtube_client.json"
        self.web_callback_url = web_callback_url  # terisi di mode online → alur OAuth Web application
        self.connect_timeout_s = connect_timeout_s
        self._transport = transport
        self._access: tuple[str, float] | None = None
        self._pending: dict[str, Any] | None = None
        self._last_error: str | None = None
        self._lock = asyncio.Lock()
        # Dipanggil saat akun diputuskan (data publik & daftar pantauan ikut dihapus).
        self.purge_hooks: list[Callable[[], None]] = []

    # ── HTTP ──────────────────────────────────────────────────────────────
    def _http(self) -> httpx.AsyncClient:
        kwargs: dict[str, Any] = {"timeout": TIMEOUT}
        if self._transport is not None:
            kwargs["transport"] = self._transport
        return self.guard.async_client(**kwargs)

    async def _post_form(self, url: str, data: dict[str, str]) -> httpx.Response:
        try:
            async with self._http() as client:
                return await client.post(url, data=data)
        except CostGuardBlocked as exc:
            raise YouTubeError(str(exc)) from exc
        except httpx.HTTPError as exc:
            raise YouTubeError(f"Google tidak dapat dihubungi ({type(exc).__name__}). Periksa koneksi internet.",
                               status_code=502, code="unreachable") from exc

    # ── client OAuth ──────────────────────────────────────────────────────
    @property
    def _client_kind(self) -> str:
        return "web" if self.web_callback_url else "installed"

    def _client_raw(self) -> str | None:
        if self.store.kind == "database":
            return self.store.get(CLIENT_NAME)
        try:
            return self.client_file.read_text(encoding="utf-8")
        except OSError:
            return None

    def client(self) -> ClientConfig | None:
        raw = self._client_raw()
        if raw is None:
            return None
        try:
            return parse_client_config(json.loads(raw), expect=self._client_kind)
        except (ValueError, YouTubeError):
            return None

    def import_client(self, data: Any) -> dict[str, Any]:
        config = parse_client_config(data, expect=self._client_kind)
        if not self.ep.is_test and not config.client_id.endswith(".apps.googleusercontent.com"):
            raise YouTubeError("client_id tidak berbentuk client Google (…apps.googleusercontent.com).")
        if self.account():
            raise YouTubeError("Akun masih terhubung. Putuskan dulu sebelum mengganti file client.", status_code=409)
        payload = json.dumps({config.kind: {"client_id": config.client_id,
                                            "client_secret": config.client_secret}})
        if self.store.kind == "database":
            self.store.set(CLIENT_NAME, payload)  # terenkripsi di database (mode online)
        else:
            self.client_file.parent.mkdir(parents=True, exist_ok=True)
            self.client_file.write_text(payload, encoding="utf-8")
        self._changed()
        return {"client_id_hint": config.hint}

    def delete_client(self) -> None:
        if self.account():
            raise YouTubeError("Putuskan akun dulu sebelum menghapus file client.", status_code=409)
        if self.store.kind == "database":
            self.store.delete(CLIENT_NAME)
        else:
            self.client_file.unlink(missing_ok=True)
        self._changed()

    # ── akun ──────────────────────────────────────────────────────────────
    def account(self) -> dict[str, Any] | None:
        with self.db.session() as s:
            row = s.get(AppMeta, ACCOUNT_KEY)
            return json.loads(row.value_json) if row else None

    def _save_account(self, account: dict[str, Any] | None) -> None:
        with self.db.session() as s:
            row = s.get(AppMeta, ACCOUNT_KEY)
            if account is None:
                if row is not None:
                    s.delete(row)
            elif row is None:
                s.add(AppMeta(key=ACCOUNT_KEY, value_json=json.dumps(account, ensure_ascii=False)))
            else:
                row.value_json = json.dumps(account, ensure_ascii=False)

    def _changed(self) -> None:
        self.bus.publish("youtube.updated", {})

    async def status(self) -> dict[str, Any]:
        self.enforce_retention()
        client = self.client()
        account = self.account()
        if account and not account.get("needs_reauth") and self.store.get(TOKEN_NAME) is None:
            account = {**account, "needs_reauth": True}  # mis. data dipulihkan di komputer lain: token tidak ikut
        return {
            "client_configured": client is not None, "client_id_hint": client.hint if client else None,
            "connected": account is not None, "account": account,
            "pending": self._pending is not None, "last_error": self._last_error,
            "token_storage": self.store.kind, "storage_warning": self.store.warning,
            "test_endpoint": self.ep.is_test, "scopes": list(SCOPES), "can_publish": False,
            "web_flow": bool(self.web_callback_url), "callback_url": self.web_callback_url or None,
            "client_kind": self._client_kind,
            "quota": self.quota.status(),
            "policy": {"reverify_days": REVERIFY_DAYS,
                       "summary": "Hanya data channel-mu sendiri yang disimpan. ZOI tidak membuat skor/metrik "
                                  "turunan dari data YouTube dan tidak bisa mengunggah atau mengubah apa pun."},
        }

    # ── menghubungkan ─────────────────────────────────────────────────────
    async def start_connect(self) -> dict[str, Any]:
        client = self.client()
        if client is None:
            kind = "Web application" if self.web_callback_url else "Desktop app"
            raise YouTubeError(f"Impor dulu file client OAuth ({kind}) dari Google Cloud.", status_code=409)
        if self.account():
            raise YouTubeError("Akun sudah terhubung. Putuskan dulu untuk menghubungkan akun lain.", status_code=409)
        await self.cancel_connect()
        if self.web_callback_url:
            verifier, challenge = new_pkce()
            state = secrets.token_urlsafe(24)
            self._last_error = None
            self._pending = {"web": True, "state": state, "verifier": verifier,
                             "deadline": time.monotonic() + WEB_CONNECT_TIMEOUT_S}
            self._changed()
            return {"auth_url": build_auth_url(self.ep, client, self.web_callback_url, state, challenge),
                    "expires_in_s": int(WEB_CONNECT_TIMEOUT_S)}
        listener = LoopbackListener()
        await listener.start()
        verifier, challenge = new_pkce()
        state = secrets.token_urlsafe(24)
        self._last_error = None
        task = asyncio.create_task(self._wait_for_redirect(listener, client, state, verifier))
        self._pending = {"listener": listener, "task": task}
        self._changed()
        return {"auth_url": build_auth_url(self.ep, client, listener.redirect_uri, state, challenge),
                "expires_in_s": int(self.connect_timeout_s)}

    async def cancel_connect(self) -> None:
        pending, self._pending = self._pending, None
        if pending:
            if not pending.get("web"):
                pending["task"].cancel()
                await pending["listener"].close()
            self._changed()

    async def handle_web_callback(self, params: dict[str, str]) -> None:
        """Jawaban Google di alur web (mode online). Galat masuk `last_error` agar tampil di halaman Settings."""
        pending = self._pending
        if not pending or not pending.get("web"):
            self._last_error = "Tidak ada permintaan hubungkan yang sedang berjalan. Mulai dari Settings › YouTube."
            self._changed()
            return
        self._pending = None
        client = self.client()
        try:
            if client is None:
                raise YouTubeError("File client OAuth tidak ditemukan. Impor ulang di Settings › YouTube.")
            if time.monotonic() > pending["deadline"]:
                raise YouTubeError("Waktu habis menunggu persetujuan di halaman Google. Coba hubungkan lagi.")
            await self._complete(client, self.web_callback_url, pending["state"], pending["verifier"], params)
            self._last_error = None
        except YouTubeError as exc:
            self._last_error = exc.message
        except Exception as exc:  # noqa: BLE001 — dilaporkan, tidak disembunyikan
            log.exception("youtube_web_callback_failed")
            self._last_error = f"Kesalahan internal saat menghubungkan ({type(exc).__name__})."
        finally:
            self._changed()

    async def _wait_for_redirect(self, listener: LoopbackListener, client: ClientConfig, state: str,
                                 verifier: str) -> None:
        try:
            params = await asyncio.wait_for(asyncio.shield(listener.result), timeout=self.connect_timeout_s)
            await self._complete(client, listener.redirect_uri, state, verifier, params)
        except TimeoutError:
            self._last_error = "Waktu habis menunggu persetujuan di halaman Google. Coba hubungkan lagi."
        except asyncio.CancelledError:
            return
        except YouTubeError as exc:
            self._last_error = exc.message
        except Exception as exc:  # noqa: BLE001 — dilaporkan, tidak disembunyikan
            log.exception("youtube_connect_failed")
            self._last_error = f"Kesalahan internal saat menghubungkan ({type(exc).__name__})."
        finally:
            await listener.close()
            if self._pending and self._pending.get("listener") is listener:
                self._pending = None
            self._changed()

    async def _complete(self, client: ClientConfig, redirect_uri: str, state: str, verifier: str,
                        params: dict[str, str]) -> None:
        if not secrets.compare_digest(params.get("state", ""), state):
            raise YouTubeError("Jawaban dari Google tidak cocok dengan permintaan (state berbeda). Coba lagi.")
        if "error" in params:
            reason = "kamu menolak izin" if params["error"] == "access_denied" else params["error"][:80]
            raise YouTubeError(f"Google tidak memberi izin: {reason}.")
        response = await self._post_form(self.ep.token, {
            "grant_type": "authorization_code", "code": params.get("code", ""), "client_id": client.client_id,
            "client_secret": client.client_secret, "redirect_uri": redirect_uri, "code_verifier": verifier})
        token = self._token_json(response, "menukar kode izin")
        refresh = token.get("refresh_token")
        if not isinstance(refresh, str) or not refresh:
            raise YouTubeError("Google tidak mengirim refresh token. Cabut akses ZOI di myaccount.google.com › "
                               "Security › Third-party access, lalu hubungkan lagi.")
        granted = set(str(token.get("scope", "")).split())
        if SCOPES[0] not in granted:
            raise YouTubeError("Izin membaca channel (youtube.readonly) tidak dicentang. Hubungkan lagi dan "
                               "centang semua izin yang diminta.")
        self._remember_access(token)
        self.store.set(TOKEN_NAME, refresh)
        try:
            channel = await self._fetch_channel(client)
        except YouTubeError:
            self.store.delete(TOKEN_NAME)
            self._access = None
            raise
        now = utcnow().isoformat()
        self._save_account({"channel_id": channel["id"], "title": channel["title"],
                            "custom_url": channel.get("custom_url"), "connected_at": now, "verified_at": now,
                            "scopes": sorted(granted & set(SCOPES)), "analytics_granted": SCOPES[1] in granted,
                            "needs_reauth": False})
        self._store_channel(channel)

    def _token_json(self, response: httpx.Response, action: str) -> dict[str, Any]:
        try:
            data = response.json()
        except ValueError:
            data = {}
        if response.status_code != 200 or not isinstance(data, dict) or "access_token" not in data:
            error = data.get("error") if isinstance(data, dict) else None
            if error == "invalid_grant":
                raise NeedsReauth()
            raise YouTubeError(f"Google menolak saat {action} ({response.status_code}: {str(error)[:80]}).")
        return data

    def _remember_access(self, token: dict[str, Any]) -> None:
        self._access = (token["access_token"], time.monotonic() + max(60, int(token.get("expires_in", 3600)) - 60))

    async def _access_token(self, client: ClientConfig) -> str:
        if self._access and time.monotonic() < self._access[1]:
            return self._access[0]
        refresh = self.store.get(TOKEN_NAME)
        if not refresh:
            raise NeedsReauth("Token YouTube tidak ditemukan di komputer ini. Hubungkan ulang akun di "
                              "Settings › YouTube.")
        response = await self._post_form(self.ep.token, {
            "grant_type": "refresh_token", "refresh_token": refresh, "client_id": client.client_id,
            "client_secret": client.client_secret})
        try:
            token = self._token_json(response, "memperbarui token")
        except NeedsReauth:
            account = self.account()
            if account:
                self._save_account({**account, "needs_reauth": True})
                self._changed()
            raise
        self._remember_access(token)
        return token["access_token"]

    async def disconnect(self) -> dict[str, Any]:
        """Mencabut token di Google (bila bisa), lalu menghapus token & SEMUA data YouTube di komputer ini."""
        await self.cancel_connect()
        refresh = self.store.get(TOKEN_NAME)
        revoked = False
        if refresh:
            try:
                revoked = (await self._post_form(self.ep.revoke, {"token": refresh})).status_code == 200
            except YouTubeError:
                revoked = False
        self.store.delete(TOKEN_NAME)
        self._access = None
        self._purge_data()
        for hook in self.purge_hooks:
            hook()
        self._save_account(None)
        self._last_error = None
        self._changed()
        return {"revoked_at_google": revoked,
                "note": None if revoked else "Token di komputer ini sudah dihapus, tetapi pencabutan di Google "
                        "tidak terkonfirmasi. Cabut manual di myaccount.google.com › Security › Third-party access."}

    def _purge_data(self) -> None:
        with self.db.session() as s:
            s.execute(delete(YouTubeCache))
            s.execute(delete(YouTubeSnapshot))

    def enforce_retention(self) -> bool:
        """Data berizin harus diverifikasi ulang tiap 30 hari; bila terlewat, data dihapus (akun tetap tersambung)."""
        account = self.account()
        if not account:
            return False
        verified = datetime.fromisoformat(account["verified_at"])
        if utcnow() - verified <= timedelta(days=REVERIFY_DAYS):
            return False
        with self.db.session() as s:
            has_data = s.scalar(select(YouTubeCache.key).limit(1)) or s.scalar(select(YouTubeSnapshot.day).limit(1))
        if not has_data:
            return False
        self._purge_data()
        log.info("youtube_data_purged_unverified")
        return True

    # ── panggilan API ─────────────────────────────────────────────────────
    def _require(self) -> ClientConfig:
        client = self.client()
        if client is None and self.account() is not None:
            raise NeedsReauth("File client OAuth tidak ada di komputer ini. Putuskan akun di Settings › YouTube, "
                              "impor file client, lalu hubungkan ulang.")
        if client is None or (self.account() is None and self.store.get(TOKEN_NAME) is None):
            raise YouTubeError("YouTube belum terhubung. Buka Settings › YouTube.", status_code=409,
                               code="not_connected")
        return client

    async def _api_get(self, client: ClientConfig, url: str, params: dict[str, str], *, analytics: bool = False,
                       search: bool = False) -> dict[str, Any]:
        for attempt in (1, 2):
            token = await self._access_token(client)
            if analytics:
                self.quota.count_analytics()
            else:
                self.quota.charge(units=1, search=search)
            try:
                async with self._http() as http:
                    response = await http.get(url, params=params, headers={"Authorization": f"Bearer {token}"})
            except CostGuardBlocked as exc:
                raise YouTubeError(str(exc)) from exc
            except httpx.HTTPError as exc:
                raise YouTubeError(f"YouTube tidak dapat dihubungi ({type(exc).__name__}).", status_code=502,
                                   code="unreachable") from exc
            if response.status_code == 401 and attempt == 1:
                self._access = None
                continue
            break
        try:
            data = response.json()
        except ValueError:
            data = {}
        if response.status_code == 200 and isinstance(data, dict):
            return data
        error = data.get("error", {}) if isinstance(data, dict) else {}
        if not isinstance(error, dict):
            error = {}
        reasons = [e.get("reason") for e in error.get("errors", []) if isinstance(e, dict)]
        message = str(error.get("message", ""))[:200]
        if response.status_code == 401:
            raise NeedsReauth()
        if response.status_code == 403 and any(r in ("quotaExceeded", "dailyLimitExceeded") for r in reasons):
            raise QuotaExceeded("YouTube melaporkan kuota project ini habis untuk hari ini.")
        raise YouTubeError(f"YouTube menolak permintaan ({response.status_code}): {message or 'tanpa keterangan'}")

    async def _fetch_channel(self, client: ClientConfig) -> dict[str, Any]:
        data = await self._api_get(client, f"{self.ep.data_api}/channels",
                                   {"part": "snippet,statistics,contentDetails", "mine": "true"})
        items = data.get("items") or []
        if not items:
            raise YouTubeError("Akun Google ini tidak punya channel YouTube. Pilih akun yang memiliki channel.")
        item = items[0]
        snippet, stats = item.get("snippet", {}), item.get("statistics", {})
        return {
            "id": item.get("id", ""), "title": snippet.get("title", ""), "custom_url": snippet.get("customUrl"),
            "published_at": snippet.get("publishedAt"), "country": snippet.get("country"),
            "view_count": _int(stats.get("viewCount")), "subscriber_count": _int(stats.get("subscriberCount")),
            "hidden_subscribers": bool(stats.get("hiddenSubscriberCount")),
            "video_count": _int(stats.get("videoCount")),
            "uploads_playlist": item.get("contentDetails", {}).get("relatedPlaylists", {}).get("uploads"),
        }

    def _store(self, key: str, payload: Any) -> None:
        with self.db.session() as s:
            row = s.get(YouTubeCache, key)
            text = json.dumps(payload, ensure_ascii=False)
            if row is None:
                s.add(YouTubeCache(key=key, payload_json=text, fetched_at=utcnow()))
            else:
                row.payload_json, row.fetched_at = text, utcnow()

    def _store_channel(self, channel: dict[str, Any]) -> None:
        self._store("channel", channel)
        day = date.today().isoformat()
        with self.db.session() as s:
            row = s.get(YouTubeSnapshot, day)
            if row is None:
                row = YouTubeSnapshot(day=day, channel_id=channel["id"], fetched_at=utcnow())
                s.add(row)
            row.channel_id, row.fetched_at = channel["id"], utcnow()
            row.view_count, row.subscriber_count = channel["view_count"], channel["subscriber_count"]
            row.hidden_subscribers, row.video_count = channel["hidden_subscribers"], channel["video_count"]

    def _mark_verified(self, channel: dict[str, Any]) -> None:
        account = self.account()
        if account:
            self._save_account({**account, "title": channel["title"], "custom_url": channel.get("custom_url"),
                                "verified_at": utcnow().isoformat(), "needs_reauth": False})

    async def refresh_channel(self) -> dict[str, Any]:
        client = self._require()
        async with self._lock:
            channel = await self._fetch_channel(client)
            account = self.account()
            if account and account["channel_id"] != channel["id"]:
                raise YouTubeError("Channel yang terhubung berubah. Putuskan lalu hubungkan ulang.", status_code=409)
            self._store_channel(channel)
            self._mark_verified(channel)
        self._changed()
        return channel

    async def refresh_videos(self) -> list[dict[str, Any]]:
        client = self._require()
        channel = self.cached("channel") or await self.refresh_channel()
        uploads = channel["payload"]["uploads_playlist"] if "payload" in channel else channel["uploads_playlist"]
        if not uploads:
            self._store("videos", [])
            return []
        async with self._lock:
            listing = await self._api_get(client, f"{self.ep.data_api}/playlistItems",
                                          {"part": "contentDetails", "playlistId": uploads,
                                           "maxResults": str(RECENT_VIDEOS)})
            ids = [i.get("contentDetails", {}).get("videoId") for i in listing.get("items", [])]
            ids = [i for i in ids if i]
            videos: list[dict[str, Any]] = []
            if ids:
                details = await self._api_get(client, f"{self.ep.data_api}/videos",
                                              {"part": "snippet,statistics,contentDetails,status", "id": ",".join(ids)})
                for item in details.get("items", []):
                    snippet, stats = item.get("snippet", {}), item.get("statistics", {})
                    videos.append({
                        "id": item.get("id"), "title": snippet.get("title", ""),
                        "published_at": snippet.get("publishedAt"),
                        "duration": item.get("contentDetails", {}).get("duration"),
                        "privacy": item.get("status", {}).get("privacyStatus"),
                        "view_count": _int(stats.get("viewCount")), "like_count": _int(stats.get("likeCount")),
                        "comment_count": _int(stats.get("commentCount")),
                    })
            self._store("videos", videos)
        self._changed()
        return videos

    async def api_get(self, path: str, params: dict[str, str], *, search: bool = False) -> dict[str, Any]:
        """GET berizin ke YouTube Data API untuk modul lain (data publik). Kuota dihitung seperti biasa."""
        client = self._require()
        async with self._lock:
            return await self._api_get(client, f"{self.ep.data_api}/{path}", params, search=search)

    async def _report(self, client: ClientConfig, start: date, end: date, *, daily: bool = False,
                      by_video: bool = False) -> dict[str, Any]:
        params = {"ids": "channel==MINE", "startDate": start.isoformat(), "endDate": end.isoformat(),
                  "metrics": VIDEO_METRICS if by_video else ANALYTICS_METRICS}
        if daily:
            params |= {"dimensions": "day", "sort": "day"}
        if by_video:
            params |= {"dimensions": "video", "sort": "-views", "maxResults": "25"}
        data = await self._api_get(client, f"{self.ep.analytics_api}/reports", params, analytics=True)
        headers = [h.get("name") for h in data.get("columnHeaders", [])]
        rows = [dict(zip(headers, row, strict=False)) for row in data.get("rows", []) or []]
        return {"start": start.isoformat(), "end": end.isoformat(), "columns": headers, "rows": rows}

    async def refresh_analytics(self) -> dict[str, Any]:
        client = self._require()
        account = self.account() or {}
        if not account.get("analytics_granted", True):
            note = {"error": "Izin YouTube Analytics tidak diberikan saat menghubungkan. Putuskan lalu hubungkan "
                             "ulang dan centang izin laporan Analytics."}
            self._store("analytics", note)
            return note
        end = date.today() - timedelta(days=1)
        result: dict[str, Any] = {}
        async with self._lock:
            try:
                result["last_28_days"] = await self._report(client, end - timedelta(days=27), end, daily=False)
                result["daily"] = await self._report(client, end - timedelta(days=27), end, daily=True)
                result["last_365_days"] = await self._report(client, end - timedelta(days=364), end, daily=False)
            except NeedsReauth:
                raise
            except YouTubeError as exc:
                result["error"] = exc.message
            if "error" not in result:
                try:
                    result["by_video"] = await self._report(client, end - timedelta(days=27), end, by_video=True)
                except NeedsReauth:
                    raise
                except YouTubeError as exc:
                    result["by_video_error"] = exc.message
            self._store("analytics", result)
        self._changed()
        return result

    async def refresh_all(self) -> dict[str, Any]:
        await self.refresh_channel()
        await self.refresh_videos()
        await self.refresh_analytics()
        return self.data()

    # ── baca data tersimpan ───────────────────────────────────────────────
    def cached(self, key: str) -> dict[str, Any] | None:
        with self.db.session() as s:
            row = s.get(YouTubeCache, key)
            if row is None:
                return None
            return {"payload": json.loads(row.payload_json), "fetched_at": row.fetched_at.isoformat()}

    def history(self, limit: int = 400) -> list[dict[str, Any]]:
        with self.db.session() as s:
            rows = s.scalars(select(YouTubeSnapshot).order_by(YouTubeSnapshot.day.desc()).limit(limit)).all()
            return [{"day": r.day, "fetched_at": r.fetched_at.isoformat(), "view_count": r.view_count,
                     "subscriber_count": r.subscriber_count, "hidden_subscribers": r.hidden_subscribers,
                     "video_count": r.video_count} for r in rows]

    def data(self) -> dict[str, Any]:
        purged = self.enforce_retention()
        account = self.account()
        return {
            "connected": account is not None, "account": account, "test_endpoint": self.ep.is_test,
            "source": ("SERVER UJI (bukan YouTube)" if self.ep.is_test
                       else "YouTube Data API v3 & YouTube Analytics API"),
            "purged_unverified": purged,
            "channel": self.cached("channel"), "videos": self.cached("videos"), "analytics": self.cached("analytics"),
            "history": self.history(), "ypp": ypp_requirements(), "quota": self.quota.status(),
        }
