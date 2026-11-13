"""Batas antarbagian arsitektur dijaga otomatis."""

from __future__ import annotations

import ast
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "app"


def imports_of(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_api_uses_providers_only_through_registry():
    for path in (APP / "api").rglob("*.py"):
        assert not imports_of(path) & {"app.providers.mock", "app.providers.ollama"}, path


def test_only_registry_and_cli_construct_concrete_providers():
    allowed = {APP / "providers" / "registry.py", APP / "cli.py", APP / "providers" / "mock.py",
               APP / "providers" / "ollama.py"}
    for path in APP.rglob("*.py"):
        if path in allowed:
            continue
        assert not imports_of(path) & {"app.providers.mock", "app.providers.ollama"}, path


def test_integrations_never_import_external_apps():
    for path in (APP / "integrations").rglob("*.py"):
        assert not any(n.startswith(("shorts_generator", "app_clipper")) for n in imports_of(path)), path
