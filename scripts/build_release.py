"""Buat paket rilis untuk local server Windows: kode backend + frontend SUDAH di-build + skrip deploy.

Local server tidak memerlukan Node.js. Tidak ada data, .env, venv, atau model di dalam paket.

  python scripts/build_release.py            → release/zoi-command-center-<versi>.zip
"""

from __future__ import annotations

import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app import __version__  # noqa: E402

DIST = ROOT / "frontend" / "apps" / "web" / "dist"
INCLUDE_TRACKED = ("backend/", "deploy/", "docs/", ".env.development.example", ".env.local.example",
                   "README.md", "CHANGELOG.md", "LICENSE", "THIRD_PARTY_NOTICES.md", ".gitattributes",
                   "Buka ZOI.bat",
                   "Matikan ZOI.bat", "Matikan Semua.bat")
EXCLUDE_PARTS = {"tests", "__pycache__", ".pytest_cache", ".ruff_cache", ".venv"}


def tracked_files() -> list[str]:
    out = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True)
    return [f for f in out.stdout.decode().split("\0") if f]


def main() -> int:
    if not (DIST / "index.html").is_file():
        print("Frontend belum di-build. Jalankan: scripts/build_frontend.sh", file=sys.stderr)
        return 1
    out = ROOT / "release" / f"zoi-command-center-{__version__}.zip"
    out.parent.mkdir(exist_ok=True)
    prefix = f"zoi-command-center-{__version__}"
    count = 0
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for rel in tracked_files():
            if not rel.startswith(INCLUDE_TRACKED) or EXCLUDE_PARTS & set(Path(rel).parts):
                continue
            data = (ROOT / rel).read_bytes()
            if rel.endswith((".ps1", ".bat")):  # Windows: CRLF
                data = data.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
            zf.writestr(f"{prefix}/{rel}", data)
            count += 1
        for path in sorted(DIST.rglob("*")):
            if path.is_file():
                zf.write(path, f"{prefix}/{path.relative_to(ROOT).as_posix()}")
                count += 1
    print(f"Paket rilis: {out} ({count} file, {out.stat().st_size / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
