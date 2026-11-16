"""Pindai rahasia di file yang dilacak Git DAN seluruh riwayat commit (Phase 9). Tanpa dependensi.

Menandai pola kunci API/token/connection string yang nyata. Nilai uji yang sengaja palsu di folder tests/
diizinkan lewat ALLOW. Keluar dengan kode 1 bila ada temuan.

    python scripts/scan_secrets.py
"""

from __future__ import annotations

import re
import subprocess
import sys

PATTERNS = {
    "NVIDIA API key": r"nvapi-[A-Za-z0-9_-]{20,}",
    "OpenRouter API key": r"sk-or-v1-[A-Fa-f0-9]{20,}",
    "Google OAuth client secret": r"GOCSPX-[A-Za-z0-9_-]{10,}",
    "Google API key": r"AIza[0-9A-Za-z_-]{35}",
    "Google access token": r"ya29\.[0-9A-Za-z_-]{20,}",
    "Google refresh token": r"1//0[0-9A-Za-z_-]{20,}",
    "GitHub token": r"gh[pousr]_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{40,}",
    "Private key": r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
    "Postgres URL dengan sandi": r"postgres(?:ql)?://[^:@/\s\"']+:[^@/\s\"'{}$]{6,}@[A-Za-z0-9.-]+",
    "Neon password": r"npg_[A-Za-z0-9]{10,}",
}
# Nilai palsu yang sengaja dipakai tes (bukan rahasia).
ALLOW = {"GOCSPX-rahasia-uji", "GOCSPX-web-uji", "ya29.abcdefghijklmnopqrstuvwxyz0123"}


def scan(text: str, where: str) -> list[str]:
    found = []
    for label, pattern in PATTERNS.items():
        for match in re.finditer(pattern, text):
            if match.group(0) not in ALLOW:
                found.append(f"{where}: {label}: {match.group(0)[:12]}…")
    return found


def main() -> int:
    findings: list[str] = []
    files = subprocess.run(["git", "ls-files"], capture_output=True, text=True, check=True).stdout.split()
    for name in files:
        try:
            with open(name, encoding="utf-8") as fh:
                findings += scan(fh.read(), name)
        except (UnicodeDecodeError, OSError):
            continue
    history = subprocess.run(["git", "log", "--all", "-p", "--no-color", "--unified=0"], capture_output=True,
                             text=True, errors="replace", check=True).stdout
    added = "\n".join(line[1:] for line in history.splitlines() if line.startswith("+") and not line.startswith("+++"))
    findings += scan(added, "riwayat git")
    names = subprocess.run(["git", "log", "--all", "--name-only", "--pretty=format:"], capture_output=True, text=True,
                           check=True).stdout.split()
    for name in sorted(set(names)):
        if re.search(r"(^|/)\.env$|client_secret.*\.json$|youtube_client\.json$|\.pem$|Blueprint_Studio\.html$", name):
            findings.append(f"riwayat git: file berisiko pernah di-commit: {name}")
    for line in sorted(set(findings)):
        print(line)
    print(f"{len(files)} file + riwayat git diperiksa. Temuan: {len(set(findings))}.")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
