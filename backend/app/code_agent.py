"""Code ZOI — agen pemrograman berulang ala Claude Code, memakai AI Brain ZOI (gratis).

Keamanan (ADR 0019):
* Agen hanya bisa menyentuh folder proyek di `<data>/kode/<proyek>/` — jalur absolut, `..`, dan symlink keluar ditolak.
* Membaca/menulis file di folder proyek berjalan otomatis (setiap tulis disalin dulu ke `.zoi/cadangan/`).
* MENJALANKAN PERINTAH dan MENGHAPUS FILE selalu menunggu izin pengguna (bisa "izinkan semua di sesi ini").
  Perintah berjalan di folder proyek, batas waktu, tanpa variabel rahasia ZOI_*/token/kunci.
* Tidak tersedia di mode online (server publik).
"""

from __future__ import annotations

import io
import json
import os
import platform
import re
import shutil
import subprocess
import threading
import time
import uuid
import zipfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

from app.ai.structured import extract_json
from app.core.errors import ZoiError
from app.providers.base import ChatMessage, LLMProvider
from app.tasks.manager import TaskContext, TaskKind

NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,39}$")
SKIP_DIRS = {".zoi", ".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build", ".next"}
MAX_STEPS = 30
MAX_FILE_READ = 512 * 1024
MAX_FILE_WRITE = 2 * 1024 * 1024
OUTPUT_LIMIT = 6000
CMD_TIMEOUT_S = 180
APPROVAL_TIMEOUT_S = 900
HISTORY_CHARS = 40000
SECRET_ENV = re.compile(r"^ZOI_|KEY|TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIAL", re.IGNORECASE)
DENY_CMD = re.compile(r"\b(format|shutdown|diskpart|bcdedit|reg\s+(add|delete)|cipher\s+/w|mkfs|dd\s+if=)\b|"
                      r"rm\s+-rf\s+/(\s|$)|del\s+/[sq].*[a-z]:\\|rmdir\s+/s.*[a-z]:\\", re.IGNORECASE)
NEEDS_APPROVAL = {"jalankan", "hapus"}


class CodeError(ZoiError):
    def __init__(self, message: str, status_code: int = 400, code: str = "code_error") -> None:
        super().__init__(message, status_code=status_code, code=code)


def system_prompt(project: str) -> str:
    shell = "cmd.exe (Windows)" if platform.system() == "Windows" else "sh (Linux/macOS)"
    return f"""Kamu ZOI Code, insinyur perangkat lunak yang bekerja di folder proyek "{project}".
Kamu bekerja langkah demi langkah memakai ALAT. Setiap balasan HANYA satu objek JSON, tanpa teks lain:
{{"pikir": "rencana singkat langkah ini", "alat": "<nama>", "args": {{...}}}}
atau bila tugas selesai / perlu bertanya ke pengguna:
{{"pikir": "...", "selesai": "ringkasan untuk pengguna: apa yang dikerjakan, file yang diubah, cara menjalankan"}}

ALAT:
- daftar {{"path": "."}} — isi folder (jalur relatif terhadap proyek).
- baca {{"path": "a.py", "mulai": 1, "jumlah": 300}} — baca file bernomor baris.
- tulis {{"path": "a.py", "isi": "..."}} — buat/timpa file utuh.
- ganti {{"path": "a.py", "lama": "teks persis", "baru": "teks baru"}} — ganti satu potongan unik
  (lebih hemat dari tulis).
- cari {{"teks": "kata"}} — cari teks di semua file proyek.
- jalankan {{"perintah": "python a.py"}} — jalankan perintah shell {shell} di folder proyek (butuh izin pengguna,
  batas {CMD_TIMEOUT_S} detik, jangan perintah interaktif/server yang tidak berhenti).
- hapus {{"path": "a.py"}} — hapus file (butuh izin pengguna).
Aturan: jalur selalu relatif di dalam proyek. Baca dulu sebelum mengubah file yang sudah ada. Perubahan kecil pakai
"ganti". Uji hasilmu dengan "jalankan" bila masuk akal. Jangan memasang paket besar atau layanan berbayar tanpa
alasan jelas — sebutkan di ringkasan bila perlu dipasang. Jawab pengguna dalam bahasa Indonesia, singkat."""


