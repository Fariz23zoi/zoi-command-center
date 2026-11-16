"""Katalog model kandidat (data statis di repo — ZOI tidak mengambil daftar model dari internet)."""

from __future__ import annotations

import json
from functools import cache
from pathlib import Path
from typing import Any

PATH = Path(__file__).resolve().parent / "catalog.json"


@cache
def load_catalog() -> dict[str, Any]:
    return json.loads(PATH.read_text(encoding="utf-8"))
