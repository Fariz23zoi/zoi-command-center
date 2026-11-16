import { api, type ProductionPackage, type ProductionStatus } from "@zoi/api-client";
import { type ChangeEvent, useCallback, useEffect, useState } from "react";

import { errorText } from "../lib/youtube";
import { useApp } from "../stores/appStore";

const FILE_LABEL: Record<string, string> = {
  "paket.json": "Paket (JSON)", "narasi.wav": "Narasi (WAV)", "narasi.srt": "SRT narasi", "video.mp4": "Video (MP4)",
};

/** Produksi Konten (Phase 7) — hanya di laptop. Paket datang dari halaman Naskah (online atau laptop). */
export function ProductionPage() {
  const online = useApp((s) => s.config?.online);
  const revision = useApp((s) => s.productionRevision);
  const tasks = useApp((s) => s.tasks);
  const [status, setStatus] = useState<ProductionStatus | null>(null);
  const [items, setItems] = useState<ProductionPackage[]>([]);
  const [scripts, setScripts] = useState<{ id: string; title: string; is_mock: boolean }[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const load = useCallback(() => {
    api.production.status().then(setStatus, (e: unknown) => setError(errorText(e, "Status produksi gagal dimuat.")));
    api.production.packages().then((r) => setItems(r.items), () => undefined);
  }, []);
  useEffect(load, [load, revision]);
  useEffect(() => {
    if (online === false) api.content.scripts().then((r) => setScripts(r.items), () => undefined);
  }, [online]);

  const act = (promise: Promise<unknown>, message?: string) => {
    setError(null);
    setNotice(null);
    promise.then(() => { if (message) setNotice(message); load(); },
      (e: unknown) => setError(errorText(e, "Gagal.")));
  };

  const importFile = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    let parsed: unknown;
    try {
      parsed = JSON.parse(await file.text());
    } catch {
      setError("File bukan JSON. Pilih file paket-zoi-….json dari halaman Naskah.");
      return;
    }
    act(api.production.importPackage(parsed), "Paket diimpor.");
  };

  if (status && !status.available) {
    return (
      <section className="page" data-testid="production-page">
        <h1>Content Production</h1>
        <p className="notice warn" data-testid="production-laptop-only">
          Produksi konten (narasi, Blueprint Studio, render video) hanya berjalan di laptop, tidak di ZOI online.
          Buka halaman <strong>Script &amp; Storyboard</strong>, klik <strong>Unduh paket produksi</strong>, lalu
          impor file itu di ZOI laptop (mode local).
        </p>
      </section>
    );
  }

  // Satu jalur antrean "production": selagi satu tugas berjalan, tombol sejenis dimatikan.
  const running = (kind: string) => tasks.some((t) => t.kind === kind && (t.status === "QUEUED" || t.status === "RUNNING"));
  const hf = status?.hyperframes;
  const narration = status?.narration;
  const blueprint = status?.blueprint;

  return (
    <section className="page" data-testid="production-page">
      <h1>Content Production</h1>
      <p className="muted">
        Paket produksi → narasi (Piper, opsional) → Blueprint Studio (animasi lewat Claude) atau render kartu teks
        HyperFrames (opsional). Semua berjalan di laptop ini; tidak ada yang dipublikasikan.
      </p>
      {error && <p className="notice bad" role="alert">{error}</p>}
      {notice && <p className="notice ok" role="status">{notice}</p>}

      <h2>Impor paket</h2>
      <label className="form">
        <span>File paket dari ZOI (paket-zoi-….json)</span>
        <input type="file" accept=".json,application/json" data-testid="production-import"
               onChange={(e) => void importFile(e)} />
      </label>
      {scripts.length > 0 && (
        <label className="form">
          <span>…atau buat dari naskah di laptop ini</span>
          <select data-testid="production-from-script" defaultValue=""
                  onChange={(e) => { if (e.target.value) act(api.production.fromScript(e.target.value), "Paket dibuat."); }}>
            <option value="">Pilih naskah…</option>
            {scripts.map((s) => <option key={s.id} value={s.id}>{s.title}{s.is_mock ? " (MOCK)" : ""}</option>)}
          </select>
        </label>
      )}

      <h2>Kesiapan</h2>
      <dl className="kv" data-testid="production-readiness">
        <dt>Narasi Piper</dt>
        <dd>{narration?.available ? (narration.mock ? "Siap (MOCK — nada uji)" : "Siap") : narration?.problem ?? "—"}</dd>
        <dt>Blueprint Studio</dt>
        <dd>
          {blueprint?.problem ?? (blueprint?.copy_exists
            ? (blueprint.up_to_date ? "Salinan siap" : "File asli berubah — perbarui salinan")
            : "Salinan belum dibuat")}{" "}
          {blueprint?.original_found && !blueprint.problem && (
            <button type="button" data-testid="blueprint-build"
                    onClick={() => act(api.production.buildBlueprint(), "Salinan Blueprint Studio dibuat. File asli tidak diubah.")}>
              {blueprint.copy_exists ? "Perbarui salinan" : "Buat salinan"}
            </button>
          )}
        </dd>
        <dt>HyperFrames (opsional)</dt>
        <dd data-testid="hyperframes-status">
          {hf?.enabled ? `Siap — v${hf.version}` : (hf?.problems ?? []).join(" ")}
        </dd>
      </dl>

      <h2>Paket</h2>
      {items.length === 0 && <p className="empty">Belum ada paket. Impor file paket dari halaman Naskah.</p>}
      {items.map((p) => (
        <article key={p.id} className="panel" data-testid="production-item">
          <h3>{p.judul || "(tanpa judul)"} {p.mock && <span className="badge warn">MOCK</span>}</h3>
          <p className="muted">{p.beats} beat · rasio {p.rasio}
            {p.narration ? ` · narasi ${p.narration.reduce((a, t) => a + t.duration, 0).toFixed(1)} detik` : ""}</p>
          <p>
            <button type="button" disabled={!narration?.available || running("production_narrate")}
                    title={narration?.problem ?? undefined} data-testid="production-narrate"
                    onClick={() => act(api.production.narrate(p.id), "Narasi dimulai — lihat Task Manager.")}>
              {p.files["narasi.wav"] ? "Buat ulang narasi" : "Buat narasi"}
            </button>{" "}
            <a className="button" href={p.blueprint_url} target="_blank" rel="noopener"
               aria-disabled={!blueprint?.copy_exists} data-testid="production-blueprint">
              Buka di Blueprint Studio
            </a>{" "}
            <button type="button" disabled={!hf?.enabled || running("production_render")}
                    title={hf?.enabled ? undefined : "HyperFrames belum siap"} data-testid="production-render"
                    onClick={() => act(api.production.render(p.id), "Render dimulai — lihat Task Manager.")}>
              Render kartu teks (HyperFrames)
            </button>{" "}
            <button type="button" onClick={() => act(api.production.remove(p.id), "Paket dihapus.")}>Hapus</button>
          </p>
          <p data-testid="production-files">
            {Object.keys(p.files).map((name) => (
              <a key={name} className="button ghost" href={api.production.fileUrl(p.id, name)} download>
                {FILE_LABEL[name] ?? name}
              </a>
            ))}
          </p>
        </article>
      ))}
    </section>
  );
}
