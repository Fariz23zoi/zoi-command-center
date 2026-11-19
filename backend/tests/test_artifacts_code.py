"""Artefak (HTML satu file, sandbox) dan Code (agen pemrograman dengan izin per perintah)."""

from __future__ import annotations

import json

import pytest

from tests.conftest import wait_for


class _Fake:
    name = "nvidia"
    is_mock = False

    def __init__(self, replies):
        self.replies = list(replies)
        self.seen = []

    async def chat(self, messages, tools=None, timeout_s=0, options=None):
        from app.providers.base import ChatChunk
        self.seen.append(list(messages))
        yield ChatChunk(type="text", text=self.replies.pop(0))
        yield ChatChunk(type="done")


PAGE = "<!DOCTYPE html><html><head><title>Kalkulator BMI</title></head><body><h1>BMI</h1></body></html>"


def _task_done(client, task_id):
    return wait_for(lambda: (t := client.get(f"/api/tasks/{task_id}").json())["status"] in
                    ("COMPLETED", "FAILED", "CANCELLED") and t)


# ── Artefak ──────────────────────────────────────────────────────────────
def test_artifact_generate_revise_serve_undo(client):
    ctx = client.app.state.zoi
    ctx.artifacts.provider = _Fake([f"Berikut:\n```html\n{PAGE}\n```", PAGE.replace("BMI</h1>", "BMI v2</h1>")])
    task = client.post("/api/artifacts/generate", json={"permintaan": "buat kalkulator BMI"}).json()
    done = _task_done(client, task["id"])
    assert done["status"] == "COMPLETED", done
    aid = done["result"]["artifact_id"]
    meta = client.get(f"/api/artifacts/{aid}").json()
    assert meta["judul"] == "Kalkulator BMI" and meta["versi"] == 1 and meta["sumber"] == "ai"

    raw = client.get(f"/artefak-raw/{aid}/")
    assert raw.status_code == 200
    csp = raw.headers["content-security-policy"]
    assert csp.startswith("sandbox allow-scripts") and "allow-same-origin" not in csp
    assert "connect-src data: blob:" in csp
    assert raw.text.index("ZOI: jembatan artefak") < raw.text.index("<h1>BMI")

    task = client.post("/api/artifacts/generate", json={"permintaan": "tambah v2", "artifact_id": aid}).json()
    assert _task_done(client, task["id"])["status"] == "COMPLETED"
    assert "BMI v2" in client.get(f"/artefak-raw/{aid}/").text
    assert PAGE in ctx.artifacts.provider.seen[1][1].content  # revisi mengirim file lama
    assert client.post(f"/api/artifacts/{aid}/undo").json()["versi"] == 1
    assert "BMI v2" not in client.get(f"/artefak-raw/{aid}/").text
    dl = client.get(f"/api/artifacts/{aid}/html")
    assert dl.headers["content-disposition"].endswith('kalkulator-bmi.html"') and "ZOI: jembatan" not in dl.text


def test_artifact_upload_list_delete_and_bad_ai(client):
    up = client.post("/api/artifacts", json={"html": PAGE, "judul": "Dari Claude"}).json()
    assert up["sumber"] == "unggah" and up["judul"] == "Dari Claude"
    assert [i["id"] for i in client.get("/api/artifacts").json()["items"]] == [up["id"]]
    assert client.post("/api/artifacts", json={"html": "x" * 20}).status_code == 400
    assert client.get("/artefak-raw/../etc/").status_code == 404
    client.app.state.zoi.artifacts.provider = _Fake(["maaf saya tidak bisa"])
    task = client.post("/api/artifacts/generate", json={"permintaan": "apa saja"}).json()
    failed = _task_done(client, task["id"])
    assert failed["status"] == "FAILED" and "HTML" in failed["error"]
    assert client.delete(f"/api/artifacts/{up['id']}").status_code == 200
    assert client.get(f"/api/artifacts/{up['id']}").status_code == 404


def test_artifact_sample_json_and_text(client):
    client.app.state.zoi.artifacts.provider = _Fake(['{"a": 1}', "halo"])
    assert client.post("/api/artifacts/sample", json={"prompt": "p"}).json()["result"] == {"a": 1}
    assert client.post("/api/artifacts/sample", json={"prompt": "p", "mode": "text"}).json()["result"] == "halo"