class Workspace:
    """Folder proyek yang aman diakses agen."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def path(self, rel: str) -> Path:
        rel = (rel or ".").replace("\\", "/").strip()
        if rel.startswith("/") or re.match(r"^[A-Za-z]:", rel) or ".." in rel.split("/"):
            raise CodeError(f"Jalur harus relatif di dalam proyek: {rel}")
        target = (self.root / rel).resolve()
        if target != self.root and self.root not in target.parents:
            raise CodeError(f"Jalur keluar dari folder proyek: {rel}")
        if ".zoi" in target.relative_to(self.root).parts:
            raise CodeError("Folder .zoi milik ZOI, tidak boleh diubah.")
        return target

    def rel(self, path: Path) -> str:
        return path.relative_to(self.root).as_posix() or "."

    def files(self, limit: int = 2000) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for dirpath, dirnames, filenames in os.walk(self.root):
            dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
            for name in sorted(filenames):
                p = Path(dirpath) / name
                out.append({"path": self.rel(p), "bytes": p.stat().st_size})
                if len(out) >= limit:
                    return out
        return out

    def listing(self, rel: str) -> str:
        folder = self.path(rel)
        if not folder.is_dir():
            raise CodeError(f"Bukan folder: {rel}")
        rows = []
        for p in sorted(folder.iterdir(), key=lambda x: (x.is_file(), x.name.lower())):
            if p.name == ".zoi":
                continue
            rows.append(f"{p.name}/" if p.is_dir() else f"{p.name}  ({p.stat().st_size} B)")
        return "\n".join(rows[:300]) or "(kosong)"

    def read(self, rel: str, start: int = 1, count: int = 300) -> str:
        p = self.path(rel)
        if not p.is_file():
            raise CodeError(f"File tidak ada: {rel}")
        if p.stat().st_size > MAX_FILE_READ:
            raise CodeError(f"File terlalu besar untuk dibaca ({p.stat().st_size} B).")
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        start = max(1, start)
        chunk = lines[start - 1: start - 1 + max(1, min(count, 600))]
        body = "\n".join(f"{i:5d}| {line}" for i, line in enumerate(chunk, start))
        more = f"\n… ({len(lines)} baris total)" if start - 1 + len(chunk) < len(lines) else ""
        return (body or "(file kosong)") + more

    def backup(self, p: Path) -> None:
        if p.is_file():
            dest = self.root / ".zoi" / "cadangan" / f"{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:4]}"
            dest.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, dest / p.name)

    def write(self, rel: str, content: str) -> str:
        if len(content.encode("utf-8")) > MAX_FILE_WRITE:
            raise CodeError("Isi file terlalu besar (maks 2 MB).")
        p = self.path(rel)
        if p == self.root or p.is_dir():
            raise CodeError("Jalur menunjuk folder, bukan file.")
        self.backup(p)
        p.parent.mkdir(parents=True, exist_ok=True)
        existed = p.exists()
        p.write_text(content, encoding="utf-8", newline="")
        return f"{'Diperbarui' if existed else 'Dibuat'}: {rel} ({len(content.splitlines())} baris)"

    def replace(self, rel: str, old: str, new: str) -> str:
        p = self.path(rel)
        if not p.is_file():
            raise CodeError(f"File tidak ada: {rel}")
        text = p.read_text(encoding="utf-8", errors="replace")
        count = text.count(old) if old else 0
        if count != 1:
            raise CodeError(f"Teks 'lama' harus muncul tepat 1 kali di {rel} (ditemukan {count}). Baca file dulu.")
        self.backup(p)
        p.write_text(text.replace(old, new, 1), encoding="utf-8", newline="")
        return f"Diganti di {rel}."

    def search(self, needle: str) -> str:
        if not needle.strip():
            raise CodeError("Teks pencarian kosong.")
        hits: list[str] = []
        low = needle.lower()
        for item in self.files():
            p = self.root / item["path"]
            if item["bytes"] > MAX_FILE_READ:
                continue
            try:
                for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
                    if low in line.lower():
                        hits.append(f"{item['path']}:{n}: {line.strip()[:160]}")
                        if len(hits) >= 60:
                            return "\n".join(hits) + "\n… (dipotong)"
            except (UnicodeDecodeError, OSError):
                continue
        return "\n".join(hits) or "Tidak ditemukan."

    def delete(self, rel: str) -> str:
        p = self.path(rel)
        if p == self.root or not p.is_file():
            raise CodeError(f"Hanya file yang bisa dihapus: {rel}")
        self.backup(p)
        p.unlink()
        return f"Dihapus: {rel} (cadangan di .zoi/cadangan)"

    def run(self, command: str) -> str:
        if DENY_CMD.search(command):
            raise CodeError("Perintah ini diblokir ZOI karena bisa merusak sistem.")
        env = {k: v for k, v in os.environ.items() if not SECRET_ENV.search(k)}
        env["PYTHONIOENCODING"] = "utf-8"
        try:
            proc = subprocess.run(command, shell=True, cwd=self.root, env=env, capture_output=True,  # noqa: S602
                                  timeout=CMD_TIMEOUT_S, stdin=subprocess.DEVNULL)
        except subprocess.TimeoutExpired:
            return f"Perintah dihentikan: melebihi {CMD_TIMEOUT_S} detik."
        out = (proc.stdout + proc.stderr).decode("utf-8", errors="replace")
        if len(out) > OUTPUT_LIMIT:
            out = "… (awal dipotong)\n" + out[-OUTPUT_LIMIT:]
        return f"Kode keluar: {proc.returncode}\n{out.strip() or '(tanpa keluaran)'}"


class Session:
    def __init__(self, project: str) -> None:
        self.id = uuid.uuid4().hex[:12]
        self.project = project
        self.status = "idle"
        self.steps: list[dict[str, Any]] = []
        self.history: list[ChatMessage] = []
        self.pending: dict[str, Any] | None = None
        self.allow_all = False
        self.decision: bool | None = None
        self.event = threading.Event()
        self.task_id: str | None = None
        self.provider: str | None = None
        self.updated = time.time()

    def add(self, kind: str, **data: Any) -> None:
        self.steps.append({"jenis": kind, "waktu": round(time.time(), 2), **data})
        self.steps = self.steps[-400:]
        self.updated = time.time()

    def public(self) -> dict[str, Any]:
        return {"id": self.id, "project": self.project, "status": self.status, "steps": self.steps,
                "pending": self.pending, "allow_all": self.allow_all, "task_id": self.task_id,
                "provider": self.provider}


class CodeService:
    def __init__(self, *, data_dir: Path, provider: LLMProvider, available: bool = True) -> None:
        self.root = data_dir / "kode"
        self.provider = provider
        self.available = available
        self.sessions: dict[str, Session] = {}
        self._lock = threading.Lock()

    # ── proyek ────────────────────────────────────────────────────────────
    def _require(self) -> None:
        if not self.available:
            raise CodeError("Code hanya tersedia di ZOI lokal (laptop), bukan mode online.", 404, "code_unavailable")

    def workspace(self, name: str) -> Workspace:
        self._require()
        if not NAME_RE.fullmatch(name or ""):
            raise CodeError("Nama proyek tidak valid.", 404, "code_not_found")
        folder = self.root / name
        if not folder.is_dir():
            raise CodeError("Proyek tidak ditemukan.", 404, "code_not_found")
        return Workspace(folder)

    def projects(self) -> list[dict[str, Any]]:
        self._require()
        if not self.root.is_dir():
            return []
        out = []
        for folder in sorted(self.root.iterdir()):
            if folder.is_dir() and NAME_RE.fullmatch(folder.name):
                files = Workspace(folder).files(limit=5000)
                out.append({"name": folder.name, "files": len(files), "updated": folder.stat().st_mtime})
        return sorted(out, key=lambda p: p["updated"], reverse=True)

    def create(self, name: str) -> dict[str, Any]:
        self._require()
        slug = re.sub(r"[^a-z0-9-]+", "-", name.strip().lower()).strip("-")[:40]
        if not NAME_RE.fullmatch(slug):
            raise CodeError("Nama proyek: huruf kecil, angka, dan tanda minus.")
        folder = self.root / slug
        if folder.exists():
            raise CodeError("Proyek dengan nama itu sudah ada.", 409, "code_exists")
        folder.mkdir(parents=True)
        return {"name": slug, "files": 0, "updated": folder.stat().st_mtime}

    def delete_project(self, name: str) -> None:
        ws = self.workspace(name)
        if any(s.project == name and s.status in ("running", "waiting") for s in self.sessions.values()):
            raise CodeError("Hentikan sesi yang sedang berjalan dulu.", 409, "code_busy")
        shutil.rmtree(ws.root)

    def zip(self, name: str) -> bytes:
        ws = self.workspace(name)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for item in ws.files(limit=5000):
                zf.write(ws.root / item["path"], f"{name}/{item['path']}")
        return buf.getvalue()

    # ── sesi agen ─────────────────────────────────────────────────────────
    def session(self, session_id: str) -> Session:
        self._require()
        found = self.sessions.get(session_id)
        if found is None:
            raise CodeError("Sesi tidak ditemukan (mungkin ZOI dimulai ulang).", 404, "code_session_not_found")
        return found

    def start(self, project: str, instruction: str, tasks: Any, session_id: str | None = None) -> dict[str, Any]:
        self.workspace(project)
        with self._lock:
            if session_id:
                sess = self.session(session_id)
                if sess.status in ("running", "waiting"):
                    raise CodeError("Sesi masih berjalan.", 409, "code_busy")
            else:
                sess = Session(project)
                self.sessions[sess.id] = sess
                old = sorted(self.sessions.values(), key=lambda s: s.updated)[:-30]
                for s in old:
                    if s.status not in ("running", "waiting"):
                        self.sessions.pop(s.id, None)
            sess.status = "running"
            sess.add("pengguna", teks=instruction)
        task = tasks.submit("code_session", {"session_id": sess.id, "instruction": instruction},
                            name=f"Code: {instruction[:60]}")
        sess.task_id = task["id"]
        return sess.public()

    def decide(self, session_id: str, approve: bool, allow_all: bool = False) -> dict[str, Any]:
        sess = self.session(session_id)
        if sess.status != "waiting" or sess.pending is None:
            raise CodeError("Tidak ada izin yang ditunggu.", 409, "code_no_pending")
        sess.decision = approve
        if approve and allow_all:
            sess.allow_all = True
        sess.event.set()
        return sess.public()

    def _ask(self, sess: Session, ctx: TaskContext) -> bool:
        sess.decision = None
        sess.event.clear()
        sess.status = "waiting"
        deadline = time.monotonic() + APPROVAL_TIMEOUT_S
        try:
            while not sess.event.wait(0.3):
                ctx.check_cancelled()
                if time.monotonic() > deadline:
                    return False
            return bool(sess.decision)
        finally:
            sess.status = "running"

    def _trim(self, sess: Session) -> None:
        total = sum(len(m.content) for m in sess.history)
        for i in range(2, max(2, len(sess.history) - 6)):
            if total <= HISTORY_CHARS:
                break
            m = sess.history[i]
            if m.role in ("user", "assistant") and len(m.content) > 400 and not m.content.startswith("TUGAS"):
                total -= len(m.content) - 160
                sess.history[i] = ChatMessage(m.role, m.content[:160] + "\n[dipersingkat]")

    async def _next(self, sess: Session) -> dict[str, Any]:
        for attempt in range(2):
            parts: list[str] = []
            async for chunk in self.provider.chat(sess.history, timeout_s=240.0):
                if chunk.type == "text":
                    parts.append(chunk.text)
                elif chunk.type == "error":
                    raise CodeError(chunk.error or "AI ZOI gagal menjawab.", 502, "ai_failed")
                elif chunk.type == "done":
                    sess.provider = chunk.served_by or self.provider.name
                    break
            raw = "".join(parts)
            candidate = extract_json(raw)
            data = json.loads(candidate) if candidate else None
            if isinstance(data, dict) and (data.get("selesai") is not None or data.get("alat")):
                sess.history.append(ChatMessage("assistant", json.dumps(data, ensure_ascii=False)[:6000]))
                return data
            if attempt == 0:
                sess.history.append(ChatMessage("assistant", raw[:1500]))
                sess.history.append(ChatMessage("user", "Format salah. Balas HANYA satu objek JSON berisi "
                                                        "\"alat\"+\"args\" atau \"selesai\"."))
        raise CodeError("AI ZOI tidak memberi langkah yang valid (bukan JSON alat). Coba model lain atau ulangi.",
                        502, "ai_bad_json")

    def _tool(self, ws: Workspace, name: str, args: dict[str, Any]) -> str:
        if name == "daftar":
            return ws.listing(str(args.get("path", ".")))
        if name == "baca":
            return ws.read(str(args["path"]), int(args.get("mulai", 1) or 1), int(args.get("jumlah", 300) or 300))
        if name == "tulis":
            return ws.write(str(args["path"]), str(args.get("isi", "")))
        if name == "ganti":
            return ws.replace(str(args["path"]), str(args["lama"]), str(args.get("baru", "")))
        if name == "cari":
            return ws.search(str(args["teks"]))
        if name == "jalankan":
            return ws.run(str(args["perintah"]))
        if name == "hapus":
            return ws.delete(str(args["path"]))
        raise CodeError(f"Alat tidak dikenal: {name}")

    def task_kind(self, run_async: Callable[..., Any]) -> TaskKind:
        def execute(ctx: TaskContext) -> dict[str, Any]:
            sess = self.session(str(ctx.params["session_id"]))
            ws = self.workspace(sess.project)
            instruction = str(ctx.params["instruction"])
            if not sess.history:
                sess.history = [ChatMessage("system", system_prompt(sess.project))]
            sess.history.append(ChatMessage("user", f"TUGAS:\n{instruction}\n\nFile di proyek saat ini:\n"
                                                    + "\n".join(f["path"] for f in ws.files(limit=200))))
            try:
                for step in range(1, MAX_STEPS + 1):
                    ctx.check_cancelled()
                    ctx.progress(min(95, step * 3), f"Langkah {step}")
                    self._trim(sess)
                    action = run_async(self._next(sess), timeout=300)
                    if action.get("selesai") is not None:
                        sess.add("selesai", teks=str(action["selesai"]), pikir=str(action.get("pikir", "")))
                        sess.status = "done"
                        return {"session_id": sess.id, "steps": step}
                    name = str(action.get("alat"))
                    args = action.get("args") if isinstance(action.get("args"), dict) else {}
                    sess.add("aksi", alat=name, args=_short_args(args), pikir=str(action.get("pikir", ""))[:500])
                    if name in NEEDS_APPROVAL and not sess.allow_all:
                        sess.pending = {"alat": name, "args": _short_args(args)}
                        ok = self._ask(sess, ctx)
                        sess.pending = None
                        if not ok:
                            sess.add("ditolak", alat=name)
                            refused = ("HASIL: Pengguna MENOLAK langkah ini. Jangan ulangi; cari cara lain "
                                       "atau selesai dan jelaskan.")
                            sess.history.append(ChatMessage("user", refused))
                            continue
                    try:
                        result = self._tool(ws, name, args)
                        sess.add("hasil", alat=name, teks=result[:OUTPUT_LIMIT])
                    except (CodeError, KeyError, ValueError, OSError) as exc:
                        result = f"GAGAL: {getattr(exc, 'message', None) or exc}"
                        sess.add("hasil", alat=name, teks=result, gagal=True)
                    sess.history.append(ChatMessage("user", f"HASIL {name}:\n{result[:OUTPUT_LIMIT]}"))
                sess.add("selesai", teks=f"Berhenti setelah {MAX_STEPS} langkah. Tulis 'lanjut' untuk meneruskan.")
                sess.status = "done"
                return {"session_id": sess.id, "steps": MAX_STEPS}
            except Exception as exc:
                cancelled = type(exc).__name__ == "TaskCancelled"
                sess.status = "stopped" if cancelled else "error"
                sess.pending = None
                sess.add("galat", teks="Dihentikan pengguna." if cancelled else str(getattr(exc, "message", exc)))
                raise

        return TaskKind(kind="code_session", name="ZOI Code", func=execute, lane="code")


def _short_args(args: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in args.items():
        text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
        out[str(key)] = text if len(text) <= 4000 else text[:4000] + f"… (+{len(text) - 4000} karakter)"
    return out
