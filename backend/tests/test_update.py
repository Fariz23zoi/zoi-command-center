"""Update ZOI dari GitHub Releases — cek versi, verifikasi hash, ekstrak aman (tanpa jaringan sungguhan)."""

from __future__ import annotations

import hashlib
import io
import zipfile
from pathlib import Path

import httpx
import pytest

from app.core.errors import ZoiError
from app.security.cost_guard import CostGuard
from app.update import service as svc
from app.update.service import UpdateService, parse_version

API = "https://api.github.com"


def make_zip(version: str, *, evil: bool = False) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        prefix = f"zoi-command-center-{version}"
        zf.writestr(f"{prefix}/deploy/windows/apply-update.ps1", "Write-Host ok")
        zf.writestr(f"{prefix}/backend/app/__init__.py", f'__version__ = "{version}"')
        if evil:
            zf.writestr("../escape.txt", "x")
    return buf.getvalue()


def release(version: str, data: bytes, sha: str | None = None) -> tuple[dict, dict[str, bytes]]:
    name = f"zoi-command-center-{version}.zip"
    files = {f"/dl/{name}": data, f"/dl/{name}.sha256": f"{sha or hashlib.sha256(data).hexdigest()}  {name}\n".encode()}
    body = {"tag_name": f"v{version}", "name": f"ZOI {version}", "body": "Catatan rilis",
            "html_url": "https://github.com/x/y/releases/tag/v" + version,
            "assets": [{"name": name, "size": len(data), "browser_download_url": f"https://github.com/dl/{name}"},
                       {"name": f"{name}.sha256", "size": 80,
                        "browser_download_url": f"https://github.com/dl/{name}.sha256"}]}
    return body, files


def service(tmp_path: Path, body: dict | None, files: dict[str, bytes] | None = None,
            status: int = 200) -> UpdateService:
    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path.endswith("/releases/latest"):
            return httpx.Response(status, json=body or {})
        if files and req.url.path in files:
            return httpx.Response(200, content=files[req.url.path])
        return httpx.Response(404)

    root = tmp_path / "zoi-command-center-1.2.3"
    root.mkdir()
    upd = UpdateService(guard=CostGuard(), repo="x/y", root=root, enabled=True, api_base=API,
                        transport=httpx.MockTransport(handler))
    upd.current = "1.2.3"
    upd._launch = lambda target: setattr(upd, "launched", target)  # type: ignore[method-assign]
    return upd


def test_parse_version():
    assert parse_version("v1.10.0") == (1, 10, 0) and parse_version("1.2") is None


async def test_check_newer_and_same(tmp_path):
    body, _ = release("1.3.0", b"zip")
    upd = service(tmp_path, body)
    st = await upd.check()
    assert st["update_available"] is True and st["latest"]["version"] == "1.3.0" and st["error"] is None
    upd.current = "1.3.0"
    assert upd.status()["update_available"] is False


async def test_check_private_or_missing_repo(tmp_path):
    st = await service(tmp_path, None, status=404).check()
    assert st["update_available"] is False and "privat" in st["error"]


async def test_install_verifies_hash_and_extracts_beside(tmp_path, monkeypatch):
    monkeypatch.setattr(svc.sys, "platform", "win32")
    data = make_zip("1.3.0")
    body, files = release("1.3.0", data)
    upd = service(tmp_path, body, files)
    await upd.check()
    st = await upd.install()
    target = tmp_path / "zoi-command-center-1.3.0"
    assert upd.launched == target and st["phase"] == "applying"
    assert (target / "backend" / "app" / "__init__.py").read_text() == '__version__ = "1.3.0"'
    assert not any(p.name.startswith(".zoi-update") for p in tmp_path.iterdir())


async def test_install_rejects_bad_hash_and_path_traversal(tmp_path, monkeypatch):
    monkeypatch.setattr(svc.sys, "platform", "win32")
    body, files = release("1.3.0", make_zip("1.3.0"), sha="0" * 64)
    upd = service(tmp_path, body, files)
    await upd.check()
    with pytest.raises(ZoiError, match="Hash"):
        await upd.install()
    assert upd.phase == "idle" and not (tmp_path / "zoi-command-center-1.3.0").exists()

    (tmp_path / "b").mkdir()
    body, files = release("1.3.0", make_zip("1.3.0", evil=True))
    upd = service(tmp_path / "b", body, files)
    await upd.check()
    with pytest.raises(ZoiError, match="format rilis"):
        await upd.install()
    assert not (tmp_path / "escape.txt").exists()


async def test_install_only_on_windows_and_needs_sha(tmp_path, monkeypatch):
    body, files = release("1.3.0", make_zip("1.3.0"))
    upd = service(tmp_path, body, files)
    await upd.check()
    monkeypatch.setattr(svc.sys, "platform", "linux")
    with pytest.raises(ZoiError, match="Windows"):
        await upd.install()
    monkeypatch.setattr(svc.sys, "platform", "win32")
    upd.latest = {**upd.latest, "sha_url": None}
    with pytest.raises(ZoiError, match="sha256"):
        await upd.install()


def test_api_status_and_online_disabled(client_factory):
    client = client_factory()
    st = client.get("/api/update/status").json()
    assert st["enabled"] is True and st["update_available"] is False and st["repo"] == "Fariz23zoi/zoi-command-center"


def test_cost_guard_allows_github_only_for_update():
    guard = CostGuard()
    assert guard.check("api.github.com")[0] and guard.check("release-assets.githubusercontent.com")[0]
    assert not guard.check("api.openai.com")[0]
