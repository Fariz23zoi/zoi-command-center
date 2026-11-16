import { api, type CloudModels, type CloudProviderInfo, type CloudStatus, type CloudTestResult } from "@zoi/api-client";
import { type FormEvent, useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { errorText, exact } from "../lib/youtube";
import { useApp } from "../stores/appStore";

type Notice = { kind: "ok" | "bad" | "warn"; text: string } | null;

function ProviderCard({ info, reload, setNotice }: {
  info: CloudProviderInfo; reload: (status?: CloudStatus) => void; setNotice: (n: Notice) => void;
}) {
  const [key, setKey] = useState("");
  const [busy, setBusy] = useState(false);
  const [models, setModels] = useState<CloudModels | null>(null);
  const [result, setResult] = useState<CloudTestResult | null>(null);

  async function run<T>(action: () => Promise<T>, done: (value: T) => void) {
    setBusy(true);
    setNotice(null);
    try {
      done(await action());
    } catch (err) {
      setNotice({ kind: "bad", text: errorText(err, "Permintaan gagal.") });
    } finally {
      setBusy(false);
    }
  }

  function save(event: FormEvent) {
    event.preventDefault();
    void run(() => api.aiCloud.putKey(info.name, key), (status) => {
      setKey("");
      setNotice({ kind: "ok", text: `API key ${info.label} tersimpan di komputer ini.` });
      reload(status);
    });
  }

  return (
    <div className="panel" data-testid={`cloud-${info.name}`}>
      <h3>{info.label}{info.role ? ` — ${info.role}` : " — tidak dipakai (.env)"}</h3>
      <dl className="kv">
        <dt>Model (.env)</dt>
        <dd className="wrap">{info.model ?? "—"}{info.free_only && " · hanya model berakhiran :free yang diterima"}</dd>
        <dt>API key</dt>
        <dd data-testid={`cloud-${info.name}-key`}>{info.has_key ? "tersimpan (tidak ditampilkan)" : "belum dimasukkan"}</dd>
        {info.limits && (
          <>
            <dt>Permintaan menit ini</dt>
            <dd>{exact(info.limits.minute_used)} dari batas aman {exact(info.limits.minute_limit)} (batas gratis{" "}
              {exact(info.limits.minute_official)})</dd>
            {info.limits.day_limit !== null && (
              <>
                <dt>Permintaan hari ini</dt>
                <dd>{exact(info.limits.day_used)} dari batas aman {exact(info.limits.day_limit)} (batas gratis{" "}
                  {exact(info.limits.day_official)})</dd>
              </>
            )}
            <dt>Sumber angka</dt><dd>{info.limits.source}</dd>
          </>
        )}
      </dl>
      {info.model_problem && <p className="notice bad" role="alert">{info.model_problem}</p>}

      <form className="form" onSubmit={save}>
        <label htmlFor={`key-${info.name}`}>{info.has_key ? "Ganti API key" : "API key"} (diawali {info.key_prefix})</label>
        <input id={`key-${info.name}`} type="password" autoComplete="off" value={key} maxLength={400}
          onChange={(e) => setKey(e.target.value)} />
        <button type="submit" className="primary" disabled={busy || key.trim().length < 20}>Simpan API key</button>
      </form>
      <p className="muted">
        Buat key di <a href={info.signup_url} target="_blank" rel="noopener noreferrer">{info.signup_url}</a>.
        {info.free_only && " Jangan membeli kredit — ZOI hanya memakai model gratis."}
      </p>
      <p>
        {info.has_key && (
          <button type="button" disabled={busy}
            onClick={() => void run(() => api.aiCloud.deleteKey(info.name), (status) => {
              setNotice({ kind: "ok", text: `API key ${info.label} dihapus dari komputer ini.` });
              reload(status);
            })}>Hapus API key</button>
        )}{" "}
        {info.role && info.has_key && (
          <>
            <button type="button" disabled={busy} data-testid={`cloud-${info.name}-test`}
              onClick={() => void run(() => api.aiCloud.test(info.name), (r) => { setResult(r); reload(); })}>
              Uji model (1 permintaan)
            </button>{" "}
            <button type="button" disabled={busy}
              onClick={() => void run(() => api.aiCloud.models(info.name), setModels)}>Lihat daftar model</button>
          </>
        )}
      </p>
      {result && (
        <p className={`notice ${result.ok ? "ok" : "bad"}`} role="status" data-testid={`cloud-${info.name}-result`}>
          {result.ok ? `Model ${result.model} menjawab: “${result.reply}”` : `Gagal: ${result.error}`}
        </p>
      )}
      {models && (
        <details open data-testid={`cloud-${info.name}-models`}>
          <summary>{models.models.length} model{info.free_only ? " gratis" : ""}</summary>
          <p className="muted">{models.note} Untuk mengganti model, ubah .env lalu jalankan ulang ZOI.</p>
          {!models.current_listed && <p className="notice bad">Model di .env ({models.current}) tidak ada di daftar ini.</p>}
          <ul className="wrap">{models.models.map((m) => <li key={m}>{m}{m === models.current ? " — dipakai" : ""}</li>)}</ul>
        </details>
      )}
    </div>
  );
}

/** Settings › AI Cloud: NVIDIA NIM (utama) dan OpenRouter (cadangan). Gratis, opsional, dipilih lewat .env. */
export function AiCloudPage() {
  const revision = useApp((s) => s.aiRevision);
  const [status, setStatus] = useState<CloudStatus | null>(null);
  const [notice, setNotice] = useState<Notice>(null);

  const fetchStatus = useCallback(() => {
    api.aiCloud.status().then(setStatus)
      .catch((err) => setNotice({ kind: "bad", text: errorText(err, "Status AI cloud tidak dapat dimuat.") }));
  }, []);
  useEffect(() => { fetchStatus(); }, [fetchStatus, revision]);
  const load = (next?: CloudStatus) => (next ? setStatus(next) : fetchStatus());

  return (
    <section className="page" data-testid="ai-cloud-page">
      <h1>AI Cloud</h1>
      <p className="muted"><Link to="/settings">← Settings</Link></p>
      {status?.test_endpoint && (
        <p className="notice warn" data-testid="cloud-test-banner">
          ENDPOINT UJI aktif — “AI cloud” di sini adalah server tiruan di komputer ini, bukan NVIDIA/OpenRouter.
        </p>
      )}
      {notice && <p className={`notice ${notice.kind}`} role="status" data-testid="cloud-notice">{notice.text}</p>}

      {status && (
        <>
          <p className={`notice ${status.enabled ? "warn" : "ok"}`} data-testid="cloud-state">
            {status.enabled
              ? "AI cloud AKTIF. Jawaban dibuat di server pihak lain, dan data di bawah dikirim ke sana."
              : "AI cloud TIDAK aktif. Tidak ada data yang dikirim ke NVIDIA atau OpenRouter."}
          </p>

          <h2>Yang dikirim saat AI cloud aktif</h2>
          <ul data-testid="cloud-data-sent">{status.data_sent.map((d) => <li key={d}>{d}</li>)}</ul>
          <h2>Yang tidak pernah dikirim</h2>
          <ul>{status.never_sent.map((d) => <li key={d}>{d}</li>)}</ul>

          <h2>Penyedia</h2>
          <p className="muted">{status.selection}</p>
          {!status.enabled && (
            <>
              <p>Untuk mengaktifkan, tambahkan baris ini ke file <code>.env</code> lalu jalankan ulang ZOI:</p>
              <pre data-testid="cloud-howto">{status.how_to_enable.join("\n")}</pre>
            </>
          )}
          {status.providers.map((p) => <ProviderCard key={p.name} info={p} reload={load} setNotice={setNotice} />)}

          <h2>Aturan biaya</h2>
          <ul>
            <li>Gratis. ZOI tidak punya jalur berbayar dan menolak model OpenRouter yang tidak berakhiran <code>:free</code>.</li>
            <li>Bila penyedia utama gagal karena batas atau gangguan, ZOI mencoba cadangan sekali dan menuliskannya di jawaban.</li>
            <li>Batas dan ketentuan layanan gratis bisa diubah penyedianya kapan saja.</li>
          </ul>

          <h2>Penyimpanan API key</h2>
          {status.token_storage === "keyring"
            ? <p data-testid="cloud-storage">API key disimpan di penyimpanan kunci sistem (Windows Credential Manager),
                bukan di .env, database, atau browser.</p>
            : <p className="notice warn" data-testid="cloud-storage">{status.storage_warning}</p>}
        </>
      )}
    </section>
  );
}
