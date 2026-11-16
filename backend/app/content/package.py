"""Paket produksi (zoi.paket/v1): naskah ZOI → satu file JSON untuk dibawa ke laptop.

Bentuk `beats` ({k: nama, n: narasi, v: catatan visual}) sengaja sama dengan struktur cerita
Blueprint Studio, sehingga tombol "Muat paket ZOI" (Phase 7) bisa membacanya langsung.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any


class PackageError(Exception):
    pass


def build_package(item: dict[str, Any]) -> dict[str, Any]:
    if item.get("kind") != "script":
        raise PackageError("Paket produksi hanya bisa dibuat dari naskah.")
    payload = item.get("payload") or {}
    request = item.get("request") or {}
    beats: list[dict[str, str]] = []
    hook = str(payload.get("hook") or "").strip()
    if hook:
        beats.append({"k": "Hook", "n": hook, "v": ""})
    for part in payload.get("bagian") or []:
        beats.append({"k": str(part.get("judul") or f"Beat {len(beats) + 1}"),
                      "n": str(part.get("narasi") or ""),
                      "v": str(part.get("visual") or "")})
    cta = str(payload.get("cta") or "").strip()
    if cta:
        beats.append({"k": "Penutup", "n": cta, "v": ""})
    if not beats:
        raise PackageError("Naskah ini kosong — tidak ada yang bisa dipaketkan.")
    is_shorts = request.get("format") == "shorts"
    return {
        "format": "zoi.paket/v1",
        "dibuat": datetime.now(UTC).isoformat(),
        "sumber": f"ZOI YouTube Intelligence — naskah {item.get('id', '')}",
        "mock": bool(item.get("is_mock")),
        "judul": str(payload.get("judul") or item.get("title") or ""),
        "topik": str(item.get("title") or ""),
        "durasi": str(request.get("durasi") or ("60 detik" if is_shorts else "")),
        "bahasa": "Indonesia",
        "rasio": "9:16" if is_shorts else "16:9",
        "beats": beats,
        "naskah_tts": "\n\n".join(b["n"] for b in beats if b["n"].strip()),
    }


def package_filename(package: dict[str, Any]) -> str:
    slug = "".join(c if c.isalnum() else "-" for c in package["judul"].lower()).strip("-")[:40] or "naskah"
    while "--" in slug:
        slug = slug.replace("--", "-")
    return f"paket-zoi-{slug}.json"


def package_bytes(package: dict[str, Any]) -> bytes:
    return json.dumps(package, indent=2, ensure_ascii=False).encode("utf-8")
