"""Layanan Produksi Konten (Phase 7, hanya di laptop).

Paket disimpan sebagai FILE di `data/production/<id>/` (bukan database) agar mudah dibawa dan dibuka
aplikasi lain. Nama file yang boleh diunduh dibatasi (FILES); id hanya huruf/angka.
"""

from __future__ import annotations

import io
import json
import re
import secrets
import shutil
import subprocess
import time
import wave
from collections.abc import Callable
from pathlib import Path
from typing import Any

from app.content.package import PackageError, build_package
from app.production.blueprint import BlueprintCopy
from app.production.hyperframes import HyperFrames, compose
from app.tasks.manager import TaskContext, TaskKind

FORMAT = "zoi.paket/v1"
ID_RE = re.compile(r"^[a-f0-9]{12}$")
FILES = {"paket.json": "application/json", "narasi.wav": "audio/wav", "narasi.srt": "application/x-subrip",
         "video.mp4": "video/mp4"}
MAX_BEATS = 40
MAX_TEXT = 4000
GAP_S = 0.3
RENDER_TIMEOUT_S = 60 * 60


class ProductionError(Exception):
    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _clean_text(value: Any, limit: int = MAX_TEXT) -> str:
    return str(value or "")[:limit]


def validate_package(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict) or data.get("format") != FORMAT:
        raise ProductionError(f"Bukan paket ZOI (format harus '{FORMAT}'). Unduh paket dari halaman Naskah.")
    beats = data.get("beats")
    if not isinstance(beats, list) or not beats:
        raise ProductionError("Paket tidak berisi beat.")
    if len(beats) > MAX_BEATS:
        raise ProductionError(f"Paket berisi lebih dari {MAX_BEATS} beat.")
    clean_beats = []
    for beat in beats:
        if not isinstance(beat, dict):
            raise ProductionError("Beat di paket tidak valid.")
        clean_beats.append({"k": _clean_text(beat.get("k"), 80), "n": _clean_text(beat.get("n")),
                            "v": _clean_text(beat.get("v"))})
    package = {k: _clean_text(data.get(k), 300) for k in ("judul", "topik", "durasi", "bahasa", "rasio",
                                                           "sumber", "dibuat")}
    if package["rasio"] not in {"9:16", "16:9", "1:1"}:
        package["rasio"] = "9:16"
    package |= {"format": FORMAT, "mock": bool(data.get("mock")), "beats": clean_beats,
                "naskah_tts": "\n\n".join(b["n"] for b in clean_beats if b["n"].strip())}
    return package


