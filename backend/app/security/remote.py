"""Akses dari HP lewat Tailscale Serve (mode local, ADR 0015).

Tailscale Serve hanya terjangkau perangkat di tailnet pemilik dan menambahkan header identitas
`Tailscale-User-Login` (salinan palsu dari klien dihapus oleh Serve). Bila permintaan datang lewat alamat
.ts.net, ZOI mewajibkan header itu — dan bila ZOI_REMOTE_USER diisi, login-nya harus sama persis.
"""

from __future__ import annotations

from collections.abc import Mapping

from app.config.modes import RuntimeConfig

IDENTITY_HEADER = "tailscale-user-login"


def remote_denied(runtime: RuntimeConfig, headers: Mapping[str, str]) -> str | None:
    """Alasan penolakan (teks), atau None bila diizinkan. Permintaan lokal (bukan lewat .ts.net) selalu boleh."""
    remote_host = runtime.remote_host
    if not remote_host:
        return None
    host = (headers.get("host") or "").split(":")[0].lower()
    if host != remote_host:
        return None
    login = (headers.get(IDENTITY_HEADER) or "").strip().lower()
    if not login:
        return "Akses lewat Tailscale butuh identitas Tailscale. Buka dari perangkat yang masuk ke tailnet-mu."
    if runtime.remote_user and login != runtime.remote_user:
        return "Akun Tailscale ini tidak diizinkan membuka ZOI."
    return None
