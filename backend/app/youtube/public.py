"""Data PUBLIK YouTube: channel pantauan, Trending resmi Indonesia, dan pencarian.

Kepatuhan (YouTube API Developer Policies, dicek 14–15 Nov 2026):
- Bukan data berizin → disimpan paling lama 30 hari lalu dihapus otomatis (III.E.4.d).
- Ditampilkan apa adanya dalam urutan dari YouTube; ZOI tidak membuat skor, peringkat, atau metrik turunan
  (III.E.4.h) dan tidak menggabungkan statistik antar-channel (III.E.2.b).
- Semua data diambil lewat API resmi dengan izin OAuth pengguna — tidak ada scraping.
- Saat akun diputuskan, data publik dan daftar pantauan ikut dihapus.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import timedelta
from typing import Any

from sqlalchemy import delete, select

from app.core.events import EventBus
from app.db.base import utcnow
from app.db.models import YouTubePublicCache, YouTubeWatch
from app.db.session import Database
from app.logging_setup import get_logger
from app.youtube.errors import YouTubeError
from app.youtube.service import YouTubeService, _int

log = get_logger("youtube.public")

RETENTION_DAYS = 30
MAX_WATCHLIST = 20
MAX_SEARCHES = 20
REGION = "ID"
LIST_SIZE = 25
COMPETITOR_VIDEOS = 10
CHANNEL_ID = re.compile(r"UC[A-Za-z0-9_-]{22}")
HANDLE = re.compile(r"@[A-Za-z0-9._-]{3,30}")


def parse_channel_ref(text: str) -> tuple[str, str]:
    """ID channel (UC…), handle (@nama), atau URL youtube.com yang memuat salah satunya."""
    text = text.strip()
    if len(text) > 300:
        raise YouTubeError("Isian terlalu panjang.")
    if match := CHANNEL_ID.search(text):
        return "id", match.group(0)
    if match := HANDLE.search(text):
        return "forHandle", match.group(0)
    raise YouTubeError("Tulis handle channel (mis. @namachannel), ID channel (UC…), atau tautan channel YouTube.")


def _video(item: dict[str, Any]) -> dict[str, Any]:
    snippet, stats = item.get("snippet", {}), item.get("statistics", {})
    video_id = item.get("id")
    if isinstance(video_id, dict):  # bentuk search.list
        video_id = video_id.get("videoId")
    return {"id": video_id, "title": snippet.get("title", ""), "channel_title": snippet.get("channelTitle", ""),
            "channel_id": snippet.get("channelId"), "published_at": snippet.get("publishedAt"),
            "category_id": snippet.get("categoryId"), "duration": item.get("contentDetails", {}).get("duration"),
            "view_count": _int(stats.get("viewCount")), "like_count": _int(stats.get("likeCount")),
            "comment_count": _int(stats.get("commentCount"))}


def _channel(item: dict[str, Any]) -> dict[str, Any]:
    snippet, stats = item.get("snippet", {}), item.get("statistics", {})
    return {"id": item.get("id", ""), "title": snippet.get("title", ""), "custom_url": snippet.get("customUrl"),
            "published_at": snippet.get("publishedAt"), "country": snippet.get("country"),
            "view_count": _int(stats.get("viewCount")), "subscriber_count": _int(stats.get("subscriberCount")),
            "hidden_subscribers": bool(stats.get("hiddenSubscriberCount")),
            "video_count": _int(stats.get("videoCount")),
            "uploads_playlist": item.get("contentDetails", {}).get("relatedPlaylists", {}).get("uploads")}


class PublicDataService:
    def __init__(self, *, db: Database, bus: EventBus, youtube: YouTubeService) -> None:
        self.db = db
        self.bus = bus
        self.yt = youtube
        youtube.purge_hooks.append(self.purge_all)

    # ── penyimpanan ≤30 hari ──────────────────────────────────────────────
    def purge_expired(self) -> int:
        cutoff = utcnow() - timedelta(days=RETENTION_DAYS)
        with self.db.session() as s:
            removed = s.execute(delete(YouTubePublicCache).where(YouTubePublicCache.fetched_at < cutoff)).rowcount
        if removed:
            log.info("youtube_public_purged", rows=removed)
        return removed or 0

    def purge_all(self) -> None:
        with self.db.session() as s:
            s.execute(delete(YouTubePublicCache))
            s.execute(delete(YouTubeWatch))

    def put(self, key: str, kind: str, payload: Any) -> None:
        with self.db.session() as s:
            row = s.get(YouTubePublicCache, key)
            text = json.dumps(payload, ensure_ascii=False)
            if row is None:
                s.add(YouTubePublicCache(key=key, kind=kind, payload_json=text, fetched_at=utcnow()))
            else:
                row.payload_json, row.fetched_at = text, utcnow()

    @staticmethod
    def _entry(row: YouTubePublicCache) -> dict[str, Any]:
        return {"key": row.key, "payload": json.loads(row.payload_json), "fetched_at": row.fetched_at.isoformat(),
                "expires_at": (row.fetched_at + timedelta(days=RETENTION_DAYS)).isoformat()}

    def get(self, key: str) -> dict[str, Any] | None:
        self.purge_expired()
        with self.db.session() as s:
            row = s.get(YouTubePublicCache, key)
            return self._entry(row) if row else None

    def entries(self, kind: str) -> list[dict[str, Any]]:
        self.purge_expired()
        with self.db.session() as s:
            rows = s.scalars(select(YouTubePublicCache).where(YouTubePublicCache.kind == kind)
                             .order_by(YouTubePublicCache.fetched_at.desc())).all()
            return [self._entry(r) for r in rows]

    def _drop(self, *keys: str) -> None:
        with self.db.session() as s:
            s.execute(delete(YouTubePublicCache).where(YouTubePublicCache.key.in_(keys)))

    def _changed(self) -> None:
        self.bus.publish("youtube.updated", {})

    def info(self) -> dict[str, Any]:
        return {"retention_days": RETENTION_DAYS, "region": REGION, "test_endpoint": self.yt.ep.is_test,
                "connected": self.yt.account() is not None,
                "source": "SERVER UJI (bukan YouTube)" if self.yt.ep.is_test else "YouTube Data API v3 (data publik)",
                "quota": self.yt.quota.status()}

    # ── channel pantauan ──────────────────────────────────────────────────
    def competitors(self) -> dict[str, Any]:
        self.purge_expired()
        with self.db.session() as s:
            watch = [(w.channel_id, w.note, w.added_at.isoformat())
                     for w in s.scalars(select(YouTubeWatch).order_by(YouTubeWatch.added_at)).all()]
        items = [{"channel_id": cid, "note": note, "added_at": added, "data": self.get(f"competitor:{cid}")}
                 for cid, note, added in watch]
        return {**self.info(), "max": MAX_WATCHLIST, "items": items}

    async def add_competitor(self, ref: str, note: str = "") -> dict[str, Any]:
        param, value = parse_channel_ref(ref)
        with self.db.session() as s:
            count = len(s.scalars(select(YouTubeWatch.channel_id)).all())
        if count >= MAX_WATCHLIST:
            raise YouTubeError(f"Daftar pantauan penuh (maksimal {MAX_WATCHLIST} channel). Hapus satu dulu.",
                               status_code=409)
        data = await self.yt.api_get("channels", {"part": "snippet,statistics,contentDetails", param: value})
        found = data.get("items") or []
        if not found:
            raise YouTubeError("YouTube tidak menemukan channel itu. Periksa handle atau ID-nya.", status_code=404)
        channel = _channel(found[0])
        with self.db.session() as s:
            if s.get(YouTubeWatch, channel["id"]) is None:
                s.add(YouTubeWatch(channel_id=channel["id"], note=note.strip()[:200]))
        self.put(f"competitor:{channel['id']}", "competitor", {"channel": channel, "videos": None})
        self._changed()
        return self.competitors()

    async def refresh_competitor(self, channel_id: str) -> dict[str, Any]:
        with self.db.session() as s:
            if s.get(YouTubeWatch, channel_id) is None:
                raise YouTubeError("Channel itu tidak ada di daftar pantauan.", status_code=404)
        data = await self.yt.api_get("channels", {"part": "snippet,statistics,contentDetails", "id": channel_id})
        found = data.get("items") or []
        if not found:
            raise YouTubeError("YouTube tidak lagi mengembalikan channel itu (mungkin dihapus atau disembunyikan).",
                               status_code=404)
        channel = _channel(found[0])
        videos: list[dict[str, Any]] = []
        if channel["uploads_playlist"]:
            listing = await self.yt.api_get("playlistItems", {"part": "contentDetails",
                                                              "playlistId": channel["uploads_playlist"],
                                                              "maxResults": str(COMPETITOR_VIDEOS)})
            ids = [i.get("contentDetails", {}).get("videoId") for i in listing.get("items", [])]
            ids = [i for i in ids if i]
            if ids:
                details = await self.yt.api_get("videos", {"part": "snippet,statistics,contentDetails",
                                                           "id": ",".join(ids)})
                videos = [_video(i) for i in details.get("items", [])]
        self.put(f"competitor:{channel_id}", "competitor", {"channel": channel, "videos": videos})
        self._changed()
        return self.competitors()

    def remove_competitor(self, channel_id: str) -> dict[str, Any]:
        with self.db.session() as s:
            row = s.get(YouTubeWatch, channel_id)
            if row is None:
                raise YouTubeError("Channel itu tidak ada di daftar pantauan.", status_code=404)
            s.delete(row)
        self._drop(f"competitor:{channel_id}")
        self._changed()
        return self.competitors()

    # ── Trending resmi & pencarian ────────────────────────────────────────
    async def refresh_categories(self) -> dict[str, Any]:
        data = await self.yt.api_get("videoCategories", {"part": "snippet", "regionCode": REGION, "hl": "id"})
        items = [{"id": i.get("id"), "title": i.get("snippet", {}).get("title", "")}
                 for i in data.get("items", []) if i.get("snippet", {}).get("assignable")]
        self.put(f"categories:{REGION}", "categories", items)
        return self.get(f"categories:{REGION}") or {}

    async def refresh_trending(self, category_id: str | None = None) -> dict[str, Any]:
        if category_id is not None and not re.fullmatch(r"\d{1,4}", category_id):
            raise YouTubeError("Kategori tidak valid.")
        if self.get(f"categories:{REGION}") is None:
            await self.refresh_categories()
        params = {"part": "snippet,statistics,contentDetails", "chart": "mostPopular", "regionCode": REGION,
                  "maxResults": str(LIST_SIZE)}
        if category_id:
            params["videoCategoryId"] = category_id
        data = await self.yt.api_get("videos", params)
        key = f"trending:{REGION}:{category_id or 'all'}"
        self.put(key, "trending", {"category_id": category_id, "region": REGION,
                                   "items": [_video(i) for i in data.get("items", [])]})
        self._changed()
        return self.viral()

    async def search(self, query: str) -> dict[str, Any]:
        query = " ".join(query.split())
        if not 2 <= len(query) <= 100:
            raise YouTubeError("Kata kunci harus 2–100 karakter.")
        data = await self.yt.api_get("search", {"part": "snippet", "type": "video", "q": query, "regionCode": REGION,
                                                "relevanceLanguage": "id", "maxResults": str(LIST_SIZE)},
                                     search=True)
        key = "search:" + hashlib.sha256(query.lower().encode()).hexdigest()[:16]
        self.put(key, "search", {"query": query, "items": [_video(i) for i in data.get("items", [])]})
        stale = [e["key"] for e in self.entries("search")[MAX_SEARCHES:]]
        if stale:
            self._drop(*stale, *[f"themes:{k}" for k in stale])
        self._changed()
        return self.viral()

    def remove_list(self, key: str) -> dict[str, Any]:
        if not key.startswith(("trending:", "search:")):
            raise YouTubeError("Daftar tidak dikenal.", status_code=404)
        self._drop(key, f"themes:{key}")
        self._changed()
        return self.viral()

    def viral(self) -> dict[str, Any]:
        return {**self.info(), "categories": self.get(f"categories:{REGION}"),
                "trending": self.entries("trending"), "searches": self.entries("search"),
                "themes": self.entries("themes")}

    def titles(self, key: str) -> list[str]:
        """Judul dari satu daftar tersimpan — satu-satunya bagian yang dibaca AI lokal untuk rangkuman tema."""
        if not key.startswith(("trending:", "search:")):
            raise YouTubeError("Daftar tidak dikenal.", status_code=404)
        entry = self.get(key)
        if entry is None:
            raise YouTubeError("Daftar itu sudah tidak tersimpan. Ambil ulang dulu.", status_code=404)
        return [v["title"] for v in entry["payload"]["items"] if v.get("title")]
