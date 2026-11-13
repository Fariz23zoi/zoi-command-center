"""Format error API seragam dengan pesan ramah berbahasa Indonesia."""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse


class ZoiError(Exception):
    status_code = 400
    code = "zoi_error"

    def __init__(self, message: str, *, status_code: int | None = None, code: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        if code is not None:
            self.code = code


class NotFound(ZoiError):
    status_code = 404
    code = "not_found"


async def zoi_error_handler(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, ZoiError)
    return JSONResponse(status_code=exc.status_code, content={"error": {"code": exc.code, "message": exc.message}})
