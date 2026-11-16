"""Jadwal sederhana dalam WIB (Asia/Jakarta): harian atau mingguan pada jam:menit tertentu."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field

WIB = ZoneInfo("Asia/Jakarta")
WEEKDAYS = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]


class Schedule(BaseModel):
    model_config = ConfigDict(extra="forbid")
    frequency: Literal["daily", "weekly"] = "daily"
    hour: int = Field(default=7, ge=0, le=23)
    minute: int = Field(default=0, ge=0, le=59)
    weekday: int = Field(default=0, ge=0, le=6)  # 0 = Senin

    def describe(self) -> str:
        at = f"{self.hour:02d}.{self.minute:02d} WIB"
        return f"Setiap hari {at}" if self.frequency == "daily" else f"Setiap {WEEKDAYS[self.weekday]} {at}"

    def next_after(self, moment: datetime) -> datetime:
        """Waktu jadwal berikutnya SETELAH `moment` (UTC aware), dikembalikan dalam UTC."""
        local = moment.astimezone(WIB)
        candidate = local.replace(hour=self.hour, minute=self.minute, second=0, microsecond=0)
        if self.frequency == "weekly":
            candidate += timedelta(days=(self.weekday - candidate.weekday()) % 7)
            if candidate <= local:
                candidate += timedelta(days=7)
        elif candidate <= local:
            candidate += timedelta(days=1)
        return candidate.astimezone(UTC)
