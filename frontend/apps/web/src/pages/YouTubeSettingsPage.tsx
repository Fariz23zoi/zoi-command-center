import { api, type YouTubeStatus } from "@zoi/api-client";
import { type ChangeEvent, useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { formatTime } from "../lib/format";
import { errorText, exact } from "../lib/youtube";
import { useApp } from "../stores/appStore";

const SCOPE_LABEL: Record<string, string> = {
  "https://www.googleapis.com/auth/youtube.readonly": "Melihat channel dan video-mu (hanya-baca)",
  "https://www.googleapis.com/auth/yt-analytics.readonly": "Melihat laporan YouTube Analytics (hanya-baca)",
};

/** Settings › YouTube: impor client OAuth, hubungkan akun lewat halaman Google, kuota, putuskan & hapus data. */
export function YouTubeSettingsPage() {
  const revision = useApp((s) => s.youtubeRevision);
  const [status, setStatus] = useState<YouTubeStatus | null>(null);
  const [authUrl, setAuthUrl] = useState<string | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [notice, setNotice] = useState<{ kind: "ok" | "bad" | "warn"; text: string } | null>(null);

  const load = useCallback(() => {
    api.youtube.status().then(setStatus)
      .catch((err) => setNotice({ kind: "bad", text: errorText(err, "Status YouTube tidak dapat dimuat.") }));
  }, []);
  useEffect(() => { load(); }, [load, revision]);

  async function run(action: () => Promise<unknown>, ok?: string) {
    setNotice(null);
    try {
      await action();
      if (ok) setNotice({ kind: "ok", text: ok });
    } catch (err) {
      setNotice({ kind: "bad", text: errorText(err, "Permintaan gagal.") });
    }
    load();
  }

  async function importClient(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    let parsed: unknown;
    try {
      parsed = JSON.parse(await file.text());
    } catch {
      setNotice({ kind: "bad", text: "File itu bukan JSON yang valid." });
      return;
    }
    await run(() => api.youtube.putClient(parsed), status?.web_flow
      ? "File client OAuth tersimpan terenkripsi di database ZOI."
      : "File client OAuth tersimpan di komputer ini.");
  }

  async function connect() {
    await run(async () => {
      const started = await api.youtube.connect();
      setAuthUrl(started.auth_url);
      if (status?.web_flow) {
        // Mode online: pindah di tab yang sama — Google mengembalikanmu ke halaman ini sesudah memberi izin.
        window.location.assign(started.auth_url);
      } else {
        window.open(started.auth_url, "_blank", "noopener,noreferrer");
      }
    });
  }

  async function disconnect() {
    setConfirming(false);
    setNotice(null);
    try {
      const result = await api.youtube.disconnect();
      setNotice(result.note ? { kind: "warn", text: result.note }
        : { kind: "ok", text: "Akun diputuskan. Token dicabut di Google dan semua data YouTube di komputer ini dihapus." });
    } catch (err) {
      setNotice({ kind: "bad", text: errorText(err, "Gagal memutuskan akun.") });
    }
    load();
  }

  const pending = status?.pending ?? false;
  const account = status?.account ?? null;

  return (
    <section className="page" data-testid="youtube-settings">
      <h1>YouTube</h1>
      <p className="muted"><Link to="/settings">← Settings</Link></p>
      {status?.test_endpoint && (
        <p className="notice warn" data-testid="youtube-test-banner">
          ENDPOINT UJI aktif — halaman ini berbicara dengan server tiruan di komputer ini, bukan Google/YouTube.
        </p>
      )}
      {notice && <p className={`notice ${notice.kind}`} role="status" data-testid="youtube-notice">{notice.text}</p>}
      {status?.last_error && !pending && !account && (
        <p className="notice bad" role="alert" data-testid="youtube-last-error">{status.last_error}</p>
      )}

      <h2>Yang ZOI lakukan dan tidak lakukan</h2>
      <ul>
        <li>Login terjadi di halaman Google. ZOI tidak pernah melihat atau meminta password Google-mu.</li>
        <li>Izin yang diminta hanya-baca. ZOI tidak bisa mengunggah, mengubah, atau menghapus apa pun di YouTube.</li>
        <li>YouTube Data API dan Analytics API gratis dengan kuota harian. Tidak ada pembayaran.</li>
        {status && <li>{status.policy.summary}</li>}
      </ul>

      {status && !account && (
        <>
          <h2>1. File client OAuth</h2>
          {status.client_configured ? (
            <p data-testid="youtube-client">
              Tersimpan: <code>{status.client_id_hint}</code>{" "}
              <button type="button" disabled={pending}
                onClick={() => void run(() => api.youtube.deleteClient(), "File client dihapus.")}>Hapus file client</button>
            </p>
          ) : (
            status.web_flow ? (
              <p className="muted" data-testid="youtube-web-howto">
                Buat <strong>OAuth client ID</strong> bertipe <strong>Web application</strong> di Google Cloud.
                Pada <em>Authorized redirect URIs</em>, isi persis: <code>{status.callback_url}</code>.
                Unduh file JSON-nya lalu pilih di sini — isinya disimpan <strong>terenkripsi di database</strong>
                dan tidak pernah dikembalikan ke browser. Jangan unggah file itu ke chat atau GitHub.
              </p>
            ) : (
            <p className="muted">
              Buat <strong>OAuth client ID</strong> bertipe <strong>Desktop app</strong> di Google Cloud, unduh file
              JSON-nya, lalu pilih di sini. Langkah lengkap ada di <code>docs/MIGRATION_TO_LOCAL_SERVER.md</code>.
              File ini hanya dikirim ke backend ZOI di komputer ini — jangan unggah ke chat atau GitHub.
            </p>
            )
          )}
          <label className="form">
            <span>{status.client_configured ? "Ganti file client (.json)" : "Pilih file client (.json)"}</span>
            <input type="file" accept="application/json,.json" data-testid="youtube-client-file" disabled={pending}
              onChange={(e) => void importClient(e)} />
          </label>

          <h2>2. Hubungkan channel</h2>
          {pending ? (
            <div className="notice warn" data-testid="youtube-pending">
              <p>Menunggu persetujuanmu di tab Google…</p>
              {authUrl && (
                <p><a href={authUrl} target="_blank" rel="noopener noreferrer">Buka halaman izin Google</a> (bila tab
                  tidak terbuka sendiri).</p>
              )}
              <button type="button" onClick={() => void run(() => api.youtube.cancelConnect())}>Batal</button>
            </div>
          ) : (
            <button type="button" disabled={!status.client_configured} data-testid="youtube-connect"
              onClick={() => void connect()}>Hubungkan akun YouTube</button>
          )}
        </>
      )}

      {status && account && (
        <>
          <h2>Akun terhubung</h2>
          {account.needs_reauth && (
            <p className="notice bad" role="alert" data-testid="youtube-reauth">
              Izin sudah tidak berlaku atau token tidak ada di komputer ini. Putuskan akun, lalu hubungkan ulang.
            </p>
          )}
          <dl className="kv" data-testid="youtube-account">
            <dt>Channel</dt><dd>{account.title}{account.custom_url ? ` · ${account.custom_url}` : ""}</dd>
            <dt>ID channel</dt><dd className="wrap">{account.channel_id}</dd>
            <dt>Terhubung sejak</dt><dd>{formatTime(account.connected_at)}</dd>
            <dt>Izin terakhir diverifikasi</dt><dd>{formatTime(account.verified_at)}</dd>
            <dt>Izin</dt>
            <dd>{account.scopes.map((s) => SCOPE_LABEL[s] ?? s).join(" · ")}
              {!account.analytics_granted && " · izin laporan Analytics TIDAK diberikan"}</dd>
          </dl>
          <p className="muted">
            Data channel yang tersimpan dihapus otomatis bila izin tidak terverifikasi lebih dari{" "}
            {status.policy.reverify_days} hari (aturan YouTube). Mengambil data terbaru memverifikasinya kembali.
          </p>
          <p><Link to="/analytics">Channel Analytics</Link> · <Link to="/monetization">Monetization</Link></p>
          {confirming ? (
            <div className="notice warn" data-testid="youtube-disconnect-confirm">
              <p>Token dicabut dan SEMUA data YouTube di komputer ini dihapus (statistik, video, riwayat harian).
                Tidak bisa dibatalkan.</p>
              <button type="button" onClick={() => void disconnect()}>Ya, putuskan dan hapus</button>{" "}
              <button type="button" onClick={() => setConfirming(false)}>Batal</button>
            </div>
          ) : (
            <button type="button" data-testid="youtube-disconnect" onClick={() => setConfirming(true)}>
              Putuskan &amp; hapus data
            </button>
          )}
        </>
      )}

      {status && (
        <>
          <h2>Penyimpanan token</h2>
          {status.token_storage === "keyring" ? (
            <p data-testid="youtube-storage">Token disimpan di penyimpanan kunci sistem (Windows Credential Manager),
              bukan di database, file ekspor, atau browser.</p>
          ) : status.token_storage === "database" ? (
            <p data-testid="youtube-storage">Token disimpan <strong>terenkripsi</strong> di database ZOI online; kunci
              enkripsinya hanya ada di pengaturan Render. Token tidak pernah ikut file cadangan atau dikirim ke browser.</p>
          ) : (
            <p className="notice warn" data-testid="youtube-storage">{status.storage_warning}</p>
          )}

          <h2>Kuota YouTube API hari ini</h2>
          <dl className="kv" data-testid="youtube-quota">
            <dt>Unit terpakai</dt>
            <dd>{exact(status.quota.units_used)} dari batas aman {exact(status.quota.unit_limit)}{" "}
              (batas resmi {exact(status.quota.units_official)})</dd>
            <dt>Panggilan laporan Analytics</dt><dd>{exact(status.quota.analytics_calls)}</dd>
            <dt>Reset</dt><dd>{formatTime(status.quota.resets_at)} (tengah malam waktu Pasifik)</dd>
            <dt>Sumber angka</dt><dd>{status.quota.source}</dd>
          </dl>
        </>
      )}
    </section>
  );
}
