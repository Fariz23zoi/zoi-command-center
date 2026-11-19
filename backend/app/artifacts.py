"""Artefak ZOI — halaman HTML satu file (alat, kuis, kalkulator, animasi) seperti artefak Claude.

* AI ZOI menulis/merevisi HTML-nya (tugas latar, karena model gratis bisa lambat), atau pengguna mengunggah HTML
  sendiri (mis. artefak buatan Claude).
* Disajikan di `/artefak-raw/<id>/` dengan CSP `sandbox` (origin buram): kode buatan AI TIDAK bisa memanggil API
  ZOI, membaca cookie, atau mengakses data lain. `window.claude.use("sample")` dan `"downloads"` dijembatani lewat
  postMessage ke halaman penampil ZOI, yang memanggil AI ZOI atas nama artefak.
* Tidak ada yang dipublikasikan: tautan hanya bisa dibuka di jaringan ZOI (laptop / Tailscale).
"""

from __future__ import annotations

import json
import re
import shutil
import time
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

from app.ai.structured import extract_json
from app.core.errors import ZoiError
from app.providers.base import ChatMessage, LLMProvider
from app.tasks.manager import TaskContext, TaskKind

MAX_HTML = 2 * 1024 * 1024
MAX_ITEMS = 300
MAX_VERSIONS = 10
ID_RE = re.compile(r"^[a-z0-9]{8,32}$")
GEN_TIMEOUT_S = 420.0

# Dijalankan sebelum skrip halaman. Tanpa penampil ZOI (dibuka langsung), "sample" = null → artefak memakai jalur
# cadangannya sendiri, persis seperti di luar Claude.
SHIM = """<script>/* ZOI: jembatan artefak (sample + downloads) */
(function(){
  if (window.claude && window.claude.use) return;
  var parentOk = window.parent && window.parent !== window, seq = 0, waiting = {};
  window.addEventListener("message", function(e){
    var d = e.data; if (e.source !== window.parent || !d || d.zoi !== "artefak-jawab" || !waiting[d.n]) return;
    var w = waiting[d.n]; delete waiting[d.n]; d.ok ? w[0](d.result) : w[1](new Error(d.error || "AI ZOI gagal"));
  });
  function ask(type, payload){
    return new Promise(function(ok, fail){ var n = ++seq; waiting[n] = [ok, fail];
      window.parent.postMessage({zoi: "artefak", type: type, n: n, payload: payload}, "*"); });
  }
  var sample = {
    json: function(prompt){ return ask("sample", {mode: "json", prompt: String(prompt)}); },
    text: function(prompt){ return ask("sample", {mode: "text", prompt: String(prompt)}); }
  };
  sample.complete = sample.text;
  function saveLocal(o){
    var blob = o.data instanceof Blob ? o.data : new Blob([String(o.data)]);
    var url = URL.createObjectURL(blob), a = document.createElement("a");
    a.href = url; a.download = o.filename || "unduhan.txt"; document.body.appendChild(a); a.click(); a.remove();
    setTimeout(function(){ URL.revokeObjectURL(url); }, 3000); return Promise.resolve(true);
  }
  var downloads = { save: function(o){
    o = o || {}; if (!parentOk) return saveLocal(o);
    var data = o.data instanceof Blob ? o.data : new Blob([String(o.data == null ? "" : o.data)], {type: "text/plain"});
    return ask("download", {filename: String(o.filename || "unduhan.txt"), data: data})
      .then(function(){ return true; });
  }};
  window.claude = {
    use: function(name){ return Promise.resolve(name === "sample" ? (parentOk ? sample : null)
      : name === "downloads" ? downloads : null); },
    complete: function(prompt){
      return parentOk ? sample.text(prompt) : Promise.reject(new Error("AI tidak tersedia")); }
  };
})();
</script>"""

