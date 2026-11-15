import type { YouTubeData, YouTubeReport } from "@zoi/api-client";
import { Link } from "react-router-dom";

import { formatTime } from "../lib/format";
import { exact, METRIC_LABEL, useYouTubeData } from "../lib/youtube";

export function NotConnected({ title }: { title: string }) {
  return (
    <section className="page" data-testid="youtube-not-connected">
      <h1>{title}</h1>
      <p>Channel YouTube belum terhubung, jadi tidak ada angka yang bisa ditampilkan.</p>
      <p><Link to="/settings/youtube">Hubungkan di Settings › YouTube</Link></p>
      <p className="muted">ZOI tidak menampilkan data contoh agar tidak ada angka yang terlihat seperti data asli.</p>
    </section>
  );
}

export function SourceLine({ data, fetchedAt }: { data: YouTubeData; fetchedAt: string | null | undefined }) {
  return (
    <p className="source" data-testid="youtube-source">
      Sumber: {data.source} · diambil {fetchedAt ? formatTime(fetchedAt) : "—"}
    </p>
  );
}

function ReportTable({ report, testId }: { report: YouTubeReport; testId: string }) {
  if (report.rows.length === 0) return <p className="muted">YouTube tidak mengirim baris untuk periode ini.</p>;
  return (
    <div className="table-wrap">
      <table className="data-table" data-testid={testId}>
        <thead><tr>{report.columns.map((c) => <th key={c} scope="col">{METRIC_LABEL[c] ?? c}</th>)}</tr></thead>
        <tbody>
          {report.rows.map((row, i) => (
            <tr key={String(row.day ?? i)}>{report.columns.map((c) => <td key={c}>{exact(row[c])}</td>)}</tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Channel Analytics: angka channel milik pengguna, persis seperti dikirim YouTube. Tidak ada skor buatan ZOI. */
export function AnalyticsPage() {
  const { data, error, busy, refresh } = useYouTubeData();
  if (!data) {
    return (
      <section className="page"><h1>Channel Analytics</h1>
        {error ? <p className="notice bad" role="alert">{error}</p> : <p className="muted">Memuat…</p>}
      </section>
    );
  }
  if (!data.connected) return <NotConnected title="Channel Analytics" />;

  const channel = data.channel?.payload;
  const analytics = data.analytics?.payload;
  const videos = data.videos?.payload;

  return (
    <section className="page" data-testid="analytics-page">
      <h1>Channel Analytics</h1>
      {data.test_endpoint && (
        <p className="notice warn" data-testid="youtube-test-banner">
          ENDPOINT UJI — angka di bawah berasal dari server tiruan, bukan YouTube.
        </p>
      )}
      {error && <p className="notice bad" role="alert" data-testid="analytics-error">{error}</p>}
      {data.account?.needs_reauth && (
        <p className="notice bad" role="alert">Izin YouTube tidak berlaku lagi.{" "}
          <Link to="/settings/youtube">Hubungkan ulang</Link>.</p>
      )}
      {data.purged_unverified && (
        <p className="notice warn">Data lama dihapus karena izin tidak terverifikasi lebih dari 30 hari (aturan
          YouTube). Ambil data terbaru untuk mengisinya lagi.</p>
      )}
      <p>
        <button type="button" disabled={busy} data-testid="youtube-refresh" onClick={() => void refresh()}>
          {busy ? "Mengambil dari YouTube…" : "Ambil data terbaru"}
        </button>{" "}
        <span className="muted">Memakai 3 unit kuota dan 4 panggilan laporan. Terpakai hari ini:{" "}
          {exact(data.quota.units_used)} dari {exact(data.quota.unit_limit)} unit.</span>
      </p>

      <h2>Channel</h2>
      {channel ? (
        <>
          <dl className="kv" data-testid="channel-stats">
            <dt>Nama</dt><dd>{channel.title}{channel.custom_url ? ` · ${channel.custom_url}` : ""}</dd>
            <dt>Subscriber</dt>
            <dd>{channel.hidden_subscribers ? "disembunyikan di channel" : exact(channel.subscriber_count)}</dd>
            <dt>Total tayangan</dt><dd>{exact(channel.view_count)}</dd>
            <dt>Jumlah video</dt><dd>{exact(channel.video_count)}</dd>
          </dl>
          <p className="muted">YouTube membulatkan jumlah subscriber di API (tiga angka penting).</p>
          <SourceLine data={data} fetchedAt={data.channel?.fetched_at} />
        </>
      ) : <p className="muted" data-testid="no-channel-data">Belum ada data. Tekan “Ambil data terbaru”.</p>}

      <h2>28 hari terakhir</h2>
      {analytics?.error && <p className="notice bad" data-testid="analytics-report-error">{analytics.error}</p>}
      {analytics?.last_28_days ? (
        <>
          <p className="muted">{analytics.last_28_days.start} s.d. {analytics.last_28_days.end}</p>
          <ReportTable report={analytics.last_28_days} testId="report-28" />
          <SourceLine data={data} fetchedAt={data.analytics?.fetched_at} />
        </>
      ) : !analytics?.error && <p className="muted">Belum ada laporan.</p>}

      {analytics?.daily && (
        <details>
          <summary>Per hari ({analytics.daily.rows.length} baris)</summary>
          <ReportTable report={analytics.daily} testId="report-daily" />
        </details>
      )}

      <h2>Video terbaru</h2>
      {videos && videos.length > 0 ? (
        <>
          <div className="table-wrap">
            <table className="data-table" data-testid="video-table">
              <thead><tr>
                <th scope="col">Judul</th><th scope="col">Terbit</th><th scope="col">Status</th>
                <th scope="col">Tayangan</th><th scope="col">Suka</th><th scope="col">Komentar</th>
              </tr></thead>
              <tbody>
                {videos.map((v) => (
                  <tr key={v.id}>
                    <td>{v.title}</td><td>{formatTime(v.published_at)}</td><td>{v.privacy ?? "—"}</td>
                    <td>{exact(v.view_count)}</td><td>{exact(v.like_count)}</td><td>{exact(v.comment_count)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <SourceLine data={data} fetchedAt={data.videos?.fetched_at} />
        </>
      ) : <p className="muted">{videos ? "Channel ini belum punya video." : "Belum ada data video."}</p>}

      <h2>Riwayat harian yang dicatat ZOI</h2>
      {data.history.length > 0 ? (
        <div className="table-wrap">
          <table className="data-table" data-testid="history-table">
            <thead><tr>
              <th scope="col">Tanggal</th><th scope="col">Subscriber</th><th scope="col">Total tayangan</th>
              <th scope="col">Jumlah video</th><th scope="col">Diambil</th>
            </tr></thead>
            <tbody>
              {data.history.map((h) => (
                <tr key={h.day}>
                  <td>{h.day}</td><td>{h.hidden_subscribers ? "disembunyikan" : exact(h.subscriber_count)}</td>
                  <td>{exact(h.view_count)}</td><td>{exact(h.video_count)}</td><td>{formatTime(h.fetched_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : <p className="muted">Belum ada catatan. Satu baris ditambahkan setiap hari kamu mengambil data.</p>}
    </section>
  );
}
