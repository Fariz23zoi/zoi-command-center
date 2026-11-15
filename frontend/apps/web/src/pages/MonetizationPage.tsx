import { exact, METRIC_LABEL, useYouTubeData } from "../lib/youtube";
import { NotConnected, SourceLine } from "./AnalyticsPage";

/**
 * Monetization: syarat resmi YPP berdampingan dengan angka channel dari YouTube.
 * ZOI sengaja TIDAK menghitung persentase, sisa, atau perkiraan — kebijakan YouTube melarang metrik turunan,
 * dan angka kelayakan yang sah hanya ada di YouTube Studio.
 */
export function MonetizationPage() {
  const { data, error, busy, refresh } = useYouTubeData();
  if (!data) {
    return (
      <section className="page"><h1>Monetization</h1>
        {error ? <p className="notice bad" role="alert">{error}</p> : <p className="muted">Memuat…</p>}
      </section>
    );
  }
  const ypp = data.ypp;
  const channel = data.channel?.payload;
  const year = data.analytics?.payload.last_365_days;
  const yearRow = year?.rows[0];

  const requirements = (
    <>
      <h2>Syarat resmi YouTube Partner Program</h2>
      <p className="muted">Dicek di halaman resmi YouTube pada {ypp.checked_at}. {ypp.note}</p>
      {ypp.tiers.map((tier) => (
        <div key={tier.name} className="panel" data-testid="ypp-tier">
          <h3>{tier.name}</h3>
          <ul>{tier.requirements.map((r) => <li key={r}>{r}</li>)}</ul>
          <p className="source">Sumber: <a href={tier.source} target="_blank" rel="noopener noreferrer">{tier.source}</a></p>
        </div>
      ))}
      <ul className="muted">{ypp.caveats.map((c) => <li key={c}>{c}</li>)}</ul>
      {ypp.unverified.map((u) => <p key={u} className="notice warn" data-testid="ypp-unverified">Belum terverifikasi: {u}</p>)}
    </>
  );

  if (!data.connected) {
    return (
      <>
        <NotConnected title="Monetization" />
        <section className="page">{requirements}</section>
      </>
    );
  }

  return (
    <section className="page" data-testid="monetization-page">
      <h1>Monetization</h1>
      {data.test_endpoint && (
        <p className="notice warn" data-testid="youtube-test-banner">
          ENDPOINT UJI — angka channel di bawah berasal dari server tiruan, bukan YouTube.
        </p>
      )}
      {error && <p className="notice bad" role="alert">{error}</p>}
      <p className="notice warn" data-testid="ypp-disclaimer">
        ZOI menampilkan syarat dan angka apa adanya, tanpa menghitung persentase atau sisa. Kelayakan sebenarnya
        (jam tonton publik yang sah, tayangan Shorts yang memenuhi syarat) hanya ada di YouTube Studio › Earn.
      </p>

      <h2>Angka channel-mu dari YouTube</h2>
      <p>
        <button type="button" disabled={busy} data-testid="youtube-refresh" onClick={() => void refresh()}>
          {busy ? "Mengambil dari YouTube…" : "Ambil data terbaru"}
        </button>
      </p>
      {channel ? (
        <>
          <dl className="kv" data-testid="ypp-channel-numbers">
            <dt>Subscriber</dt>
            <dd>{channel.hidden_subscribers ? "disembunyikan di channel" : exact(channel.subscriber_count)}</dd>
            {yearRow && year && (
              <>
                <dt>{METRIC_LABEL.estimatedMinutesWatched}, {year.start} s.d. {year.end}</dt>
                <dd>{exact(yearRow.estimatedMinutesWatched)} menit</dd>
                <dt>{METRIC_LABEL.views}, periode yang sama</dt><dd>{exact(yearRow.views)}</dd>
              </>
            )}
          </dl>
          <p className="muted">
            Menit ditonton di atas mencakup SEMUA tayangan menurut YouTube Analytics (termasuk Shorts dan video
            non-publik), jadi bukan angka “jam tonton publik yang sah” yang dipakai YPP.
          </p>
          {data.analytics?.payload.error && <p className="notice bad">{data.analytics.payload.error}</p>}
          <SourceLine data={data} fetchedAt={data.analytics?.fetched_at ?? data.channel?.fetched_at} />
        </>
      ) : <p className="muted">Belum ada data. Tekan “Ambil data terbaru”.</p>}

      {requirements}
    </section>
  );
}
