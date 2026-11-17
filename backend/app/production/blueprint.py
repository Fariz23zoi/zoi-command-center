# ruff: noqa: E501 — blok JavaScript yang disisipkan sengaja dibiarkan apa adanya.
"""Salinan Blueprint Studio dengan tombol "Muat paket ZOI" (keputusan K-2 Phase 7).

File asli hanya DIBACA. Salinan = isi asli + satu blok <script> sebelum </body>; selebihnya identik.
Kode Blueprint Studio tidak pernah masuk repo ZOI — salinan dibuat di komputer pengguna dari file miliknya.
Bila penanda struktur tidak cocok (file asli berubah besar), salinan ditolak: lebih baik jujur daripada menebak.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

MARKERS = (
    "<title>Blueprint Studio</title>",
    'id="topik"', 'id="durasi"', 'id="bahasa"', 'id="rasio"', 'id="mc"', 'id="srt"', 'id="beats"',
    "function render()", "function setMode()", "state={beats:",
)
MAX_BYTES = 2 * 1024 * 1024
INJECT_MARK = "<!-- ZOI: tombol Muat paket ZOI -->"

# Disisipkan apa adanya. Hanya memakai fungsi/variabel global milik Blueprint ($, state, setMode, render, sync).
INJECT = INJECT_MARK + """
<script>
// ZOI: pengganti fitur AI Claude. Blueprint asli memakai claude.use("sample") yang hanya ada di dalam Claude;
// di sini dijawab AI Brain ZOI (gratis, sesuai .env). Unduhan file memakai unduhan biasa browser.
(function(){
  if (window.claude && window.claude.use) return;
  function note(text){ var s=document.getElementById("zoi-paket-status"); if(s) s.textContent=text; }
  var sample = { json: function(prompt){
    note("AI ZOI sedang menulis…");
    return fetch("/api/production/blueprint/ai", {method:"POST",
      headers:{"Content-Type":"application/json","X-ZOI-Client":"web"},
      body: JSON.stringify({prompt: String(prompt).slice(0, 30000)})})
    .then(function(r){ return r.json().then(function(d){ if(!r.ok) throw new Error((d.error&&d.error.message)||"AI gagal"); return d; }); })
    .then(function(d){ note("Ditulis oleh AI ZOI (" + d.provider + ")" + (d.is_mock ? " — MOCK, teks tiruan" : "")); return d.result; })
    .catch(function(e){ note("AI ZOI gagal: " + e.message + " — Blueprint memakai cara cadangan."); throw e; });
  }};
  var downloads = { save: function(o){
    var url = URL.createObjectURL(o.data), a = document.createElement("a");
    a.href = url; a.download = o.filename || "blueprint.txt"; document.body.appendChild(a); a.click(); a.remove();
    setTimeout(function(){ URL.revokeObjectURL(url); }, 2000); return Promise.resolve(true);
  }};
  window.claude = { use: function(name){
    return Promise.resolve(name === "sample" ? sample : name === "downloads" ? downloads : null);
  }};
})();
</script>
<script>
(function(){
  var SUPPORTED = "zoi.paket/v1";
  function nearestDuration(text){
    var n = parseInt(String(text||"").replace(/[^0-9]/g,""),10) || 60;
    return [30,60,90].reduce(function(a,b){return Math.abs(b-n)<Math.abs(a-n)?b:a});
  }
  function setSelect(id, value){
    var el = $(id); if(!el) return;
    for (var i=0;i<el.options.length;i++){
      var o = el.options[i]; if((o.value||o.text)===String(value)){ el.selectedIndex=i; return; }
    }
  }
  function apply(p, srt){
    if(!p || p.format!==SUPPORTED){ alert("Bukan paket ZOI ("+SUPPORTED+")."); return; }
    $("topik").value = p.topik || p.judul || "";
    setSelect("durasi", String(nearestDuration(p.durasi)));
    setSelect("bahasa", p.bahasa==="English" ? "English" : "Indonesia");
    setSelect("rasio", p.rasio || "9:16");
    $("mc").value = "manual"; setMode();
    state.beats = (p.beats||[]).map(function(b){ return {k:b.k||"", n:b.n||"", v:b.v||"", a:""}; });
    state.note = "Dimuat dari paket ZOI" + (p.mock ? " (MOCK — teks tiruan, bukan hasil AI)" : "") + ".";
    render(); if(typeof sync==="function") sync();
    if(srt) $("srt").value = srt;
    var s = $("zoi-paket-status"); if(s) s.textContent = "Paket dimuat: " + (p.judul||p.topik||"") + (srt ? " + SRT narasi" : "");
  }
  var bar = document.createElement("div");
  bar.setAttribute("style","position:fixed;right:12px;bottom:12px;z-index:9999;background:#131722;color:#fff;"+
    "padding:8px 10px;border-radius:10px;font:14px sans-serif;box-shadow:0 2px 12px rgba(0,0,0,.4)");
  bar.innerHTML = '<label style="cursor:pointer">📦 Muat paket ZOI<input type="file" accept=".json,application/json" '+
    'id="zoi-paket-file" hidden></label> <span id="zoi-paket-status" style="opacity:.8;margin-left:6px"></span>';
  document.body.appendChild(bar);
  // Kirim cerita + gaya (prompt motion) ke ZOI → Content Production: narasi Piper → Animasikan dengan ZOI AI.
  var send = document.createElement("button");
  send.type = "button"; send.textContent = "🎬 Kirim ke ZOI";
  send.setAttribute("style","margin-left:8px;padding:4px 10px;border-radius:8px;border:0;background:#8b5cf6;color:#fff;cursor:pointer");
  bar.insertBefore(send, document.getElementById("zoi-paket-status"));
  send.addEventListener("click", function(){
    var st = document.getElementById("zoi-paket-status");
    var beats = (state.beats||[]).map(function(b){ return {k:String(b.k||""), n:String(b.n||""), v:String(b.v||"")}; })
      .filter(function(b){ return b.n.trim(); });
    if(!beats.length){ st.textContent = "Buat cerita dulu, lalu kirim."; return; }
    var gaya = $("prompt") ? String($("prompt").textContent||"").trim() : "";
    if(!gaya && typeof STYLES!=="undefined" && STYLES[state.style]){ var g = STYLES[state.style];
      gaya = "Gaya: " + g.n + ". " + (g.d||"") + (g.c ? " Palet warna: " + g.c.join(", ") + "." : ""); }
    var p = {format:SUPPORTED, judul:$("topik").value.trim(), topik:$("topik").value.trim(), durasi:$("durasi").value+" detik",
             bahasa:$("bahasa").value, rasio:$("rasio").value, sumber:"Blueprint Studio", beats:beats, gaya:gaya.slice(0,4000)};
    send.disabled = true; st.textContent = "Mengirim…";
    fetch("/api/production/packages", {method:"POST", headers:{"Content-Type":"application/json","X-ZOI-Client":"web"},
      body: JSON.stringify({package:p})})
    .then(function(r){ return r.json().then(function(d){ if(!r.ok) throw new Error((d.error&&d.error.message)||"gagal"); return d; }); })
    .then(function(){ st.innerHTML = 'Terkirim. Lanjut di <a href="/production" target="_top" style="color:#c4b5fd">Content Production</a> — buat narasi lalu Animasikan.'; })
    .catch(function(e){ st.textContent = "Gagal mengirim: " + e.message; })
    .then(function(){ send.disabled = false; });
  });
  document.getElementById("zoi-paket-file").addEventListener("change", function(e){
    var f = e.target.files && e.target.files[0]; if(!f) return;
    f.text().then(function(t){ apply(JSON.parse(t), null); }).catch(function(){ alert("File paket tidak bisa dibaca."); });
  });
  var id = new URLSearchParams(location.search).get("paket");
  if(id && /^[A-Za-z0-9_-]{1,64}$/.test(id)){
    var base = "/api/production/packages/" + id + "/files/";
    fetch(base + "paket.json").then(function(r){ if(!r.ok) throw 0; return r.json(); }).then(function(p){
      return fetch(base + "narasi.srt").then(function(r){ return r.ok ? r.text() : null; }).catch(function(){ return null; })
        .then(function(srt){ apply(p, srt); });
    }).catch(function(){ var s=$("zoi-paket-status"); if(s) s.textContent="Paket tidak ditemukan di ZOI."; });
  }
})();
</script>
"""


def _stamp(raw: bytes) -> str:
    """Sidik salinan: berubah bila file asli ATAU sisipan ZOI berubah → salinan dibuat ulang otomatis."""
    return hashlib.sha256(raw + INJECT.encode("utf-8")).hexdigest()


class BlueprintCopyError(Exception):
    pass


def make_copy(original: str) -> str:
    missing = [m for m in MARKERS if m not in original]
    if missing:
        raise BlueprintCopyError("Struktur file Blueprint Studio tidak dikenali (penanda tidak ada: "
                                 + ", ".join(missing[:4]) + "). Salinan tidak dibuat agar tidak merusak.")
    if INJECT_MARK in original:
        raise BlueprintCopyError("File ini sudah berupa salinan ZOI. Arahkan ZOI_BLUEPRINT_FILE ke file asli.")
    index = original.rfind("</body>")
    if index < 0:
        raise BlueprintCopyError("File Blueprint Studio tidak memiliki </body>.")
    return original[:index] + INJECT + original[index:]


@dataclass
class BlueprintCopy:
    original: Path | None
    out_dir: Path

    @property
    def copy_path(self) -> Path:
        return self.out_dir / "index.html"

    def _original_bytes(self) -> bytes:
        if self.original is None:
            raise BlueprintCopyError("ZOI_BLUEPRINT_FILE belum diisi di file .env.")
        if not self.original.is_file():
            raise BlueprintCopyError(f"File Blueprint Studio tidak ditemukan: {self.original}")
        if self.original.stat().st_size > MAX_BYTES:
            raise BlueprintCopyError("File Blueprint Studio terlalu besar (> 2 MB) — bukan file yang diharapkan.")
        return self.original.read_bytes()  # hanya baca

    def status(self) -> dict:
        info: dict = {"configured": self.original is not None, "original_found": False, "copy_exists":
                      self.copy_path.is_file(), "up_to_date": False, "problem": None, "url": "/blueprint-studio/"}
        try:
            raw = self._original_bytes()
            info["original_found"] = True
            digest = _stamp(raw)
            make_copy(raw.decode("utf-8"))  # validasi penanda
            stamp = self.out_dir / "source.sha256"
            info["up_to_date"] = info["copy_exists"] and stamp.is_file() and stamp.read_text().strip() == digest
        except (BlueprintCopyError, UnicodeDecodeError) as exc:
            info["problem"] = str(exc)
        return info

    def build(self) -> dict:
        raw = self._original_bytes()
        try:
            html = make_copy(raw.decode("utf-8"))
        except UnicodeDecodeError as exc:
            raise BlueprintCopyError("File Blueprint Studio bukan teks UTF-8.") from exc
        self.out_dir.mkdir(parents=True, exist_ok=True)
        tmp = self.copy_path.with_suffix(".tmp")
        tmp.write_text(html, encoding="utf-8")
        tmp.replace(self.copy_path)
        (self.out_dir / "source.sha256").write_text(_stamp(raw), encoding="utf-8")
        return self.status()
