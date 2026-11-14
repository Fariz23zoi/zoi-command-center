"""Periksa lisensi SEMUA dependensi (Python di venv backend + npm produksi) dan tulis THIRD_PARTY_NOTICES.md.

Gagal (exit 1) bila ada lisensi di luar daftar izin. Jalankan dengan Python dari backend/.venv:
  backend/.venv/bin/python scripts/check_licenses.py [--write THIRD_PARTY_NOTICES.md]
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from importlib import metadata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALLOWED = {"MIT", "MIT-CMU", "BSD-2-Clause", "BSD-3-Clause", "Apache-2.0", "ISC", "PSF-2.0", "Python-2.0", "0BSD",
           "MPL-2.0", "Unlicense", "CC0-1.0", "BlueOak-1.0.0", "Zlib", "HPND", "CC-BY-4.0"}
CLASSIFIER_MAP = {
    "MIT License": "MIT", "BSD License": "BSD-3-Clause", "Apache Software License": "Apache-2.0",
    "Python Software Foundation License": "PSF-2.0", "ISC License (ISCL)": "ISC",
    "Mozilla Public License 2.0 (MPL 2.0)": "MPL-2.0", "The Unlicense (Unlicense)": "Unlicense",
}
# Penyesuaian manual yang sudah diverifikasi (metadata paket tidak lengkap).
KNOWN = {"pip": "MIT", "setuptools": "MIT"}


def normalize(text: str) -> list[str]:
    text = text.replace("(", " ").replace(")", " ")
    parts = [p.strip() for p in re.split(r"\s+OR\s+|\s+AND\s+|/|,", text) if p.strip()]
    fixes = {"BSD": "BSD-3-Clause", "Apache 2.0": "Apache-2.0", "Apache License 2.0": "Apache-2.0",
             "Apache Software License": "Apache-2.0", "MIT License": "MIT", "BSD-3": "BSD-3-Clause",
             "3-Clause BSD License": "BSD-3-Clause", "BSD 3-Clause": "BSD-3-Clause", "PSF": "PSF-2.0"}
    return [fixes.get(p, p) for p in parts]


def python_licenses() -> list[tuple[str, str, str, str]]:
    rows = []
    for dist in metadata.distributions():
        name = dist.metadata["Name"]
        meta = dist.metadata
        expr = meta.get("License-Expression") or ""
        if not expr:
            classifiers = [c.split(" :: ")[-1] for c in meta.get_all("Classifier") or [] if c.startswith("License ::")]
            mapped = [CLASSIFIER_MAP.get(c, c) for c in classifiers if c != "OSI Approved"]
            expr = " OR ".join(mapped)
        if not expr:
            license_field = (meta.get("License") or "").strip().splitlines()
            expr = license_field[0] if license_field else ""
        expr = KNOWN.get(name.lower(), expr) or "TIDAK DIKETAHUI"
        rows.append(("python", name, dist.version, expr))
    return sorted(rows, key=lambda r: r[1].lower())


def npm_licenses() -> list[tuple[str, str, str, str]]:
    frontend = ROOT / "frontend"
    out = subprocess.run(["npm", "ls", "--omit=dev", "--all", "--json"], cwd=frontend, capture_output=True,
                         text=True, check=False)
    tree = json.loads(out.stdout or "{}")
    seen: dict[tuple[str, str], str] = {}

    def walk(deps: dict) -> None:
        for name, info in (deps or {}).items():
            if info.get("missing") or "version" not in info:
                continue  # peer dependency opsional yang tidak terpasang (mis. immer untuk zustand)
            version = info["version"]
            if name.startswith("@zoi/"):
                walk(info.get("dependencies", {}))
                continue
            pkg = frontend / "node_modules" / name / "package.json"
            lic = "TIDAK DIKETAHUI"
            if pkg.exists():
                data = json.loads(pkg.read_text(encoding="utf-8"))
                lic = data.get("license") if isinstance(data.get("license"), str) else lic
            seen[(name, version)] = lic
            walk(info.get("dependencies", {}))

    walk(tree.get("dependencies", {}))
    return sorted((("npm", n, v, lic) for (n, v), lic in seen.items()), key=lambda r: r[1])


def is_allowed(expr: str) -> bool:
    parts = normalize(expr)
    # "A OR B": cukup salah satu diizinkan. "A AND B": semuanya harus diizinkan.
    if " AND " in expr:
        return all(p in ALLOWED for p in parts)
    return any(p in ALLOWED for p in parts)


def main(argv: list[str]) -> int:
    rows = python_licenses() + npm_licenses()
    bad = [r for r in rows if not is_allowed(r[3])]
    if "--write" in argv:
        target = ROOT / argv[argv.index("--write") + 1]
        lines = ["# Third-party notices", "",
                 "Daftar dependensi ZOI beserta lisensinya (dibuat otomatis oleh `scripts/check_licenses.py`).",
                 "Python: seluruh paket di venv backend (termasuk alat pengembangan). npm: dependensi produksi frontend.",
                 "", "| Ekosistem | Paket | Versi | Lisensi |", "|---|---|---|---|"]
        lines += [f"| {e} | {n} | {v} | {lic} |" for e, n, v, lic in rows]
        lines += ["", "## Aset yang ikut dibundel (avatar 3D)", "",
                  "Disalin dari paket `@interviewflowai/talking-avatar` ke `avatar-assets/` dan disajikan dari server ZOI",
                  "sendiri (tanpa CDN). Teks lisensinya ikut disalin ke folder yang sama.", "",
                  "| Aset | Asal | Lisensi |", "|---|---|---|",
                  "| `female.glb`, `male.glb` | Microsoft Rocketbox (business female 04 / male 01), dikonversi oleh "
                  "talking-avatar | MIT (Copyright (c) 2020 Microsoft) — `LICENSE-rocketbox.txt` |",
                  "| `viseme-model.bin` | Bobot model lip-sync talking-avatar | MIT — `LICENSE-talking-avatar.txt` |"]
        lines += ["", "## Program terpisah (TIDAK dibundel dengan ZOI)", "",
                  "- **Piper** (`piper-tts` 1.8.0, GPL-3.0-or-later) — dipasang & dijalankan pengguna sendiri sebagai server",
                  "  HTTP lokal. ZOI hanya mengirim teks lewat HTTP dan tidak mengimpor kodenya.",
                  "- **Suara `id_ID-news_tts-medium`** — repo MIT, tetapi dataset asalnya tidak jelas (lihat",
                  "  `docs/audit/LICENSE_COMPLIANCE.md`). Hanya untuk pemakaian pribadi.",
                  "- **faster-whisper dan dependensinya** di atas adalah paket opsional (`requirements-voice.txt`)."]
        lines += ["", "Lisensi lengkap tiap paket tersedia di folder paket masing-masing (site-packages / node_modules).",
                  "", "ZOI sendiri berlisensi MIT — lihat `LICENSE`."]
        target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{len(rows)} paket diperiksa ({sum(r[0] == 'python' for r in rows)} Python, "
          f"{sum(r[0] == 'npm' for r in rows)} npm).")
    for r in bad:
        print(f"  DITOLAK: {r[0]} {r[1]} {r[2]} — {r[3]}")
    print("Semua lisensi diizinkan." if not bad else f"{len(bad)} paket bermasalah.")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
