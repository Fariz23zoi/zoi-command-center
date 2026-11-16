"""Jalankan ZOI:  python -m app   (dari folder backend)."""

from __future__ import annotations

import sys

import uvicorn

from app.config.modes import ConfigError, resolve_runtime
from app.config.settings import load_settings
from app.system.detectors import port_available, port_owner


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    try:
        settings = load_settings()
        runtime = resolve_runtime(settings)
    except ConfigError as exc:
        print(f"[ZOI] Konfigurasi salah: {exc}", file=sys.stderr)
        return 2
    if not port_available(runtime.host, runtime.port):
        owner = port_owner(runtime.port)
        print(f"[ZOI] Port {runtime.port} sudah dipakai" + (f" oleh {owner}" if owner else "") + ".",
              file=sys.stderr)
        alt = 8001 if runtime.port == 8000 else 8000
        print(f"[ZOI] ZOI tidak mematikan program lain. Hentikan program itu, atau set ZOI_PORT={alt} di .env.",
              file=sys.stderr)
        return 3
    from app.main import create_app

    print(f"[ZOI] Mode {runtime.mode.value} — membuka {runtime.base_url}")
    uvicorn.run(create_app(settings), host=runtime.host, port=runtime.port, log_level="warning",
                proxy_headers=False, server_header=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
