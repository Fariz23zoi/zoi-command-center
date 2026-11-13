"""Adapter ZOI AI CLIPPER — Phase 1: deteksi read-only.

Aturan: TIDAK meng-import modul CLIPPER, TIDAK menjalankan, TIDAK menulis apa pun di foldernya.
Pemanggilan sebagai subprocess (memakai Python milik CLIPPER sendiri) baru dibuat di Phase 7.
"""

from __future__ import annotations

from pathlib import Path

from app.integrations.base import AdapterStatus

EXPECTED_ENTRIES = {"app.py": "file", "main.py": "file", "shorts_generator": "dir", "LICENSE": "file"}


class ClipperAdapter:
    name = "zoi_ai_clipper"

    def __init__(self, clipper_dir: Path | None, clipper_python: Path | None) -> None:
        self.clipper_dir = clipper_dir
        self.clipper_python = clipper_python

    def detect(self) -> AdapterStatus:
        status = AdapterStatus(name=self.name, configured=self.clipper_dir is not None, found=False)
        if self.clipper_dir is None:
            status.problems.append("ZOI_CLIPPER_DIR belum diisi.")
            return status
        root = self.clipper_dir
        if not root.is_dir():
            status.problems.append(f"Folder tidak ditemukan: {root}")
            return status
        entries = {}
        for name, kind in EXPECTED_ENTRIES.items():
            path = root / name
            ok = path.is_dir() if kind == "dir" else path.is_file()
            entries[name] = ok
            if not ok:
                status.problems.append(f"Tidak ditemukan di folder CLIPPER: {name}")
        status.details["entries"] = entries
        status.details["python_configured"] = self.clipper_python is not None
        if self.clipper_python is not None:
            status.details["python_found"] = self.clipper_python.is_file()
            if not self.clipper_python.is_file():
                status.problems.append(f"Interpreter CLIPPER tidak ditemukan: {self.clipper_python}")
        status.found = all(entries[n] for n in ("app.py", "shorts_generator"))
        return status
