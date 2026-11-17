"""Update ZOI dari GitHub Releases (ADR 0017).

- Cek versi terbaru (otomatis tiap 24 jam di mode local, atau manual). Hanya membaca API publik GitHub.
- Pasang hanya setelah pengguna menekan tombol: unduh ZIP rilis + file .sha256 dari rilis yang SAMA, cocokkan hash,
  ekstrak ke folder saudara `zoi-command-center-<versi>` (folder lama TIDAK diubah → bisa kembali), lalu jalankan
  `deploy/windows/apply-update.ps1` dari folder baru di jendela terpisah. Skrip itu menghentikan ZOI lama,
  menyalin .env & data, memasang paket, dan menyalakan versi baru (atau menyalakan lagi versi lama bila gagal).
"""

from __future__ import annotations

import asyncio
import hashlib
import re
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime, timedelta
from pathlib import Path, PurePosixPath
from typing import Any

import httpx

from app import __version__
from app.core.errors import ZoiError
from app.db.base import utcnow
from app.security.cost_guard import CostGuard

CHECK_EVERY = timedelta(hours=24)
MAX_ZIP_BYTES = 200 * 1024 * 1024
_VERSION = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")


def parse_version(text: str) -> tuple[int, int, int] | None:
    m = _VERSION.match(text.strip())
    return (int(m[1]), int(m[2]), int(m[3])) if m else None