def srt_time(seconds: float) -> str:
    ms = int(round(seconds * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def build_srt(beats: list[dict[str, Any]], timings: list[dict[str, Any]]) -> str:
    blocks = []
    for i, (beat, timing) in enumerate(zip(beats, timings, strict=False), start=1):
        start, end = timing["start"], timing["start"] + timing["speech"]
        blocks.append(f"{i}\n{srt_time(start)} --> {srt_time(end)}\n{beat['n'].strip()}\n")
    return "\n".join(blocks)


class ProductionService:
    def __init__(self, *, data_dir: Path, blueprint_file: Path | None, hyperframes_dir: Path | None,
                 voice: Any, content: Any, available: bool, bus: Any = None) -> None:
        self.root = data_dir / "production"
        self.voice = voice
        self.content = content
        self.available = available  # False di mode online: fitur ini hanya di laptop
        self.bus = bus
        self.blueprint = BlueprintCopy(blueprint_file, data_dir / "blueprint")
        self.hyperframes = HyperFrames(hyperframes_dir)
        self._processes: dict[str, subprocess.Popen] = {}

    # ── paket ─────────────────────────────────────────────────────────────
    def _require(self) -> None:
        if not self.available:
            raise ProductionError("Produksi konten hanya berjalan di laptop (mode local), tidak di ZOI online. "
                                  "Unduh paket produksi dari halaman Naskah lalu impor di ZOI laptop.", 409)

    def _dir(self, package_id: str) -> Path:
        if not ID_RE.match(package_id or ""):
            raise ProductionError("Paket tidak ditemukan.", 404)
        path = self.root / package_id
        if not (path / "paket.json").is_file():
            raise ProductionError("Paket tidak ditemukan.", 404)
        return path

    def _changed(self) -> None:
        if self.bus:
            self.bus.publish("production.updated", {})

    def import_package(self, data: Any) -> dict[str, Any]:
        self._require()
        package = validate_package(data)
        package_id = secrets.token_hex(6)
        folder = self.root / package_id
        folder.mkdir(parents=True, exist_ok=False)
        (folder / "paket.json").write_text(json.dumps(package, indent=2, ensure_ascii=False), encoding="utf-8")
        self._changed()
        return self.get(package_id)

    def from_script(self, item_id: str) -> dict[str, Any]:
        self._require()
        item = self.content.item(item_id)
        if item is None:
            raise ProductionError("Naskah tidak ditemukan.", 404)
        try:
            return self.import_package(build_package(item))
        except PackageError as exc:
            raise ProductionError(str(exc)) from exc

    def package(self, package_id: str) -> dict[str, Any]:
        return json.loads((self._dir(package_id) / "paket.json").read_text(encoding="utf-8"))

    def get(self, package_id: str) -> dict[str, Any]:
        folder = self._dir(package_id)
        package = self.package(package_id)
        files = {name: (folder / name).stat().st_size for name in FILES if (folder / name).is_file()}
        timings_file = folder / "waktu.json"
        timings = json.loads(timings_file.read_text(encoding="utf-8")) if timings_file.is_file() else None
        return {"id": package_id, "judul": package.get("judul"), "rasio": package.get("rasio"),
                "mock": package.get("mock"), "beats": len(package.get("beats", [])), "files": files,
                "narration": timings, "created": (folder / "paket.json").stat().st_mtime,
                "blueprint_url": f"/blueprint-studio/?paket={package_id}"}

    def list(self) -> list[dict[str, Any]]:
        if not self.root.is_dir():
            return []
        items = []
        for folder in self.root.iterdir():
            if ID_RE.match(folder.name) and (folder / "paket.json").is_file():
                items.append(self.get(folder.name))
        return sorted(items, key=lambda x: x["created"], reverse=True)

    def delete(self, package_id: str) -> None:
        self._require()
        shutil.rmtree(self._dir(package_id))
        self._changed()

    def file(self, package_id: str, name: str) -> tuple[Path, str]:
        if name not in FILES:
            raise ProductionError("File tidak dikenal.", 404)
        path = self._dir(package_id) / name
        if not path.is_file():
            raise ProductionError("File belum dibuat.", 404)
        return path, FILES[name]

    # ── status ────────────────────────────────────────────────────────────
    async def status(self) -> dict[str, Any]:
        voice = await self.voice.status() if self.available else None
        narration = None
        if voice:
            tts = voice["tts"]
            licensed = tts["is_mock"] or voice["preferences"].get("piper_license_accepted")
            problem = None if tts["available"] else (tts.get("detail") or "Server Piper tidak berjalan.")
            if tts["available"] and not licensed:
                problem = "Terima dulu catatan lisensi suara Piper di Settings › Suara."
            narration = {"available": problem is None, "problem": problem, "mock": tts["is_mock"],
                         "engine": tts["name"]}
        return {"available": self.available, "blueprint": self.blueprint.status() if self.available else None,
                "hyperframes": self.hyperframes.status() if self.available else None, "narration": narration}

    def build_blueprint(self) -> dict[str, Any]:
        self._require()
        return self.blueprint.build()

    # ── tugas ─────────────────────────────────────────────────────────────
    def task_kinds(self, run_async: Callable[..., Any]) -> list[TaskKind]:
        def narrate(ctx: TaskContext) -> dict[str, Any]:
            package_id = ctx.params["package_id"]
            folder = self._dir(package_id)
            beats = self.package(package_id)["beats"]
            parts: list[bytes] = []
            params = None
            timings: list[dict[str, Any]] = []
            t = 0.0
            work = folder / "narasi"
            work.mkdir(exist_ok=True)
            for i, beat in enumerate(beats):
                ctx.progress(5 + int(80 * i / len(beats)), f"Membacakan beat {i + 1}/{len(beats)}…")
                text = beat["n"].strip() or beat["k"]
                audio = run_async(self.voice.speak(text), timeout=180)
                with wave.open(io.BytesIO(audio)) as w:
                    current = (w.getnchannels(), w.getsampwidth(), w.getframerate())
                    frames = w.readframes(w.getnframes())
                    speech = w.getnframes() / float(w.getframerate())
                if params and current != params:
                    raise ProductionError("Format audio Piper berubah di tengah narasi.")
                params = current
                (work / f"beat-{i + 1:02d}.wav").write_bytes(audio)
                gap = bytes(int(GAP_S * current[2]) * current[0] * current[1])
                parts.append(frames + gap)
                duration = round(speech + GAP_S, 3)
                timings.append({"start": round(t, 3), "speech": round(speech, 3), "duration": duration,
                                "file": f"narasi/beat-{i + 1:02d}.wav"})
                t += duration
            ctx.progress(90, "Menggabungkan narasi…")
            buffer = io.BytesIO()
            with wave.open(buffer, "wb") as w:
                w.setnchannels(params[0])
                w.setsampwidth(params[1])
                w.setframerate(params[2])
                w.writeframes(b"".join(parts))
            (folder / "narasi.wav").write_bytes(buffer.getvalue())
            (folder / "narasi.srt").write_text(build_srt(beats, timings), encoding="utf-8")
            (folder / "waktu.json").write_text(json.dumps(timings, indent=2), encoding="utf-8")
            self._changed()
            mock = bool(getattr(self.voice.tts, "is_mock", False))
            return {"package_id": package_id, "seconds": round(t, 2), "mock": mock,
                    "note": "MOCK — nada uji, bukan suara manusia." if mock else "Narasi Piper siap."}

        def render(ctx: TaskContext) -> dict[str, Any]:
            package_id = ctx.params["package_id"]
            folder = self._dir(package_id)
            hf = self.hyperframes.status()
            if not hf["enabled"]:
                raise ProductionError("HyperFrames belum siap: " + " ".join(hf["problems"]))
            package = self.package(package_id)
            timings_file = folder / "waktu.json"
            timings = json.loads(timings_file.read_text(encoding="utf-8")) if timings_file.is_file() else None
            project = folder / "komposisi"
            if project.exists():
                shutil.rmtree(project)
            project.mkdir()
            if timings:
                shutil.copytree(folder / "narasi", project / "narasi")
            (project / "index.html").write_text(compose(package, timings), encoding="utf-8")
            output = folder / "video.tmp.mp4"
            output.unlink(missing_ok=True)
            cmd, env = self.hyperframes.command(project, output)
            ctx.progress(10, "HyperFrames me-render (bisa lama di laptop lemah)…")
            proc = subprocess.Popen(cmd, cwd=project, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    text=True, encoding="utf-8", errors="replace")
            self._processes[ctx.task_id] = proc
            deadline = time.monotonic() + RENDER_TIMEOUT_S
            lines: list[str] = []
            try:
                assert proc.stdout is not None
                for line in proc.stdout:
                    lines = (lines + [line.rstrip()])[-40:]
                    match = re.search(r'"pct":\s*(\d+)', line)
                    if match:
                        ctx.progress(10 + int(int(match.group(1)) * 0.85), "Me-render video…")
                    if ctx.cancel_event.is_set() or time.monotonic() > deadline:
                        proc.kill()
                        break
                proc.wait(timeout=30)
            finally:
                self._processes.pop(ctx.task_id, None)
            ctx.check_cancelled()
            if proc.returncode != 0 or not output.is_file():
                tail = " | ".join(x for x in lines[-5:] if x)[:600]
                raise ProductionError(f"Render HyperFrames gagal (kode {proc.returncode}). {tail}")
            output.replace(folder / "video.mp4")
            self._changed()
            return {"package_id": package_id, "bytes": (folder / "video.mp4").stat().st_size,
                    "with_audio": bool(timings), "mock": bool(package.get("mock"))}

        return [TaskKind(kind="production_narrate", name="Narasi paket produksi", func=narrate, lane="production"),
                TaskKind(kind="production_render", name="Render HyperFrames", func=render, lane="production")]
