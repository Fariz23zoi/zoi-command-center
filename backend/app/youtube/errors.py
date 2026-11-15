from __future__ import annotations

from app.core.errors import ZoiError


class YouTubeError(ZoiError):
    """Kegagalan YouTube yang dilaporkan apa adanya (Bahasa Indonesia)."""

    def __init__(self, message: str, *, status_code: int = 400, code: str = "youtube_error") -> None:
        super().__init__(message, status_code=status_code, code=code)


class QuotaExceeded(YouTubeError):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=429, code="quota_exceeded")


class NeedsReauth(YouTubeError):
    DEFAULT = "Izin YouTube sudah tidak berlaku. Hubungkan ulang akun di Settings › YouTube."

    def __init__(self, message: str = DEFAULT) -> None:
        super().__init__(message, status_code=409, code="needs_reauth")
