"""Engine & sesi database.

- development/local: satu file SQLite di dalam ZOI_DATA_DIR.
- online: Postgres (Neon) lewat ZOI_DATABASE_URL. Sambungan selalu memakai TLS kecuali ke komputer ini sendiri
  (tes). Database gratis tertidur saat tidak dipakai, jadi sambungan diperiksa dulu sebelum dipakai.
"""

from __future__ import annotations

import ssl
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import unquote, urlparse

from sqlalchemy import URL, Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

DB_FILENAME = "zoi.db"
LOOPBACK = {"127.0.0.1", "localhost", "::1"}


def db_path(data_dir: Path) -> Path:
    return data_dir / DB_FILENAME


def make_engine(path: Path) -> Engine:
    path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{path.as_posix()}", connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _pragmas(dbapi_conn, _record):  # type: ignore[no-untyped-def]
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()

    return engine


def postgres_url(database_url: str) -> tuple[URL, dict[str, object]]:
    """ZOI_DATABASE_URL → URL SQLAlchemy (penghubung pg8000) + argumen sambungan. Parameter kueri diabaikan."""
    parsed = urlparse(database_url)
    host = parsed.hostname or ""
    url = URL.create("postgresql+pg8000", username=unquote(parsed.username or ""),
                     password=unquote(parsed.password or ""), host=host, port=parsed.port or 5432,
                     database=unquote(parsed.path.lstrip("/")))
    args: dict[str, object] = {"timeout": 30}
    if host not in LOOPBACK:
        args["ssl_context"] = ssl.create_default_context()  # verifikasi sertifikat + nama host
    return url, args


def make_postgres_engine(database_url: str) -> Engine:
    url, args = postgres_url(database_url)
    return create_engine(url, connect_args=args, pool_pre_ping=True, pool_recycle=240, pool_size=5, max_overflow=5)


class Database:
    def __init__(self, path: Path | None = None, *, url: str = "") -> None:
        if not url and path is None:
            raise ValueError("Database membutuhkan path SQLite atau alamat Postgres.")
        self.path = path
        self.engine = make_postgres_engine(url) if url else make_engine(path)  # type: ignore[arg-type]
        self.dialect = self.engine.dialect.name  # "sqlite" | "postgresql"
        self._factory = sessionmaker(self.engine, expire_on_commit=False)

    @contextmanager
    def session(self) -> Iterator[Session]:
        session = self._factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def dispose(self) -> None:
        self.engine.dispose()
