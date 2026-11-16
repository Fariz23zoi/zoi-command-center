"""Penyimpanan rahasia di database (mode online). Nilai dienkripsi dengan Fernet (AES-128-CBC + HMAC),
kuncinya diturunkan dari ZOI_SECRET_KEY lewat scrypt. Antarmukanya sama dengan SecretStore (get/set/delete),
jadi YouTube dan AI Cloud tidak perlu tahu di mana rahasia disimpan.
"""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import select

from app.db.models import Secret
from app.db.session import Database

_SALT = b"zoi-secrets-v1"  # salt tetap: kuncinya sudah acak (ZOI_SECRET_KEY dari Render), bukan kata sandi manusia


def _fernet(secret_key: str) -> Fernet:
    derived = hashlib.scrypt(secret_key.encode("utf-8"), salt=_SALT, n=2**14, r=8, p=1, dklen=32)
    return Fernet(base64.urlsafe_b64encode(derived))


class DbSecretStore:
    kind = "database"
    warning = None  # terenkripsi — tidak ada peringatan penyimpanan

    def __init__(self, db: Database, secret_key: str) -> None:
        self.db = db
        self._fernet = _fernet(secret_key)

    def get(self, name: str) -> str | None:
        with self.db.session() as s:
            row = s.execute(select(Secret).where(Secret.name == name)).scalar_one_or_none()
            if row is None:
                return None
            try:
                return self._fernet.decrypt(row.value_encrypted.encode("ascii")).decode("utf-8")
            except (InvalidToken, ValueError):
                # ZOI_SECRET_KEY berubah → nilai lama tidak terbaca; dianggap tidak ada agar bisa diisi ulang.
                return None

    def set(self, name: str, value: str) -> None:
        token = self._fernet.encrypt(value.encode("utf-8")).decode("ascii")
        with self.db.session() as s:
            row = s.execute(select(Secret).where(Secret.name == name)).scalar_one_or_none()
            if row is None:
                s.add(Secret(name=name, value_encrypted=token))
            else:
                row.value_encrypted = token

    def delete(self, name: str) -> None:
        with self.db.session() as s:
            row = s.execute(select(Secret).where(Secret.name == name)).scalar_one_or_none()
            if row is not None:
                s.delete(row)
