"""Login satu kata sandi (mode online, keputusan K-2 rencana online).

- Kata sandi disimpan sebagai hash scrypt (stdlib) di app_meta — tidak pernah teks asli.
- Sesi: token acak 256-bit; yang disimpan hanya SHA-256-nya. Cookie HttpOnly+Secure+SameSite=Lax.
- Setup/reset lewat ZOI_SETUP_TOKEN (dari environment Render) — bukan endpoint terbuka.
- Pembatas percobaan global: setelah MAX_ATTEMPTS gagal, login ditahan WINDOW_S detik (satu pengguna,
  jadi pembatas global cukup dan tidak bisa diakali lewat banyak alamat IP).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets as pysecrets
import time
from datetime import timedelta

from sqlalchemy import delete, select

from app.db.base import utcnow
from app.db.models import AppMeta, AuthSession
from app.db.session import Database

PASSWORD_KEY = "auth:password"  # noqa: S105 — nama kunci app_meta, bukan kata sandi. Isi: {"salt","hash"} (b64)
SESSION_COOKIE = "zoi_session"
SESSION_DAYS = 30
MIN_PASSWORD = 8
MAX_ATTEMPTS = 10
WINDOW_S = 15 * 60


def _scrypt(password: str, salt: bytes) -> bytes:
    return hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1, dklen=32)


class AuthError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class AuthService:
    def __init__(self, db: Database, setup_token: str, *, enabled: bool = True) -> None:
        self.db = db
        self._setup_token = setup_token
        self.enabled = enabled
        self._failures: list[float] = []  # waktu percobaan gagal (monotonic)

    # ── status ────────────────────────────────────────────────────────────
    def has_password(self) -> bool:
        with self.db.session() as s:
            return s.get(AppMeta, PASSWORD_KEY) is not None

    def status(self) -> dict:
        return {"enabled": self.enabled, "ready": self.has_password() if self.enabled else True}

    # ── setup / reset ─────────────────────────────────────────────────────
    def setup(self, token: str, password: str) -> str:
        if not self._setup_token or not hmac.compare_digest(token, self._setup_token):
            raise AuthError("setup_token_salah", "Setup token tidak cocok. Lihat nilai ZOI_SETUP_TOKEN di Render.")
        if len(password) < MIN_PASSWORD:
            raise AuthError("kata_sandi_pendek", f"Kata sandi minimal {MIN_PASSWORD} karakter.")
        salt = pysecrets.token_bytes(16)
        payload = {"salt": base64.b64encode(salt).decode("ascii"),
                   "hash": base64.b64encode(_scrypt(password, salt)).decode("ascii")}
        with self.db.session() as s:
            row = s.get(AppMeta, PASSWORD_KEY)
            if row is None:
                s.add(AppMeta(key=PASSWORD_KEY, value_json=json.dumps(payload)))
            else:
                row.value_json = json.dumps(payload)
            s.execute(delete(AuthSession))  # ganti kata sandi → semua sesi lama keluar
        self._failures.clear()
        return self._create_session()

    # ── login / logout ────────────────────────────────────────────────────
    def login(self, password: str) -> str:
        now = time.monotonic()
        self._failures = [t for t in self._failures if now - t < WINDOW_S]
        if len(self._failures) >= MAX_ATTEMPTS:
            raise AuthError("terkunci", "Terlalu banyak percobaan gagal. Coba lagi dalam 15 menit.")
        with self.db.session() as s:
            row = s.get(AppMeta, PASSWORD_KEY)
        if row is None:
            raise AuthError("belum_setup", "Kata sandi belum dibuat. Buka halaman setup dahulu.")
        data = json.loads(row.value_json)
        expected = base64.b64decode(data["hash"])
        got = _scrypt(password, base64.b64decode(data["salt"]))
        if not hmac.compare_digest(expected, got):
            self._failures.append(now)
            raise AuthError("kata_sandi_salah", "Kata sandi salah.")
        self._failures.clear()
        return self._create_session()

    def _create_session(self) -> str:
        token = pysecrets.token_urlsafe(32)
        with self.db.session() as s:
            s.add(AuthSession(token_hash=hashlib.sha256(token.encode("ascii")).hexdigest(),
                              expires_at=utcnow() + timedelta(days=SESSION_DAYS)))
        return token

    def check(self, token: str | None) -> bool:
        """Benar bila token sesi sah dan belum kedaluwarsa. Mode nonaktif → selalu benar."""
        if not self.enabled:
            return True
        if not token:
            return False
        digest = hashlib.sha256(token.encode("ascii")).hexdigest()
        with self.db.session() as s:
            row = s.execute(select(AuthSession).where(AuthSession.token_hash == digest)).scalar_one_or_none()
            if row is None:
                return False
            if row.expires_at <= utcnow():
                s.delete(row)
                return False
            return True

    def logout(self, token: str | None) -> None:
        if not token:
            return
        digest = hashlib.sha256(token.encode("ascii")).hexdigest()
        with self.db.session() as s:
            s.execute(delete(AuthSession).where(AuthSession.token_hash == digest))

    def logout_all(self) -> None:
        with self.db.session() as s:
            s.execute(delete(AuthSession))