# Kode artefak berjalan di origin buram: tanpa akses ke API/cookie ZOI. Boleh memuat pustaka dari CDN umum (gratis).
CDN = "https://cdnjs.cloudflare.com https://cdn.jsdelivr.net https://unpkg.com"
RAW_CSP = ("sandbox allow-scripts allow-forms allow-modals allow-popups allow-downloads; default-src 'none'; "
           f"script-src 'unsafe-inline' 'unsafe-eval' blob: {CDN}; "
           f"style-src 'unsafe-inline' https://fonts.googleapis.com {CDN}; "
           f"font-src data: https://fonts.gstatic.com {CDN}; img-src data: blob: https:; media-src data: blob:; "
           f"worker-src blob:; connect-src data: blob: {CDN}; frame-src 'none'; base-uri 'none'; form-action 'none'; "
           "frame-ancestors 'self'")

SYSTEM_BUILD = """Kamu membuat ARTEFAK: satu file HTML mandiri (HTML + CSS + JavaScript dalam satu file) yang langsung
berjalan di browser, seperti artefak Claude. Aturan:
- Balas HANYA dengan isi file HTML lengkap dari <!DOCTYPE html> sampai </html>. Tanpa penjelasan, tanpa ```.
- Semua CSS dan JS ditulis di dalam file. Pustaka luar hanya dari cdnjs.cloudflare.com, cdn.jsdelivr.net atau unpkg.com,
  dan hanya bila benar-benar perlu. Tanpa fetch ke internet, tanpa localStorage wajib (bungkus try/catch).
- Rapi di HP dan laptop (responsif), teks bahasa Indonesia kecuali diminta lain, kontras cukup, tombol jelas.
- Jangan membuat data/statistik palsu seolah nyata; beri label "contoh" bila memakai data contoh.
- Bila perlu AI di dalam artefak: `const s = await window.claude.use("sample")` lalu `await s.json(prompt)` (hasil JSON)
  atau `await s.text(prompt)` (teks). Bisa null → sediakan cara cadangan.
- Untuk unduh file: `const d = await window.claude.use("downloads"); await d.save({filename, data: new Blob([...])})`.
- Jaga ukuran wajar (di bawah ~1500 baris)."""


def _now() -> float:
    return round(time.time(), 3)


