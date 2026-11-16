"""Adapter Blueprint Studio — Phase 1: deteksi read-only (membaca maksimal 8 KB pertama, tidak menulis)."""

from __future__ import annotations

from pathlib import Path

from app.integrations.base import AdapterStatus

MARKER = "<title>Blueprint Studio</title>"
READ_LIMIT = 8192


class BlueprintAdapter:
    name = "blueprint_studio"

    def __init__(self, blueprint_file: Path | None) -> None:
        self.blueprint_file = blueprint_file

    def detect(self) -> AdapterStatus:
        status = AdapterStatus(name=self.name, configured=self.blueprint_file is not None, found=False)
        if self.blueprint_file is None:
            status.problems.append("ZOI_BLUEPRINT_FILE belum diisi.")
            return status
        path = self.blueprint_file
        if not path.is_file():
            status.problems.append(f"File tidak ditemukan: {path}")
            return status
        if path.suffix.lower() != ".html":
            status.problems.append("File Blueprint Studio harus berekstensi .html")
        with path.open("rb") as fh:  # mode baca saja
            head = fh.read(READ_LIMIT).decode("utf-8", errors="replace")
        status.details["size_bytes"] = path.stat().st_size
        status.details["title_matches"] = MARKER in head
        if MARKER not in head:
            status.problems.append("Judul halaman bukan 'Blueprint Studio' — pastikan file yang benar.")
        status.found = path.suffix.lower() == ".html" and MARKER in head
        return status
