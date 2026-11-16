"""Unduh & pulihkan cadangan data dari Settings (semua mode; penting di hosting gratis yang bisa berubah).

Rahasia (API key, token, sesi login) TIDAK PERNAH ikut arsip.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, Request, Response

from app.context import AppContext, get_ctx
from app.core.errors import ZoiError
from app.db.backup_json import MAX_ARCHIVE_BYTES, BackupError, export_bytes, restore_bytes

router = APIRouter(prefix="/backup", tags=["backup"])


@router.get("/download")
def download(ctx: AppContext = Depends(get_ctx)) -> Response:
    blob, manifest = export_bytes(ctx.db)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return Response(blob, media_type="application/zip", headers={
        "Content-Disposition": f'attachment; filename="zoi-backup-{stamp}.zip"',
        "X-ZOI-Tables": str(sum(manifest["tables"].values())),
    })


@router.post("/restore")
async def restore(request: Request, ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    body = await request.body()
    if not body:
        raise ZoiError("Tidak ada file yang dikirim. Pilih file cadangan ZOI (.zip) dahulu.")
    if len(body) > MAX_ARCHIVE_BYTES:
        raise ZoiError(f"File melebihi {MAX_ARCHIVE_BYTES // (1024 * 1024)} MB.", status_code=413)
    try:
        result = restore_bytes(ctx.db, body)
    except BackupError as exc:
        raise ZoiError(str(exc)) from exc
    ctx.bus.publish("backup.restored", {})
    return {"ok": True, **result,
            "note": "Data dipulihkan. Rahasia (API key, akun YouTube) tidak ikut arsip — hubungkan ulang bila "
                    "perlu. Muat ulang halaman untuk melihat data baru."}
