"""Penyimpanan refresh token. Utama: keyring sistem (Windows Credential Manager). Cadangan: file di
`<data>/secrets/` dengan izin terbatas — BUKAN terenkripsi, dan statusnya dilaporkan jujur ke pengguna.

Folder `secrets` tidak pernah ikut ekspor data dan tidak pernah berada di repo.
"""

from __future__ import annotations

import contextlib
import json
from pathlib import Path
from typing import Any, Protocol

SERVICE = "zoi-youtube-intelligence"


class KeyringLike(Protocol):
    def get_password(self, service: str, name: str) -> str | None: ...

    def set_password(self, service: str, name: str, value: str) -> None: ...

    def delete_password(self, service: str, name: str) -> None: ...


def system_keyring() -> KeyringLike | None:
    """Keyring sistem bila benar-benar bisa dipakai; None bila tidak ada (mis. Linux tanpa desktop)."""
    try:
        import keyring
        from keyring.errors import KeyringError

        try:
            keyring.get_password(SERVICE, "__probe__")
        except KeyringError:
            return None
        return keyring  # type: ignore[return-value]
    except Exception:  # noqa: BLE001 — keyring rusak/tidak terpasang → pakai cadangan, dilaporkan di status
        return None


class SecretStore:
    def __init__(self, data_dir: Path, backend: KeyringLike | None | str = "auto") -> None:
        self.dir = data_dir / "secrets"
        self._keyring: KeyringLike | None = system_keyring() if backend == "auto" else backend  # type: ignore[assignment]

    @property
    def kind(self) -> str:
        return "keyring" if self._keyring is not None else "file"

    @property
    def warning(self) -> str | None:
        if self._keyring is not None:
            return None
        return ("Penyimpanan kunci sistem tidak tersedia di komputer ini, jadi token disimpan sebagai FILE BIASA "
                "(tidak terenkripsi) di folder data/secrets. Siapa pun yang bisa membuka folder itu bisa memakainya.")

    def _file(self) -> Path:
        return self.dir / "tokens.json"

    def _read_file(self) -> dict[str, Any]:
        try:
            return json.loads(self._file().read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def _write_file(self, data: dict[str, Any]) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        path = self._file()
        if not data:
            path.unlink(missing_ok=True)
            return
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data), encoding="utf-8")
        with contextlib.suppress(OSError):
            tmp.chmod(0o600)
        tmp.replace(path)

    def get(self, name: str) -> str | None:
        if self._keyring is not None:
            return self._keyring.get_password(SERVICE, name)
        value = self._read_file().get(name)
        return value if isinstance(value, str) else None

    def set(self, name: str, value: str) -> None:
        if self._keyring is not None:
            self._keyring.set_password(SERVICE, name, value)
            return
        data = self._read_file()
        data[name] = value
        self._write_file(data)

    def delete(self, name: str) -> None:
        if self._keyring is not None:
            with contextlib.suppress(Exception):  # sudah tidak ada → tidak masalah
                self._keyring.delete_password(SERVICE, name)
            return
        data = self._read_file()
        data.pop(name, None)
        self._write_file(data)