def extract_html(raw: str) -> str | None:
    text = raw.strip()
    fence = re.search(r"```(?:html)?\s*\n(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if fence:
        text = fence.group(1).strip()
    start = re.search(r"<!DOCTYPE html|<html", text, re.IGNORECASE)
    if not start:
        return None
    text = text[start.start():]
    end = text.lower().rfind("</html>")
    return text[: end + 7] if end >= 0 else text + "\n</html>"


def inject_shim(html: str) -> str:
    match = re.search(r"<head[^>]*>", html, re.IGNORECASE)
    if match:
        return html[: match.end()] + SHIM + html[match.end():]
    return SHIM + html


def _title(html: str, fallback: str) -> str:
    match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    title = re.sub(r"\s+", " ", match.group(1)).strip() if match else ""
    return (title or fallback or "Artefak")[:120]


class ArtifactError(ZoiError):
    def __init__(self, message: str, status_code: int = 400, code: str = "artefak_error") -> None:
        super().__init__(message, status_code=status_code, code=code)


class ArtifactService:
    def __init__(self, *, data_dir: Path, provider: LLMProvider, available: bool = True) -> None:
        self.root = data_dir / "artefak"
        self.provider = provider
        self.available = available

    # ── penyimpanan ───────────────────────────────────────────────────────
    def _require(self) -> None:
        if not self.available:
            raise ArtifactError("Artefak hanya tersedia di ZOI lokal (laptop), bukan mode online.", 404,
                                "artefak_unavailable")

    def _dir(self, artifact_id: str) -> Path:
        if not ID_RE.fullmatch(artifact_id or ""):
            raise ArtifactError("ID artefak tidak valid.", 404, "artefak_not_found")
        folder = self.root / artifact_id
        if not (folder / "meta.json").is_file():
            raise ArtifactError("Artefak tidak ditemukan.", 404, "artefak_not_found")
        return folder

    def _meta(self, folder: Path) -> dict[str, Any]:
        data: dict[str, Any] = json.loads((folder / "meta.json").read_text(encoding="utf-8"))
        return data

    def _write_meta(self, folder: Path, meta: dict[str, Any]) -> None:
        tmp = folder / "meta.tmp"
        tmp.write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(folder / "meta.json")

    def list(self) -> list[dict[str, Any]]:
        self._require()
        if not self.root.is_dir():
            return []
        items = []
        for folder in self.root.iterdir():
            if (folder / "meta.json").is_file() and ID_RE.fullmatch(folder.name):
                try:
                    items.append(self._public(self._meta(folder)))
                except (OSError, ValueError):
                    continue
        return sorted(items, key=lambda m: m.get("updated", 0), reverse=True)

    def get(self, artifact_id: str) -> dict[str, Any]:
        self._require()
        return self._public(self._meta(self._dir(artifact_id)))

    def _public(self, meta: dict[str, Any]) -> dict[str, Any]:
        return {**meta, "url": f"/artefak/{meta['id']}", "raw_url": f"/artefak-raw/{meta['id']}/"}

    def html(self, artifact_id: str) -> str:
        self._require()
        folder = self._dir(artifact_id)
        meta = self._meta(folder)
        return (folder / f"v{meta['versi']}.html").read_text(encoding="utf-8")

    def save(self, html: str, *, judul: str = "", sumber: str, permintaan: str = "",
             artifact_id: str | None = None, provider: str | None = None, mock: bool = False) -> dict[str, Any]:
        self._require()
        data = html.encode("utf-8")
        if len(data) > MAX_HTML:
            raise ArtifactError("HTML terlalu besar (maks 2 MB).", 413, "artefak_too_large")
        if "<" not in html:
            raise ArtifactError("Isi bukan HTML.")
        if artifact_id:
            folder = self._dir(artifact_id)
            meta = self._meta(folder)
            meta["versi"] += 1
        else:
            self.root.mkdir(parents=True, exist_ok=True)
            if sum(1 for _ in self.root.iterdir()) >= MAX_ITEMS:
                raise ArtifactError(f"Sudah ada {MAX_ITEMS} artefak. Hapus beberapa dulu.", 409, "artefak_full")
            artifact_id = uuid.uuid4().hex[:12]
            folder = self.root / artifact_id
            folder.mkdir()
            meta = {"id": artifact_id, "versi": 1, "dibuat": _now(), "riwayat": []}
        (folder / f"v{meta['versi']}.html").write_text(html, encoding="utf-8")
        old = folder / f"v{meta['versi'] - MAX_VERSIONS}.html"
        if old.is_file():
            old.unlink()
        meta.update({"judul": (judul.strip() or _title(html, meta.get("judul", "")))[:120], "updated": _now(),
                     "sumber": sumber, "bytes": len(data), "provider": provider, "mock": mock})
        meta["riwayat"] = [*meta.get("riwayat", []), {"versi": meta["versi"], "sumber": sumber,
                                                      "permintaan": permintaan[:500], "waktu": _now()}][-MAX_VERSIONS:]
        self._write_meta(folder, meta)
        return self._public(meta)

    def undo(self, artifact_id: str) -> dict[str, Any]:
        self._require()
        folder = self._dir(artifact_id)
        meta = self._meta(folder)
        prev = folder / f"v{meta['versi'] - 1}.html"
        if not prev.is_file():
            raise ArtifactError("Tidak ada versi sebelumnya.", 409, "artefak_no_prev")
        (folder / f"v{meta['versi']}.html").unlink(missing_ok=True)
        meta["versi"] -= 1
        meta["riwayat"] = [r for r in meta.get("riwayat", []) if r["versi"] <= meta["versi"]]
        meta["updated"] = _now()
        meta["bytes"] = prev.stat().st_size
        self._write_meta(folder, meta)
        return self._public(meta)

    def rename(self, artifact_id: str, judul: str) -> dict[str, Any]:
        self._require()
        folder = self._dir(artifact_id)
        meta = self._meta(folder)
        meta["judul"] = judul.strip()[:120] or meta["judul"]
        self._write_meta(folder, meta)
        return self._public(meta)

    def delete(self, artifact_id: str) -> None:
        self._require()
        shutil.rmtree(self._dir(artifact_id))

    def serve(self, artifact_id: str) -> str:
        return inject_shim(self.html(artifact_id))

    # ── AI ────────────────────────────────────────────────────────────────
    async def _collect(self, messages: list[ChatMessage], timeout_s: float) -> tuple[str, str | None]:
        parts: list[str] = []
        served: str | None = None
        async for chunk in self.provider.chat(messages, timeout_s=timeout_s):
            if chunk.type == "text":
                parts.append(chunk.text)
            elif chunk.type == "error":
                raise ArtifactError(chunk.error or "AI ZOI gagal menjawab.", 502, "ai_failed")
            elif chunk.type == "done":
                served = chunk.served_by
                break
        return "".join(parts), served

    async def write_html(self, permintaan: str, current: str | None) -> tuple[str, str]:
        if current is None:
            user = f"Buat artefak ini:\n{permintaan.strip()}"
        else:
            user = (f"Ini file artefak saat ini:\n{current}\n\nUbah sesuai permintaan berikut dan kembalikan file HTML "
                    f"LENGKAP yang sudah diperbarui (bukan potongan):\n{permintaan.strip()}")
        messages = [ChatMessage("system", SYSTEM_BUILD), ChatMessage("user", user)]
        raw, served = await self._collect(messages, GEN_TIMEOUT_S)
        html = extract_html(raw)
        if html is None:
            raise ArtifactError("AI ZOI tidak mengembalikan file HTML. Coba ulangi atau perjelas permintaan.", 502,
                                "ai_bad_html")
        return html, served or self.provider.name

    async def sample(self, prompt: str, mode: str) -> dict[str, Any]:
        self._require()
        mock = bool(getattr(self.provider, "is_mock", False))
        if mode == "text":
            raw, served = await self._collect([ChatMessage("user", prompt)], 180.0)
            return {"result": raw.strip(), "provider": served or self.provider.name, "is_mock": mock}
        messages = [ChatMessage("system", "Ikuti instruksi pengguna persis. Balas HANYA JSON yang valid (objek atau "
                                          "array), tanpa teks lain dan tanpa ```."), ChatMessage("user", prompt)]
        for _ in range(2):
            raw, served = await self._collect(messages, 180.0)
            candidate = extract_json(raw)
            if candidate is not None:
                return {"result": json.loads(candidate), "provider": served or self.provider.name, "is_mock": mock}
            messages = [*messages, ChatMessage("assistant", raw[:2000]),
                        ChatMessage("user", "Jawaban tadi bukan JSON. Balas HANYA JSON yang diminta.")]
        raise ArtifactError("AI ZOI tidak memberi JSON yang valid.", 502, "ai_bad_json")

    def task_kind(self, run_async: Callable[..., Any]) -> TaskKind:
        def generate(ctx: TaskContext) -> dict[str, Any]:
            artifact_id = ctx.params.get("artifact_id")
            permintaan = str(ctx.params["permintaan"])
            current = self.html(artifact_id) if artifact_id else None
            ctx.progress(10, "AI ZOI sedang menulis artefak…" if current is None else "AI ZOI sedang merevisi artefak…")
            html, served = run_async(self.write_html(permintaan, current), timeout=GEN_TIMEOUT_S + 30)
            ctx.check_cancelled()
            saved = self.save(html, sumber="ai", permintaan=permintaan, artifact_id=artifact_id, provider=served,
                              mock=bool(getattr(self.provider, "is_mock", False)))
            return {"artifact_id": saved["id"], "versi": saved["versi"], "judul": saved["judul"],
                    "url": saved["url"], "mock": saved["mock"]}

        return TaskKind(kind="artifact_generate", name="Artefak ZOI AI", func=generate, lane="artifact")
