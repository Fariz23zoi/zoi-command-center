"""Penjaga ZERO PAID API: SDK layanan AI berbayar tidak boleh terpasang atau di-import."""

from __future__ import annotations

import ast
from importlib import metadata
from pathlib import Path

BANNED_MODULES = {"openai", "anthropic", "google.genai", "google.generativeai", "elevenlabs", "deepgram",
                  "azure", "cohere", "groq", "mistralai"}
BANNED_DISTS = {"openai", "anthropic", "google-genai", "google-generativeai", "elevenlabs", "deepgram-sdk",
                "azure-cognitiveservices-speech", "cohere", "groq", "mistralai"}
APP_DIR = Path(__file__).resolve().parents[1] / "app"


def test_app_code_does_not_import_paid_sdks():
    offenders = []
    for path in APP_DIR.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            for name in names:
                if any(name == b or name.startswith(b + ".") for b in BANNED_MODULES):
                    offenders.append(f"{path.relative_to(APP_DIR)}: {name}")
    assert offenders == []


def test_paid_sdks_not_installed():
    installed = {d.metadata["Name"].lower() for d in metadata.distributions()}
    assert installed & BANNED_DISTS == set()
