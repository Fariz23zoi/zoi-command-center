import { api, type ClipperLaunch, type ProductionStatus } from "@zoi/api-client";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { formatTime } from "../lib/format";
import { errorText } from "../lib/youtube";
import { MENU } from "../menu";
import { useApp } from "../stores/appStore";
import { OnlineNotice } from "./OnlineNotice";

const ENV_VAR: Record<string, string> = {
  zoi_ai_clipper: "ZOI_CLIPPER_DIR",
  blueprint_studio: "ZOI_BLUEPRINT_FILE",
};

/** Halaman integrasi: fitur penuh di Phase 7; sekarang hanya status deteksi read-only yang nyata. */
export function IntegrationPage({ adapterName }: { adapterName: string }) {
  const item = MENU.find((m) => m.path === (adapterName === "zoi_ai_clipper" ? "/clipper" : "/blueprint"))!;
  const adapter = useApp((s) => s.adapters.find((a) => a.name === adapterName));

  return (
    <>
      {adapterName === "blueprint_studio" ? (
        <section className="page" data-testid="blueprint-page">
          <h1>{item.label}</h1>
          <p>{item.description}</p>
          <p>
            Salinan dengan tombol <strong>Muat paket ZOI</strong> dibuat dan dibuka dari{" "}
            <Link to="/production">Content Production</Link>. File asli Blueprint Studio hanya dibaca, tidak pernah
            diubah, dan tidak diunggah ke mana pun.
          </p>
          <BlueprintLauncher />
        </section>
      ) : (
        <ClipperLauncher title={item.label} description={item.description} />
      )}
      <OnlineNotice feature="Integrasi aplikasi di laptop" />
      <section className="page">
        <h2>Deteksi (read-only)</h2>
        {!adapter && <p className="muted">Memeriksa…</p>}
        {adapter && (
          <>
            <p className={`notice ${adapter.found ? "ok" : adapter.configured ? "bad" : "warn"}`}>
              {adapter.found ? "Aplikasi ditemukan. ZOI hanya membaca — tidak mengubah file apa pun."
                : adapter.configured ? "Aplikasi tidak ditemukan di lokasi yang dikonfigurasi."
                  : `Belum dikonfigurasi. Isi ${ENV_VAR[adapterName]} di file .env.`}
            </p>
            {adapter.problems.length > 0 && <ul>{adapter.problems.map((p) => <li key={p}>{p}</li>)}</ul>}
            <p className="source">Diperiksa {formatTime(adapter.checked_at)}</p>
          </>
        )}
      </section>
    </>
  );
}

/** Menyalakan web app CLIPPER apa adanya (proses terpisah) lalu membukanya di tab baru. ZOI tidak mengolah video. */
function ClipperLauncher({ title, description }: { title: string; description: string }) {
  const [state, setState] = useState<ClipperLaunch | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.clipper.status().then(setState).catch((e) => setError(errorText(e, "Status CLIPPER tidak dapat dimuat.")));
  }, []);

  async function run(action: "start" | "stop") {
    setBusy(true);
    setError(null);
    try {
      let next = await api.clipper[action]();
      // Server CLIPPER butuh beberapa detik untuk siap menerima koneksi.
      for (let i = 0; action === "start" && !next.running && i < 20; i += 1) {
        await new Promise((r) => setTimeout(r, 1000));
        next = await api.clipper.status();
      }
      setState(next);
      if (action === "start" && !next.running) setError("CLIPPER belum merespons. Periksa apakah paket Python-nya sudah terpasang.");
    } catch (e) {
      setError(errorText(e, "Perintah ke CLIPPER gagal."));
    } finally {
      setBusy(false);
    }
  }

  const url = state ? `http://${window.location.hostname}:${state.port}` : "#";
  return (
    <section className="page" data-testid="clipper-page">
      <h1>{title}</h1>
      <p>{description}</p>
      <p className="notice warn">
        CLIPPER berjalan sebagai aplikasi terpisah dengan aturannya sendiri. Fitur unduh video YouTube di dalamnya memakai
        yt-dlp; pakai hanya untuk video milikmu sendiri atau yang kamu punya izinnya. ZOI tidak mengunduh apa pun.
      </p>
      {error && <p className="notice bad" role="alert">{error}</p>}
      {!state ? <p className="muted">Memeriksa…</p> : (
        <>
          <p className={`notice ${state.running ? "ok" : "warn"}`} data-testid="clipper-state">
            {state.running ? "Server CLIPPER menyala." : "Server CLIPPER mati."}
          </p>
          {state.reason && <p className="muted">{state.reason}</p>}
          <div className="row">
            {state.running ? (
              <a className="dash-cta" href={url} target="_blank" rel="noreferrer noopener">Buka CLIPPER</a>
            ) : (
              <button type="button" className="primary" disabled={busy || !state.can_start} onClick={() => run("start")}>
                {busy ? "Menyalakan…" : "Jalankan CLIPPER"}
              </button>
            )}
            {state.started_by_zoi && <button type="button" disabled={busy} onClick={() => run("stop")}>Matikan CLIPPER</button>}
          </div>
          <p className="source">Alamat: {url}. CLIPPER hanya menerima akses dari laptop ini (bawaannya 127.0.0.1), jadi tombol Buka dipakai dari browser laptop.</p>
        </>
      )}
    </section>
  );
}

/** Membuka salinan Blueprint Studio yang disajikan ZOI (/blueprint-studio/). Salinan dibuat/diperbarui bila perlu. */
function BlueprintLauncher() {
  const [bp, setBp] = useState<ProductionStatus["blueprint"]>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.production.status().then((s) => setBp(s.blueprint)).catch(() => undefined);
  }, []);

  async function open() {
    setBusy(true);
    setError(null);
    // Tab dibuka saat klik (agar tidak diblokir browser), lalu diarahkan setelah salinan siap.
    const tab = window.open("", "_blank");
    try {
      if (!bp?.copy_exists || !bp.up_to_date) await api.production.buildBlueprint();
      const fresh = (await api.production.status()).blueprint;
      setBp(fresh);
      if (tab) tab.location.href = fresh?.url ?? "/blueprint-studio/";
    } catch (e) {
      tab?.close();
      setError(errorText(e, "Blueprint Studio tidak dapat dibuka."));
    } finally {
      setBusy(false);
    }
  }

  if (!bp) return null;
  const ready = bp.original_found && !bp.problem;
  return (
    <>
      {error && <p className="notice bad" role="alert">{error}</p>}
      <div className="row">
        <button type="button" className="primary" disabled={busy || !ready} onClick={open} data-testid="blueprint-open">
          {busy ? "Menyiapkan…" : "Buka Blueprint Studio"}
        </button>
      </div>
      {!ready && <p className="muted">{bp.problem ?? "Isi ZOI_BLUEPRINT_FILE di file .env dengan lokasi file Blueprint Studio (.html)."}</p>}
    </>
  );
}
