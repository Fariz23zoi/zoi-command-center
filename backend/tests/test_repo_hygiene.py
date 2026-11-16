"""Kebersihan repo & kesiapan Windows."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_powershell_scripts_are_ascii():
    """Windows PowerShell 5.1 salah membaca UTF-8 tanpa BOM → skrip .ps1 wajib ASCII murni."""
    scripts = list((ROOT / "deploy" / "windows").glob("*.ps1"))
    assert {p.name for p in scripts} >= {"install.ps1", "start.ps1", "stop.ps1", "autostart.ps1", "common.ps1"}
    for path in scripts:
        path.read_bytes().decode("ascii")


def test_gitignore_protects_secrets_and_data():
    rules = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    for rule in (".env", "data/", "data-dev/", "*.db", ".venv/", "node_modules/"):
        assert rule in rules


def test_ps1_crlf_on_checkout():
    assert "*.ps1 text eol=crlf" in (ROOT / ".gitattributes").read_text(encoding="utf-8")


def test_env_examples_have_no_secrets():
    for name in (".env.development.example", ".env.local.example"):
        text = (ROOT / name).read_text(encoding="utf-8")
        assert "API_KEY" not in text.upper() and "sk-" not in text and "AIza" not in text
