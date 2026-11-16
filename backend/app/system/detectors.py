"""Deteksi sistem NYATA (tanpa menebak). Alat yang tidak ditemukan dilaporkan apa adanya."""

from __future__ import annotations

import platform
import re
import shutil
import socket
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import psutil

TOOLS: dict[str, list[str]] = {
    "node": ["node", "--version"],
    "git": ["git", "--version"],
    "ffmpeg": ["ffmpeg", "-version"],
    "ollama": ["ollama", "--version"],
}
VERSION_RE = re.compile(r"(\d+\.\d+(?:\.\d+)?)")


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def detect_tool(name: str, timeout_s: float = 5.0) -> dict[str, Any]:
    args = TOOLS[name]
    path = shutil.which(args[0])
    if path is None:
        return {"name": name, "found": False, "version": None, "path": None}
    try:
        out = subprocess.run([path, *args[1:]], capture_output=True, text=True, timeout=timeout_s, check=False)
        text = (out.stdout or out.stderr or "").strip().splitlines()
        first = text[0] if text else ""
        match = VERSION_RE.search(first)
        version = match.group(1) if match else (first[:60] or None)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"name": name, "found": True, "version": None, "path": path, "error": str(exc)[:200]}
    return {"name": name, "found": True, "version": version, "path": path}


def python_info() -> dict[str, Any]:
    return {
        "version": platform.python_version(),
        "implementation": platform.python_implementation(),
        "executable": sys.executable,
        "supported": sys.version_info >= (3, 12),
    }


def os_info() -> dict[str, Any]:
    return {"system": platform.system(), "release": platform.release(), "version": platform.version(),
            "machine": platform.machine()}


def resources(data_dir: Path) -> dict[str, Any]:
    vm = psutil.virtual_memory()
    probe = data_dir if data_dir.exists() else data_dir.anchor or Path.cwd()
    disk = psutil.disk_usage(str(probe))
    return {
        "cpu": {"physical_cores": psutil.cpu_count(logical=False), "logical_cores": psutil.cpu_count(),
                "model": platform.processor() or None},
        "memory": {"total_bytes": vm.total, "available_bytes": vm.available},
        "disk": {"path": str(probe), "total_bytes": disk.total, "free_bytes": disk.free},
        "gpu": detect_gpu(),
    }


def detect_gpu() -> dict[str, Any]:
    smi = shutil.which("nvidia-smi")
    if smi:
        try:
            out = subprocess.run([smi, "--query-gpu=name,memory.total", "--format=csv,noheader"],
                                 capture_output=True, text=True, timeout=5, check=False)
            if out.returncode == 0 and out.stdout.strip():
                return {"detected": True, "source": "nvidia-smi", "devices": out.stdout.strip().splitlines()}
        except (OSError, subprocess.TimeoutExpired):
            pass
    return {"detected": False, "source": None,
            "note": "Hanya GPU NVIDIA yang dideteksi di Phase 1. Deteksi WebGL dilakukan browser di Phase 2."}


def port_available(host: str, port: int) -> bool:
    """Apakah ZOI bisa membuka port ini. Meniru perilaku uvicorn agar tidak salah lapor."""
    with socket.socket(socket.AF_INET6 if ":" in host else socket.AF_INET, socket.SOCK_STREAM) as sock:
        if sys.platform != "win32":
            # Seperti uvicorn: port dalam status TIME_WAIT (baru saja ditutup) tetap boleh dipakai.
            # Di Windows SO_REUSEADDR berarti "boleh merebut port yang sedang dipakai" — sengaja tidak dipakai.
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
        except OSError:
            return False
    return True


def port_owner(port: int) -> str | None:
    """Nama proses yang memakai port (best effort; di Windows kadang butuh hak Administrator)."""
    try:
        for conn in psutil.net_connections(kind="tcp"):
            if conn.laddr and conn.laddr.port == port and conn.status == psutil.CONN_LISTEN and conn.pid:
                try:
                    return f"{psutil.Process(conn.pid).name()} (PID {conn.pid})"
                except psutil.Error:
                    return f"PID {conn.pid}"
    except (psutil.AccessDenied, PermissionError):
        return None
    return None
