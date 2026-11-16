"""HyperFrames sebagai renderer TAMBAHAN yang opsional (keputusan K-3 Phase 7, ADR 0013).

- ZOI tidak pernah memasang apa pun: pengguna menjalankan `npm install hyperframes` sendiri di folder
  `ZOI_HYPERFRAMES_DIR`. ZOI memanggil `node <folder>/node_modules/hyperframes/bin/hyperframes.mjs`.
- HyperFrames bisa mengunduh Chrome sendiri; ZOI SELALU memberi path browser yang sudah terpasang
  (HYPERFRAMES_BROWSER_PATH) dan menolak render bila tidak ada.
- Telemetri dimatikan; render cloud (berbayar) tidak pernah dipakai — hanya `render` lokal.
- Templat: kartu teks per beat dengan animasi CSS saja (GSAP tidak dipakai: lisensinya bukan open source).
"""

from __future__ import annotations

import html
import json
import os
import platform
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

MIN_NODE_MAJOR = 22
TESTED_VERSION = "0.9.55"
WORDS_PER_SECOND = 2.2  # sama dengan perkiraan Blueprint Studio
MIN_BEAT_S, MAX_BEAT_S = 2.0, 20.0
SIZES = {"9:16": (720, 1280), "16:9": (1280, 720), "1:1": (1080, 1080)}

QUIET_ENV = {"HYPERFRAMES_NO_TELEMETRY": "1", "DO_NOT_TRACK": "1", "HYPERFRAMES_SKIP_SKILLS": "1",
             "HYPERFRAMES_RENDER_LOCK": "off"}

BROWSER_CANDIDATES = {
    "Windows": [r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
                r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"],
    "Darwin": ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
               "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"],
    "Linux": ["/usr/bin/google-chrome", "/usr/bin/google-chrome-stable", "/usr/bin/chromium",
              "/usr/bin/chromium-browser", "/usr/bin/microsoft-edge"],
}


def find_browser() -> str | None:
    for candidate in BROWSER_CANDIDATES.get(platform.system(), []):
        if Path(candidate).is_file():
            return candidate
    return None


def _run(cmd: list[str], timeout: float = 20) -> str | None:
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False,
                             env={**os.environ, **QUIET_ENV})
    except (OSError, subprocess.TimeoutExpired):
        return None
    return (out.stdout or out.stderr).strip() if out.returncode == 0 else None


@dataclass
class HyperFrames:
    folder: Path | None
    browser: str | None = None  # None → dicari otomatis

    @property
    def entry(self) -> Path | None:
        return self.folder / "node_modules" / "hyperframes" / "bin" / "hyperframes.mjs" if self.folder else None

    def status(self) -> dict[str, Any]:
        problems: list[str] = []
        node = shutil.which("node")
        node_version = _run([node, "--version"]) if node else None
        major = int(re.sub(r"[^0-9].*", "", node_version.lstrip("v"))) if node_version else 0
        if not node:
            problems.append("Node.js tidak ditemukan. Pasang Node.js 22+ sendiri dari nodejs.org (gratis).")
        elif major < MIN_NODE_MAJOR:
            problems.append(f"Node.js {node_version} terlalu lama — HyperFrames butuh versi {MIN_NODE_MAJOR}+.")
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            problems.append("FFmpeg tidak ditemukan di PATH.")
        version = None
        if self.folder is None:
            problems.append("ZOI_HYPERFRAMES_DIR belum diisi (folder tempat kamu menjalankan "
                            "`npm install hyperframes`).")
        elif not self.entry or not self.entry.is_file():
            problems.append(f"HyperFrames belum terpasang di {self.folder} — jalankan `npm install hyperframes` "
                            "di folder itu.")
        elif node and major >= MIN_NODE_MAJOR:
            version = _run([node, str(self.entry), "--version"], timeout=60)
            if not version:
                problems.append("HyperFrames terpasang tetapi tidak bisa dijalankan (`--version` gagal).")
        browser = self.browser or find_browser()
        if not browser:
            problems.append("Chrome atau Edge tidak ditemukan. ZOI tidak membiarkan HyperFrames mengunduh "
                            "browser sendiri.")
        return {"enabled": not problems, "problems": problems, "node": node_version, "ffmpeg": bool(ffmpeg),
                "version": version, "tested_version": TESTED_VERSION, "browser": browser,
                "folder": str(self.folder) if self.folder else None}

    def command(self, project: Path, output: Path) -> tuple[list[str], dict[str, str]]:
        node = shutil.which("node") or "node"
        browser = self.browser or find_browser() or ""
        cmd = [node, str(self.entry), "render", str(project), "-o", str(output), "--quality", "draft",
               "--workers", "1", "--quiet", "--no-wait"]
        env = {**os.environ, **QUIET_ENV, "HYPERFRAMES_BROWSER_PATH": browser}
        return cmd, env


