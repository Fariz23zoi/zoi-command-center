import { Link } from "react-router-dom";

import { formatTime } from "../lib/format";
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
        </section>
      ) : (
        <section className="page not-ready" data-testid="not-yet-available">
          <h1>{item.label}</h1>
          <p className="tag-phase">Ditunda (keputusan Phase 7)</p>
          <p>{item.description}</p>
        </section>
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
