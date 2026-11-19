import { api, type Artifact } from "@zoi/api-client";
import { type ChangeEvent, useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { download, timeText, waitTask } from "../artifacts/shared";
import "../artifacts/artifacts.css";
import { errorText } from "../lib/youtube";

const EXAMPLES = ["Kalkulator penghasilan AdSense dari views dan RPM", "Kuis 5 soal tentang tata surya dengan skor",
  "Generator ide judul video: isi topik, AI ZOI memberi 10 judul"];

/** Daftar artefak + minta artefak baru ke AI ZOI + unggah HTML (mis. artefak buatan Claude). */
export function ArtifactsPage() {
  const navigate = useNavigate();
  const [items, setItems] = useState<Artifact[] | null>(null);
  const [permintaan, setPermintaan] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    api.artifacts.list().then((r) => setItems(r.items), (e) => setError(errorText(e, "Gagal memuat artefak.")));
  }, []);
  useEffect(load, [load]);

  async function generate() {
    setError(null);
    setBusy("AI ZOI sedang menulis artefak… (model gratis bisa 1–5 menit)");
    try {
      const task = await api.artifacts.generate(permintaan.trim());
      const done = await waitTask(task.id, (t) => setBusy(t.message || "Menulis…"));
      if (done.status !== "COMPLETED") throw new Error(done.error || "Gagal membuat artefak.");
      navigate(`/artefak/${String(done.result?.artifact_id)}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : errorText(err, "Gagal membuat artefak."));
    } finally {
      setBusy(null);
    }
  }

  async function upload(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    setError(null);
    try {
      const saved = await api.artifacts.upload(await file.text(), file.name.replace(/\.html?$/i, ""));
      navigate(`/artefak/${saved.id}`);
    } catch (err) {
      setError(errorText(err, "File tidak bisa diunggah."));
    }
  }

  return (
    <section className="page art-page" data-testid="artifacts-page">
      <h1>Artefak</h1>
      <p className="muted">
        Halaman HTML siap pakai (alat, kuis, kalkulator, animasi) seperti artefak Claude. Dibuat AI ZOI atau diunggah
        dari file HTML-mu. Berjalan terisolasi (tanpa akses ke data ZOI) dan hanya bisa dibuka di jaringan ZOI-mu.
      </p>
      {error && <p className="notice bad" role="alert">{error}</p>}
      <div className="art-new">
        <label htmlFor="art-req">Minta artefak baru</label>
        <textarea id="art-req" rows={3} value={permintaan} maxLength={8000} data-testid="art-request"
                  placeholder="Contoh: kalkulator penghasilan AdSense dari views dan RPM"
                  onChange={(e) => setPermintaan(e.target.value)} />
        <div className="art-chips">
          {EXAMPLES.map((ex) => <button key={ex} type="button" className="ghost" onClick={() => setPermintaan(ex)}>{ex}</button>)}
        </div>
        <div className="art-row">
          <button type="button" className="primary" disabled={!!busy || permintaan.trim().length < 3}
                  data-testid="art-generate" onClick={generate}>✨ Buat dengan AI ZOI</button>
          <label className="button">⬆️ Unggah HTML<input type="file" accept=".html,.htm,text/html" hidden onChange={upload} /></label>
        </div>
        {busy && <p className="muted" role="status">{busy}</p>}
      </div>

      <h2>Tersimpan</h2>
      {items === null ? <p className="muted">Memuat…</p> : items.length === 0
        ? <p className="empty">Belum ada artefak.</p>
        : (
          <ul className="art-list">
            {items.map((a) => (
              <li key={a.id} data-testid="art-item">
                <Link to={`/artefak/${a.id}`}><b>{a.judul}</b></Link>
                <span className="muted">v{a.versi} · {a.sumber === "ai" ? `AI ZOI${a.mock ? " (MOCK)" : ""}` : "unggahan"} ·
                  {" "}{timeText(a.updated)}</span>
                <span className="art-actions">
                  <a className="button" href={api.artifacts.htmlUrl(a.id)}>Unduh</a>
                  <button type="button" onClick={() => {
                    if (window.confirm(`Hapus artefak "${a.judul}"?`)) api.artifacts.remove(a.id).then(load, (e) => setError(errorText(e, "Gagal menghapus.")));
                  }}>Hapus</button>
                </span>
              </li>
            ))}
          </ul>
        )}
    </section>
  );
}

/** Penampil artefak: iframe sandbox + jembatan window.claude (sample → AI ZOI, downloads → unduhan browser). */
export function ArtifactViewerPage() {
  const { id = "" } = useParams();
  const frameRef = useRef<HTMLIFrameElement>(null);
  const boxRef = useRef<HTMLDivElement>(null);
  const [meta, setMeta] = useState<Artifact | null>(null);
  const [revisi, setRevisi] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const calls = useRef<number[]>([]);

  const load = useCallback(() => {
    api.artifacts.get(id).then(setMeta, (e) => setError(errorText(e, "Artefak tidak ditemukan.")));
  }, [id]);
  useEffect(load, [load]);

  useEffect(() => {
    function onMessage(event: MessageEvent) {
      const frame = frameRef.current;
      const data = event.data as { zoi?: string; type?: string; n?: number; payload?: Record<string, unknown> } | null;
      if (!frame || event.source !== frame.contentWindow || !data || data.zoi !== "artefak") return;
      const reply = (ok: boolean, result?: unknown, err?: string) =>
        frame.contentWindow?.postMessage({ zoi: "artefak-jawab", n: data.n, ok, result, error: err }, "*");
      const payload = data.payload ?? {};
      if (data.type === "sample") {
        const now = Date.now();
        calls.current = calls.current.filter((t) => now - t < 60_000);
        if (calls.current.length >= 20) { reply(false, null, "Terlalu banyak permintaan AI (maks 20/menit)."); return; }
        calls.current.push(now);
        setNote("AI ZOI sedang menjawab artefak…");
        api.artifacts.sample(String(payload.prompt ?? ""), payload.mode === "text" ? "text" : "json").then((r) => {
          setNote(`Dijawab AI ZOI (${r.provider})${r.is_mock ? " — MOCK, teks tiruan" : ""}.`);
          reply(true, r.result);
        }, (err) => { const m = errorText(err, "AI ZOI gagal."); setNote(m); reply(false, null, m); });
      } else if (data.type === "download") {
        const blob = payload.data instanceof Blob ? payload.data : new Blob([String(payload.data ?? "")]);
        download(blob, String(payload.filename ?? "unduhan.txt"));
        reply(true, true);
      }
    }
    window.addEventListener("message", onMessage);
    return () => window.removeEventListener("message", onMessage);
  }, []);

  async function revise() {
    setError(null);
    setBusy("AI ZOI sedang merevisi…");
    try {
      const task = await api.artifacts.generate(revisi.trim(), id);
      const done = await waitTask(task.id, (t) => setBusy(t.message || "Merevisi…"));
      if (done.status !== "COMPLETED") throw new Error(done.error || "Revisi gagal.");
      setRevisi("");
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : errorText(err, "Revisi gagal."));
    } finally {
      setBusy(null);
    }
  }

  return (
    <section className="page art-view" data-testid="artifact-viewer">
      <div className="art-head">
        <Link to="/artefak" className="ghost">← Artefak</Link>
        <h1>{meta?.judul ?? "Artefak"}</h1>
        {meta && <span className="muted">v{meta.versi}{meta.mock ? " · MOCK" : ""}</span>}
      </div>
      {error && <p className="notice bad" role="alert">{error}</p>}
      {meta && (
        <>
          <div className="art-frame" ref={boxRef}>
            <iframe ref={frameRef} key={`${meta.id}-${meta.versi}`} title={meta.judul} data-testid="art-frame"
                    src={`${meta.raw_url}?v=${meta.versi}`}
                    sandbox="allow-scripts allow-forms allow-modals allow-popups allow-downloads" />
          </div>
          {note && <p className="muted" role="status">{note}</p>}
          <div className="art-row">
            <button type="button" onClick={() => boxRef.current?.requestFullscreen?.()}>⛶ Layar penuh</button>
            <a className="button" href={api.artifacts.htmlUrl(meta.id)}>Unduh HTML</a>
            <button type="button" disabled={meta.versi <= 1 || !!busy}
                    onClick={() => api.artifacts.undo(meta.id).then(setMeta, (e) => setError(errorText(e, "Gagal.")))}>
              ↶ Versi sebelumnya
            </button>
          </div>
          <label htmlFor="art-rev">Minta perubahan</label>
          <textarea id="art-rev" rows={2} value={revisi} maxLength={8000} data-testid="art-revise-text"
                    placeholder="Contoh: tambahkan mode gelap dan tombol reset" onChange={(e) => setRevisi(e.target.value)} />
          <button type="button" className="primary" disabled={!!busy || revisi.trim().length < 3} onClick={revise}>
            ✏️ Revisi dengan AI ZOI
          </button>
          {busy && <p className="muted" role="status">{busy}</p>}
        </>
      )}
    </section>
  );
}
