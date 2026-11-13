import { formatTime } from "../lib/format";
import { MENU } from "../menu";
import { useApp } from "../stores/appStore";
import { NotYetAvailable } from "./NotYetAvailable";

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
      <NotYetAvailable item={item} />
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