class UpdateService:
    def __init__(self, *, guard: CostGuard, repo: str, root: Path, enabled: bool,
                 api_base: str = "https://api.github.com", transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.guard = guard
        self.repo = repo
        self.root = root
        self.enabled = enabled  # False di mode online (server bukan laptop pengguna)
        self.api_base = api_base.rstrip("/")
        self.transport = transport
        self.current = __version__
        self.latest: dict[str, Any] | None = None
        self.checked_at: datetime | None = None
        self.error: str | None = None
        self.phase = "idle"  # idle | downloading | applying
        self._lock = asyncio.Lock()

    def _client(self, timeout: float = 20) -> httpx.AsyncClient:
        return self.guard.async_client(timeout=timeout, follow_redirects=True, transport=self.transport,
                                       headers={"Accept": "application/vnd.github+json",
                                                "User-Agent": f"zoi-command-center/{self.current}"})

    def status(self) -> dict[str, Any]:
        latest = self.latest
        zero = (0, 0, 0)
        newer = bool(latest and (parse_version(latest["version"]) or zero) > (parse_version(self.current) or zero))
        return {
            "enabled": self.enabled, "repo": self.repo, "current": self.current,
            "latest": latest, "update_available": newer,
            "checked_at": self.checked_at.isoformat() if self.checked_at else None,
            "error": self.error, "phase": self.phase,
            "can_install": newer and self.enabled and sys.platform == "win32" and self.phase == "idle",
            "install_note": None if sys.platform == "win32" else "Pemasangan otomatis hanya untuk Windows.",
        }

    async def check(self) -> dict[str, Any]:
        if not self.enabled:
            raise ZoiError("Update otomatis hanya untuk ZOI di laptop (mode local).", status_code=400)
        async with self._lock:
            try:
                async with self._client() as client:
                    res = await client.get(f"{self.api_base}/repos/{self.repo}/releases/latest")
                if res.status_code == 404:
                    self.latest, self.error = None, "Belum ada rilis di GitHub, atau repo masih privat."
                else:
                    res.raise_for_status()
                    self.latest, self.error = self._release(res.json()), None
            except (httpx.HTTPError, ValueError, KeyError) as exc:
                self.error = f"Tidak bisa mengecek update: {type(exc).__name__}. Periksa koneksi internet."
            self.checked_at = utcnow()
        return self.status()

    def _release(self, data: dict[str, Any]) -> dict[str, Any] | None:
        version = str(data.get("tag_name", "")).lstrip("v")
        if parse_version(version) is None:
            return None
        assets = {a["name"]: a for a in data.get("assets", [])}
        zip_name = f"zoi-command-center-{version}.zip"
        zip_asset, sha_asset = assets.get(zip_name), assets.get(f"{zip_name}.sha256")
        return {"version": version, "name": data.get("name") or f"v{version}", "notes": (data.get("body") or "")[:4000],
                "published_at": data.get("published_at"), "url": data.get("html_url"),
                "zip_url": zip_asset["browser_download_url"] if zip_asset else None,
                "sha_url": sha_asset["browser_download_url"] if sha_asset else None,
                "size": zip_asset.get("size") if zip_asset else None}

    async def loop(self) -> None:
        """Cek otomatis: 2 menit setelah ZOI menyala, lalu tiap 24 jam. Hanya mengecek, tidak memasang."""
        await asyncio.sleep(120)
        while True:
            try:
                await self.check()
            except ZoiError:
                return
            await asyncio.sleep(CHECK_EVERY.total_seconds())

    def target_dir(self, version: str) -> Path:
        return self.root.parent / f"zoi-command-center-{version}"

    async def install(self) -> dict[str, Any]:
        status = self.status()
        if not status["can_install"]:
            raise ZoiError(status["install_note"] or "Tidak ada update yang bisa dipasang sekarang.", status_code=409)
        release = self.latest or {}
        if not release.get("zip_url") or not release.get("sha_url"):
            raise ZoiError("Rilis ini tidak punya file ZIP dan .sha256 — tidak dipasang demi keamanan.",
                           status_code=409)
        version = release["version"]
        target = self.target_dir(version)
        self.phase = "downloading"
        try:
            if not (target / "deploy" / "windows" / "apply-update.ps1").is_file():
                await self._download_and_extract(release, target)
            self._launch(target)
            self.phase = "applying"
        except Exception:
            self.phase = "idle"
            raise
        return self.status()

    async def _download_and_extract(self, release: dict[str, Any], target: Path) -> None:
        version = release["version"]
        work = self.root.parent / f".zoi-update-{version}"
        shutil.rmtree(work, ignore_errors=True)
        work.mkdir(parents=True)
        zip_path = work / f"zoi-command-center-{version}.zip"
        try:
            async with self._client(timeout=300) as client:
                sha = (await client.get(release["sha_url"])).raise_for_status().text.split()[0].lower()
                digest = hashlib.sha256()
                size = 0
                async with client.stream("GET", release["zip_url"]) as res:
                    res.raise_for_status()
                    with zip_path.open("wb") as fh:
                        async for chunk in res.aiter_bytes():
                            size += len(chunk)
                            if size > MAX_ZIP_BYTES:
                                raise ZoiError("File update terlalu besar — dibatalkan.", status_code=502)
                            digest.update(chunk)
                            fh.write(chunk)
            if digest.hexdigest() != sha:
                raise ZoiError("Hash file update tidak cocok — file rusak atau diubah. Tidak dipasang.",
                               status_code=502)
            self._extract(zip_path, version, work / "x")
            shutil.rmtree(target, ignore_errors=True)
            (work / "x" / f"zoi-command-center-{version}").rename(target)
        except httpx.HTTPError as exc:
            raise ZoiError(f"Gagal mengunduh update: {type(exc).__name__}.", status_code=502) from exc
        finally:
            shutil.rmtree(work, ignore_errors=True)

    @staticmethod
    def _extract(zip_path: Path, version: str, dest: Path) -> None:
        prefix = f"zoi-command-center-{version}"
        with zipfile.ZipFile(zip_path) as zf:
            for name in zf.namelist():
                parts = PurePosixPath(name).parts
                if not parts or parts[0] != prefix or ".." in parts or name.startswith("/") or "\\" in name:
                    raise ZoiError("Isi ZIP update tidak sesuai format rilis ZOI — tidak dipasang.", status_code=502)
            zf.extractall(dest)
        if not (dest / prefix / "deploy" / "windows" / "apply-update.ps1").is_file():
            raise ZoiError("ZIP update tidak berisi skrip pemasang.", status_code=502)

    def _launch(self, target: Path) -> None:  # pragma: no cover — hanya Windows
        script = target / "deploy" / "windows" / "apply-update.ps1"
        subprocess.Popen(  # noqa: S603 — path dari folder rilis yang hash-nya sudah dicocokkan
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script), "-From", str(self.root)],
            cwd=str(target), creationflags=subprocess.CREATE_NEW_CONSOLE)  # type: ignore[attr-defined]
