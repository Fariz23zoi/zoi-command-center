"""Adapter ZOI AI CLIPPER — deteksi read-only + peluncur.

Aturan: TIDAK meng-import modul CLIPPER dan TIDAK mengubah file repository-nya.
Atas keputusan pemilik (17 Nov 2026), ZOI boleh MENYALAKAN web app CLIPPER apa adanya (`python app.py`, port 5000)
sebagai proses terpisah dengan Python milik CLIPPER. ZOI tidak memanggil fitur unduh/olah videonya.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
from pathlib import Path

from app.core.errors import ZoiError
from app.integrations.base import AdapterStatus

EXPECTED_ENTRIES = {"app.py": "file", "main.py": "file", "shorts_generator": "dir", "LICENSE": "file"}


class ClipperAdapter:
    name = "zoi_ai_clipper"

    def __init__(self, clipper_dir: Path | None, clipper_python: Path | None) -> None:
        self.clipper_dir = clipper_dir
        self.clipper_python = clipper_python
        self.port = 5000  # tetap di app.py CLIPPER
        self._proc: subprocess.Popen[bytes] | None = None

    # ── peluncur ──────────────────────────────────────────────────────────
    def _python(self) -> Path | None:
        if self.clipper_python is not None:
            return self.clipper_python if self.clipper_python.is_file() else None
        if self.clipper_dir is None:
            return None
        for rel in (".venv/Scripts/python.exe", "venv/Scripts/python.exe", ".venv/bin/python", "venv/bin/python"):
            if (self.clipper_dir / rel).is_file():
                return self.clipper_dir / rel
        return None

    def running(self) -> bool:
        with socket.socket() as sock:
            sock.settimeout(0.3)
            return sock.connect_ex(("127.0.0.1", self.port)) == 0

    def launch_status(self) -> dict[str, object]:
        found = self.detect().found
        python = self._python()
        reason = None
        if not found:
            reason = "CLIPPER belum ditemukan. Isi ZOI_CLIPPER_DIR di file .env dengan folder zoi-ai-clipper."
        elif python is None:
            reason = ("Python milik CLIPPER tidak ditemukan. Isi ZOI_CLIPPER_PYTHON di .env "
                      "(mis. ...\\zoi-ai-clipper\\.venv\\Scripts\\python.exe).")
        return {"running": self.running(), "port": self.port, "can_start": reason is None, "reason": reason,
                "started_by_zoi": self._proc is not None and self._proc.poll() is None}

    def start(self) -> dict[str, object]:
        status = self.launch_status()
        if status["running"]:
            return status
        if not status["can_start"]:
            raise ZoiError(str(status["reason"]), status_code=409, code="clipper_unavailable")
        flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0  # type: ignore[attr-defined]
        # CLIPPER juga membaca variabel ZOI_* (ZOI_PORT, ZOI_HOST, ...). Jangan wariskan milik ZOI; paksa port 5000.
        env = {k: v for k, v in os.environ.items() if not k.upper().startswith("ZOI_")}
        env["ZOI_PORT"] = str(self.port)
        self._proc = subprocess.Popen(  # noqa: S603 — path tetap dari .env, tanpa argumen dari pengguna
            [str(self._python()), "app.py"], cwd=str(self.clipper_dir), stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=flags, env=env)
        return self.launch_status()

    def stop(self) -> dict[str, object]:
        """Hanya menghentikan proses yang dinyalakan ZOI; CLIPPER yang kamu jalankan sendiri tidak disentuh."""
        if self._proc is not None and self._proc.poll() is None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._proc.kill()
        self._proc = None
        return self.launch_status()

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