def test_artifacts_and_code_disabled_online(client_factory):
    from app.artifacts import ArtifactError, ArtifactService
    from app.code_agent import CodeError, CodeService
    with pytest.raises(ArtifactError):
        ArtifactService(data_dir=client_factory().app.state.zoi.runtime.data_dir, provider=None,
                        available=False).list()
    with pytest.raises(CodeError):
        CodeService(data_dir=client_factory().app.state.zoi.runtime.data_dir, provider=None, available=False).projects()


# ── Code ─────────────────────────────────────────────────────────────────
def test_workspace_rejects_escape(tmp_path):
    from app.code_agent import CodeError, Workspace
    ws = Workspace(tmp_path)
    for bad in ("../x", "/etc/passwd", "C:/Windows/x", "a/../../x", ".zoi/cadangan/x"):
        with pytest.raises(CodeError):
            ws.path(bad)
    assert ws.write("src/a.py", "print(1)\n").startswith("Dibuat")
    assert ws.replace("src/a.py", "print(1)", "print(2)") == "Diganti di src/a.py."
    assert (tmp_path / ".zoi" / "cadangan").is_dir()
    with pytest.raises(CodeError):
        ws.replace("src/a.py", "tidak ada", "x")
    with pytest.raises(CodeError):
        ws.run("shutdown /s /t 0")


def test_code_session_writes_asks_permission_and_runs(client):
    ctx = client.app.state.zoi
    assert client.post("/api/code/projects", json={"name": "Halo Dunia"}).json()["name"] == "halo-dunia"
    steps = [
        {"pikir": "buat file", "alat": "tulis", "args": {"path": "halo.py", "isi": "print('halo zoi')\n"}},
        {"pikir": "uji", "alat": "jalankan", "args": {"perintah": "python3 halo.py"}},
        {"pikir": "beres", "selesai": "File halo.py dibuat dan diuji."},
    ]
    ctx.code.provider = _Fake([json.dumps(s) for s in steps])
    sess = client.post("/api/code/sessions", json={"project": "halo-dunia", "perintah": "buat skrip halo"}).json()
    sid = sess["id"]
    waiting = wait_for(lambda: (s := client.get(f"/api/code/sessions/{sid}").json())["status"] == "waiting" and s)
    assert waiting["pending"] == {"alat": "jalankan", "args": {"perintah": "python3 halo.py"}}
    assert (ctx.runtime.data_dir / "kode" / "halo-dunia" / "halo.py").is_file()  # tulis tanpa izin, di dalam proyek
    client.post(f"/api/code/sessions/{sid}/izin", json={"setuju": True})
    final = wait_for(lambda: (s := client.get(f"/api/code/sessions/{sid}").json())["status"] == "done" and s)
    hasil = [s for s in final["steps"] if s["jenis"] == "hasil" and s["alat"] == "jalankan"][0]
    assert "halo zoi" in hasil["teks"] and "Kode keluar: 0" in hasil["teks"]
    assert final["steps"][-1]["teks"] == "File halo.py dibuat dan diuji."
    files = client.get("/api/code/projects/halo-dunia/files").json()["items"]
    assert [f["path"] for f in files] == ["halo.py"]
    assert client.get("/api/code/projects/halo-dunia/zip").headers["content-type"] == "application/zip"


def test_code_session_refusal_is_reported(client):
    ctx = client.app.state.zoi
    client.post("/api/code/projects", json={"name": "p2"})
    ctx.code.provider = _Fake([json.dumps({"alat": "hapus", "args": {"path": "x.txt"}}),
                               json.dumps({"selesai": "Tidak jadi menghapus."})])
    sid = client.post("/api/code/sessions", json={"project": "p2", "perintah": "hapus x"}).json()["id"]
    wait_for(lambda: client.get(f"/api/code/sessions/{sid}").json()["status"] == "waiting")
    client.post(f"/api/code/sessions/{sid}/izin", json={"setuju": False})
    final = wait_for(lambda: (s := client.get(f"/api/code/sessions/{sid}").json())["status"] == "done" and s)
    assert any(s["jenis"] == "ditolak" for s in final["steps"])
    assert "MENOLAK" in ctx.code.provider.seen[1][-1].content
