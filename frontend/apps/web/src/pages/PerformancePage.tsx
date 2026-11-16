import { Link } from "react-router-dom";

import { exact, METRIC_LABEL, useYouTubeData } from "../lib/youtube";
import { NotConnected, SourceLine } from "./AnalyticsPage";

/** Performance: laporan per video channel sendiri dari YouTube Analytics. Tidak ada hitungan buatan ZOI. */
export function PerformancePage() {
  const { data, error, busy, refresh } = useYouTubeData();
  if (!data) {
    return (
      <section className="page"><h1>Performance</h1>
        {error ? <p className="notice bad" role="alert">{error}</p> : <p className="muted">Memuat…</p>}
      </section>
    );
  }
  if (!data.connected) return <NotConnected title="Performance" />;

  const analytics = data.analytics?.payload;
  const report = analytics?.by_video;
  const titles = new Map((data.videos?.payload ?? []).map((v) => [v.id, v.title]));

  return (
    <section className="page" data-testid="performance-page">
      <h1>Performance</h1>
      {data.test_endpoint && (
        <p className="notice warn" data-testid="youtube-test-banner">
          ENDPOINT UJI — angka di bawah berasal dari server tiruan, bukan YouTube.
        </p>
      )}
      {error && <p className="notice bad" role="alert">{error}</p>}
      <p>
        <button type="button" disabled={busy} data-testid="youtube-refresh" onClick={() => void refresh()}>
          {busy ? "Mengambil dari YouTube…" : "Ambil data terbaru"}
        </button>
      </p>

      <h2>Per video, 28 hari terakhir</h2>
      {(analytics?.by_video_error ?? analytics?.error) && (
        <p className="notice bad" data-testid="performance-error">{analytics?.by_video_error ?? analytics?.error}</p>
      )}
      {report && report.rows.length > 0 ? (
        <>
          <p className="muted">
            {report.start} s.d. {report.end} · urutan dari YouTube (tayangan terbanyak). “Rata-rata persentase ditonton”
            dihitung oleh YouTube, bukan ZOI.
          </p>
          <div className="table-wrap">
            <table className="data-table" data-testid="performance-table">
              <thead><tr>
                <th scope="col">Video</th>
                {report.columns.filter((c) => c !== "video").map((c) => <th key={c} scope="col">{METRIC_LABEL[c] ?? c}</th>)}
              </tr></thead>
              <tbody>
                {report.rows.map((row) => {
                  const id = String(row.video);
                  return (
                    <tr key={id}>
                      <td>{titles.get(id) ?? `ID ${id} (judul tidak ada di daftar video terbaru)`}</td>
                      {report.columns.filter((c) => c !== "video").map((c) => <td key={c}>{exact(row[c])}</td>)}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <SourceLine data={data} fetchedAt={data.analytics?.fetched_at} />
        </>
      ) : !analytics?.by_video_error && !analytics?.error && (
        <p className="muted" data-testid="performance-empty">Belum ada laporan. Tekan “Ambil data terbaru”.</p>
      )}

      <h2>Waktu upload</h2>
      <p className="muted" data-testid="upload-time-note">
        YouTube API tidak menyediakan laporan “kapan penontonmu aktif”, dan ZOI tidak menebaknya dari angka lain. Lihat
        kartu “When your viewers are on YouTube” di YouTube Studio › Analytics › Audience.
      </p>
      <p><Link to="/analytics">Channel Analytics</Link></p>
    </section>
  );
}
