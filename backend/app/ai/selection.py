"""Model aktif. Urutan: pilihan pengguna di UI (database, ikut ekspor) → ZOI_OLLAMA_MODEL (.env).

Model selalu divalidasi ulang terhadap Ollama saat dipilih; health() menilai ulang setiap kali status diminta.
"""

from __future__ import annotations

import json
from typing import Literal

from app.db.models import AppMeta
from app.db.session import Database

KEY = "ai_model"
Source = Literal["ui", "env", "none"]


def stored_model(db: Database) -> str | None:
    with db.session() as s:
        row = s.get(AppMeta, KEY)
        if row is None:
            return None
        value = json.loads(row.value_json).get("model")
        return value if isinstance(value, str) and value else None


def save_model(db: Database, model: str | None) -> None:
    with db.session() as s:
        row = s.get(AppMeta, KEY)
        if model is None:
            if row is not None:
                s.delete(row)
            return
        payload = json.dumps({"model": model})
        if row is None:
            s.add(AppMeta(key=KEY, value_json=payload))
        else:
            row.value_json = payload


def resolve(db: Database, env_model: str | None) -> tuple[str | None, Source]:
    chosen = stored_model(db)
    if chosen:
        return chosen, "ui"
    if env_model:
        return env_model, "env"
    return None, "none"
