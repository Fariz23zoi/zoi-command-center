"""API Artefak (halaman HTML satu file) dan Code (agen pemrograman). Hanya di ZOI lokal."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, ConfigDict, Field

from app.context import AppContext, get_ctx

router = APIRouter(tags=["artefak", "code"])


class _Body(BaseModel):
    model_config = ConfigDict(extra="forbid")


class GenerateBody(_Body):
    permintaan: str = Field(min_length=3, max_length=8000)
    artifact_id: str | None = Field(default=None, max_length=32)


class UploadBody(_Body):
    judul: str = Field(default="", max_length=120)
    html: str = Field(min_length=10, max_length=2_200_000)


class RenameBody(_Body):
    judul: str = Field(min_length=1, max_length=120)


class SampleBody(_Body):
    prompt: str = Field(min_length=1, max_length=30000)
    mode: Literal["json", "text"] = "json"


@router.get("/artifacts")
def list_artifacts(ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    return {"items": ctx.artifacts.list()}


@router.post("/artifacts/generate")
def generate(body: GenerateBody, ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    ctx.artifacts.list()  # mode online → 404 jujur
    if body.artifact_id:
        ctx.artifacts.get(body.artifact_id)
    return ctx.tasks.submit("artifact_generate", {"permintaan": body.permintaan, "artifact_id": body.artifact_id},
                            name=f"Artefak: {body.permintaan[:60]}")


@router.post("/artifacts")
def upload(body: UploadBody, ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    return ctx.artifacts.save(body.html, judul=body.judul, sumber="unggah")


@router.get("/artifacts/{artifact_id}")
def get_artifact(artifact_id: str, ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    return ctx.artifacts.get(artifact_id)


@router.get("/artifacts/{artifact_id}/html")
def download_html(artifact_id: str, ctx: AppContext = Depends(get_ctx)) -> Response:
    meta = ctx.artifacts.get(artifact_id)
    name = "".join(c if c.isalnum() or c in "-_" else "-" for c in meta["judul"].lower())[:50].strip("-") or "artefak"
    return Response(ctx.artifacts.html(artifact_id), media_type="application/octet-stream",
                    headers={"Content-Disposition": f'attachment; filename="{name}.html"'})


@router.put("/artifacts/{artifact_id}")
def rename(artifact_id: str, body: RenameBody, ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    return ctx.artifacts.rename(artifact_id, body.judul)


@router.post("/artifacts/{artifact_id}/undo")
def undo(artifact_id: str, ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    return ctx.artifacts.undo(artifact_id)


@router.delete("/artifacts/{artifact_id}")
def delete(artifact_id: str, ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    ctx.artifacts.delete(artifact_id)
    return {"deleted": artifact_id}


@router.post("/artifacts/sample")
async def sample(body: SampleBody, ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    """Dipanggil penampil ZOI atas nama artefak (window.claude.use("sample"))."""
    return await ctx.artifacts.sample(body.prompt, body.mode)


# ── Code ─────────────────────────────────────────────────────────────────
class ProjectBody(_Body):
    name: str = Field(min_length=1, max_length=40)


class FileBody(_Body):
    path: str = Field(min_length=1, max_length=300)
    content: str = Field(max_length=2_100_000)


class StartBody(_Body):
    project: str = Field(min_length=1, max_length=40)
    perintah: str = Field(min_length=1, max_length=8000)
    session_id: str | None = Field(default=None, max_length=32)


class DecideBody(_Body):
    setuju: bool
    semua: bool = False


@router.get("/code/projects")
def projects(ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    return {"items": ctx.code.projects()}


@router.post("/code/projects")
def create_project(body: ProjectBody, ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    return ctx.code.create(body.name)


@router.delete("/code/projects/{name}")
def delete_project(name: str, ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    ctx.code.delete_project(name)
    return {"deleted": name}


@router.get("/code/projects/{name}/files")
def files(name: str, ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    return {"items": ctx.code.workspace(name).files()}


@router.get("/code/projects/{name}/file")
def read_file(name: str, path: str = Query(max_length=300), ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    from app.code_agent import MAX_FILE_READ, CodeError
    p = ctx.code.workspace(name).path(path)
    if not p.is_file():
        raise CodeError("File tidak ada.", 404, "code_not_found")
    if p.stat().st_size > MAX_FILE_READ:
        raise CodeError("File terlalu besar untuk ditampilkan.", 413, "code_too_large")
    raw = p.read_bytes()
    try:
        return {"path": path, "content": raw.decode("utf-8"), "binary": False}
    except UnicodeDecodeError:
        return {"path": path, "content": "", "binary": True}


@router.put("/code/projects/{name}/file")
def write_file(name: str, body: FileBody, ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    return {"message": ctx.code.workspace(name).write(body.path, body.content)}


@router.get("/code/projects/{name}/zip")
def download_zip(name: str, ctx: AppContext = Depends(get_ctx)) -> Response:
    return Response(ctx.code.zip(name), media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="{name}.zip"'})


@router.post("/code/sessions")
def start_session(body: StartBody, ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    return ctx.code.start(body.project, body.perintah, ctx.tasks, body.session_id)


@router.get("/code/sessions/{session_id}")
def get_session(session_id: str, ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    return ctx.code.session(session_id).public()


@router.post("/code/sessions/{session_id}/izin")
def decide(session_id: str, body: DecideBody, ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    return ctx.code.decide(session_id, body.setuju, body.semua)


@router.post("/code/sessions/{session_id}/stop")
def stop(session_id: str, ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    sess = ctx.code.session(session_id)
    if sess.task_id:
        ctx.tasks.cancel(sess.task_id)
    return sess.public()