def estimate_seconds(text: str) -> float:
    words = len(text.split())
    return max(MIN_BEAT_S, min(MAX_BEAT_S, round(words / WORDS_PER_SECOND + 0.6, 2)))


def compose(package: dict[str, Any], timings: list[dict[str, Any]] | None = None) -> str:
    """paket + (opsional) waktu narasi per beat → index.html komposisi HyperFrames."""
    width, height = SIZES.get(str(package.get("rasio")), SIZES["9:16"])
    beats = package.get("beats") or []
    scale = width / 720
    clips: list[str] = []
    t = 0.0
    for i, beat in enumerate(beats):
        timing = timings[i] if timings and i < len(timings) else None
        duration = round(float(timing["duration"]) if timing else estimate_seconds(str(beat.get("n", ""))), 3)
        clips.append(
            f'<section class="clip" data-start="{t:.3f}" data-duration="{duration:.3f}">'
            f'<div class="k">{html.escape(str(beat.get("k", "")))}</div>'
            f'<div class="n">{html.escape(str(beat.get("n", "")))}</div></section>')
        if timing and timing.get("file"):
            clips.append(f'<audio data-start="{t:.3f}" data-duration="{duration:.3f}" '
                         f'src="{html.escape(timing["file"])}"></audio>')
        t += duration
    total = round(t, 3)
    mock = '<div class="mock">MOCK — teks tiruan</div>' if package.get("mock") else ""
    title = html.escape(str(package.get("judul", "ZOI")))
    return f"""<!doctype html>
<html lang="id"><head><meta charset="utf-8"><title>{title}</title>
<!-- Dibuat ZOI dari paket {html.escape(json.dumps(package.get("format")))}; templat kartu teks, animasi CSS saja. -->
<style>
html,body{{margin:0;background:#0b0e14}}
#root{{position:relative;width:{width}px;height:{height}px;overflow:hidden;color:#f2f4f8;
  font-family:"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif}}
.clip{{position:absolute;inset:0;display:flex;flex-direction:column;justify-content:center;
  padding:{round(64 * scale)}px;box-sizing:border-box}}
.k{{font-size:{round(28 * scale)}px;color:#4f8cff;letter-spacing:.12em;text-transform:uppercase;
  animation:masuk .6s ease-out both}}
.n{{font-size:{round(46 * scale)}px;line-height:1.28;margin-top:{round(24 * scale)}px;
  animation:masuk .8s .2s ease-out both}}
.mock{{position:absolute;top:16px;left:16px;font-size:{round(20 * scale)}px;color:#ffb020;z-index:5}}
@keyframes masuk{{from{{opacity:0;transform:translateY(30px)}}to{{opacity:1;transform:none}}}}
</style></head><body>
<div id="root" data-composition-id="root" data-width="{width}" data-height="{height}" data-fps="30"
     data-start="0" data-duration="{total:.3f}">
{mock}
{chr(10).join(clips)}
</div></body></html>
"""
