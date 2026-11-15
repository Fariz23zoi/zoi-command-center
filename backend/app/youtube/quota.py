"""Pencatat & pembatas kuota YouTube Data API. Hitungan ini milik ZOI (bukan angka dari YouTube).

Fakta resmi (dicek 15 Nov 2026): 10.000 unit/hari per project; search.list punya ember sendiri, 100 panggilan/hari;
hampir semua metode baca = 1 unit, reset tengah malam waktu Pasifik. ZOI berhenti di 90% agar tidak pernah
menyentuh batas (project yang sama bisa dipakai alat lain).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from app.db.models import YouTubeQuota
from app.db.session import Database
from app.youtube.errors import QuotaExceeded

PACIFIC = ZoneInfo("America/Los_Angeles")
DAILY_UNITS = 10_000
DAILY_SEARCH_CALLS = 100
SAFETY = 0.9
UNIT_LIMIT = int(DAILY_UNITS * SAFETY)
SEARCH_LIMIT = int(DAILY_SEARCH_CALLS * SAFETY)


def quota_day(now: datetime | None = None) -> str:
    return (now or datetime.now(UTC)).astimezone(PACIFIC).date().isoformat()


def next_reset(now: datetime | None = None) -> datetime:
    local = (now or datetime.now(UTC)).astimezone(PACIFIC)
    midnight = (local + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return midnight.astimezone(UTC)


class QuotaTracker:
    def __init__(self, db: Database) -> None:
        self.db = db

    def _row(self, s: Any) -> YouTubeQuota:
        day = quota_day()
        row = s.get(YouTubeQuota, day)
        if row is None:
            row = YouTubeQuota(day=day, units=0, search_calls=0, analytics_calls=0)
            s.add(row)
        return row

    def charge(self, *, units: int = 1, search: bool = False) -> None:
        """Dipanggil SEBELUM permintaan dikirim. Menolak bila melewati batas aman."""
        with self.db.session() as s:
            row = self._row(s)
            if search:  # search.list punya ember kuota sendiri; tidak memotong unit umum
                if row.search_calls + 1 > SEARCH_LIMIT:
                    raise QuotaExceeded(f"Batas aman pencarian YouTube hari ini tercapai "
                                        f"({row.search_calls}/{SEARCH_LIMIT} panggilan). "
                                        "Kuota direset tengah malam waktu Pasifik.")
                row.search_calls += 1
                return
            if row.units + units > UNIT_LIMIT:
                raise QuotaExceeded(f"Batas aman kuota YouTube hari ini tercapai ({row.units}/{UNIT_LIMIT} unit). "
                                    "Kuota direset tengah malam waktu Pasifik.")
            row.units += units

    def count_analytics(self) -> None:
        with self.db.session() as s:
            self._row(s).analytics_calls += 1

    def status(self) -> dict[str, Any]:
        with self.db.session() as s:
            row = s.get(YouTubeQuota, quota_day())
            used, search, analytics = (row.units, row.search_calls, row.analytics_calls) if row else (0, 0, 0)
        return {"source": "hitungan ZOI sendiri atas panggilan yang dikirim dari aplikasi ini",
                "day": quota_day(), "units_used": used, "unit_limit": UNIT_LIMIT, "units_official": DAILY_UNITS,
                "search_used": search, "search_limit": SEARCH_LIMIT, "search_official": DAILY_SEARCH_CALLS,
                "analytics_calls": analytics, "resets_at": next_reset().isoformat()}
