"""Antarmuka adapter aplikasi lama. Phase 1: hanya deteksi READ-ONLY (stat + baca, tidak pernah menulis)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol


@dataclass
class AdapterStatus:
    name: str
    configured: bool
    found: bool
    checked_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    details: dict[str, Any] = field(default_factory=dict)
    problems: list[str] = field(default_factory=list)
    integration_phase: int = 7

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ExternalAppAdapter(Protocol):
    name: str

    def detect(self) -> AdapterStatus: ...
