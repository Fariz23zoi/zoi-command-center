import {
  api, type CompetitorItem, type CompetitorSnapshot, type CompetitorsData, type PublicVideo, type YouTubeChannel,
  type YouTubeData,
} from "@zoi/api-client";
import { CalendarDays, History, Plus, RefreshCw, Search, Trash2, Trophy, Users } from "lucide-react";
import { type FormEvent, useCallback, useEffect, useState } from "react";

import { formatTime } from "../lib/format";
import { errorText } from "../lib/youtube";
import { Badge, Card, EmptyState } from "../ui";

const nf = new Intl.NumberFormat("id-ID", { notation: "compact", maximumFractionDigits: 1 });
const DAY = 86_400_000;
const isRef = (text: string) => /UC[A-Za-z0-9_-]{22}|@[A-Za-z0-9._-]{3,30}|youtube\.com\//.test(text);

/** Label asal data — wajib di setiap kartu: aktual (YouTube), histori (dikumpulkan ZOI), atau estimasi AI. */
export function DataKind({ kind }: { kind: "actual" | "history" | "ai" }) {
  if (kind === "actual") return <Badge tone="ok">Aktual · YouTube</Badge>;
  if (kind === "history") return <Badge tone="info">Histori dikumpulkan ZOI</Badge>;
  return <Badge tone="warn">Estimasi AI</Badge>;
}

interface Row { id: string; title: string; mine: boolean; channel: YouTubeChannel | null; fetched: string | null;
  videos: PublicVideo[] | null; history: CompetitorSnapshot[]; item?: CompetitorItem }

/** Tab COMPETITORS: data publik YouTube Data API v3 (tanpa login kompetitor), disimpan ≤30 hari, tanpa skor buatan. */
export function CompetitorsTab({ mine }: { mine: YouTubeData | null }) {
  const [data, setData] = useState<CompetitorsData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const run = useCallback(async (fn: () => Promise<CompetitorsData | void>) => {
    setBusy(true);
    setError(null);
    try {
      const next = await fn();
      if (next) setData(next);
    } catch (err) {
      setError(errorText(err, "Permintaan ke YouTube gagal."));
    } finally {
      setBusy(false);
    }
  }, []);

  useEffect(() => {
    api.youtubePublic.competitors().then(setData).catch((err) => setError(errorText(err, "Daftar kompetitor tidak dapat dimuat.")));
  }, []);

  const own = mine?.connected ? mine.channel?.payload ?? null : null;
  const rows: Row[] = [
    ...(own ? [{ id: own.id, title: own.title, mine: true, channel: own, fetched: mine?.channel?.fetched_at ?? null,
      videos: null, history: (mine?.history ?? []).map((h) => ({ ...h })) }] : []),
    ...(data?.items ?? []).map((it) => ({
      id: it.channel_id, title: it.data?.payload.channel.title ?? it.channel_id, mine: false,
      channel: it.data?.payload.channel ?? null, fetched: it.data?.fetched_at ?? null,
      videos: it.data?.payload.videos ?? null, history: it.history, item: it })),
  ];

  async function refreshAll() {
    await run(async () => {
      let last: CompetitorsData | undefined;
      for (const it of data?.items ?? []) last = await api.youtubePublic.refreshCompetitor(it.channel_id);
      return last;
    });
  }

  return (
    <div className="dash-tabpanel" data-testid="competitors-tab">
      <AddCompetitor busy={busy} run={run} full={(data?.items.length ?? 0) >= (data?.max ?? 20)} />
      {error && <p className="notice bad" role="alert">{error}</p>}
      {!data ? <p className="muted">Memuat…</p> : data.items.length === 0 ? (
        <Card>
          <EmptyState icon={Users} title="Belum ada kompetitor">
            Cari channel dengan nama, tautan, atau ID. ZOI hanya membaca data publik dari YouTube Data API v3.
          </EmptyState>
        </Card>
      ) : (
        <>
          <Card title="Compare Channels" action={
            <button type="button" onClick={refreshAll} disabled={busy}>
              <RefreshCw size={16} aria-hidden="true" /> Segarkan semua
            </button>}>
            <p className="dash-legend"><DataKind kind="actual" /> <DataKind kind="history" />
              <span className="muted">Halaman ini tidak memuat estimasi AI.</span></p>
            <CompareTable rows={rows} busy={busy}
              onRefresh={(id) => run(() => api.youtubePublic.refreshCompetitor(id, true))}
              onRemove={(id) => run(() => api.youtubePublic.removeCompetitor(id))} />
            <p className="source">Sumber: {data.source} · data publik channel lain dihapus otomatis setelah {data.retention_days} hari
              (kebijakan YouTube API). Refresh ulang dalam 1 jam memakai cache untuk menghemat kuota.</p>
          </Card>
          <div className="dash-row">
            <PerformanceBars rows={rows} />
            <GrowthTracking rows={rows} />
          </div>
          <div className="dash-row dash-row-2">
            <TopVideos rows={rows} />
            <UploadTimeline rows={rows} />
          </div>
        </>
      )}
    </div>
  );
}

function AddCompetitor({ busy, run, full }: {
  busy: boolean; full: boolean; run(fn: () => Promise<CompetitorsData | void>): Promise<void>;
}) {
  const [text, setText] = useState("");
  const [results, setResults] = useState<YouTubeChannel[] | null>(null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    const q = text.trim();
    if (q.length < 2) return;
    if (isRef(q)) {
      await run(() => api.youtubePublic.addCompetitor(q, ""));
      setText("");
      setResults(null);
    } else {
      await run(async () => setResults((await api.youtubePublic.searchChannels(q)).items));
    }
  }

  return (
    <Card title="Tambah kompetitor">
      <form className="dash-search" onSubmit={submit}>
        <label className="sr-only" htmlFor="comp-q">Nama, tautan, atau ID channel</label>
        <input id="comp-q" value={text} onChange={(e) => setText(e.target.value)} maxLength={300}
          placeholder="Nama channel, @handle, tautan, atau UC…" />
        <button type="submit" className="primary" disabled={busy || full || text.trim().length < 2}>
          <Search size={16} aria-hidden="true" /> {isRef(text) ? "Tambahkan" : "Cari"}
        </button>
      </form>
      <p className="muted dash-note">Pencarian nama memakai 100 unit kuota YouTube; tautan/ID/@handle hanya 1 unit.
        {full && " Daftar pantauan penuh (maks 20)."}</p>
      {results && (results.length === 0 ? <p className="muted">YouTube tidak menemukan channel untuk kata itu.</p> : (
        <ul className="dash-results">
          {results.map((c) => (
            <li key={c.id}>
              <span><b>{c.title}</b> <small className="muted">{c.custom_url}</small></span>
              <small>{c.hidden_subscribers || c.subscriber_count === null ? "subscriber disembunyikan" : `${nf.format(c.subscriber_count)} subscriber`}</small>
              <button type="button" disabled={busy || full}
                onClick={() => run(async () => { const d = await api.youtubePublic.addCompetitor(c.id, ""); setResults(null); return d; })}>
                <Plus size={16} aria-hidden="true" /> Pantau
              </button>
            </li>
          ))}
        </ul>
      ))}
    </Card>
  );
}

function CompareTable({ rows, busy, onRefresh, onRemove }: {
  rows: Row[]; busy: boolean; onRefresh(id: string): void; onRemove(id: string): void;
}) {
  const fmt = (v: number | null | undefined) => (v == null ? "—" : nf.format(v));
  return (
    <div className="table-wrap">
      <table className="data-table" data-testid="compare-table">
        <thead><tr><th scope="col">Channel</th><th scope="col">Subscribers</th><th scope="col">Total views</th>
          <th scope="col">Video</th><th scope="col">Diambil</th><th scope="col"><span className="sr-only">Aksi</span></th></tr></thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.id} className={r.mine ? "mine" : undefined}>
              <th scope="row">{r.title} {r.mine && <Badge tone="primary">Channel saya</Badge>}</th>
              <td>{r.channel?.hidden_subscribers ? "disembunyikan" : fmt(r.channel?.subscriber_count)}</td>
              <td>{fmt(r.channel?.view_count)}</td>
              <td>{fmt(r.channel?.video_count)}</td>
              <td><small>{r.fetched ? formatTime(r.fetched) : "—"}</small></td>
              <td className="actions">
                {!r.mine && <>
                  <button type="button" className="icon-btn" aria-label={`Segarkan ${r.title}`} disabled={busy}
                    onClick={() => onRefresh(r.id)}><RefreshCw size={16} /></button>
                  <button type="button" className="icon-btn" aria-label={`Hapus ${r.title}`} disabled={busy}
                    onClick={() => onRemove(r.id)}><Trash2 size={16} /></button>
                </>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function PerformanceBars({ rows }: { rows: Row[] }) {
  const [metric, setMetric] = useState<"subscriber_count" | "view_count">("subscriber_count");
  const values = rows.map((r) => ({ r, v: r.channel?.hidden_subscribers && metric === "subscriber_count" ? null : r.channel?.[metric] ?? null }));
  const max = Math.max(1, ...values.map((x) => x.v ?? 0));
  return (
    <Card title="Performance Comparison" action={
      <div className="dash-tabs" role="tablist" aria-label="Metrik pembanding">
        {([["subscriber_count", "Subscribers"], ["view_count", "Total views"]] as const).map(([k, label]) => (
          <button key={k} type="button" role="tab" aria-selected={metric === k} className={metric === k ? "on" : undefined}
            onClick={() => setMetric(k)}>{label}</button>
        ))}
      </div>}>
      <ul className="dash-compare">
        {values.map(({ r, v }) => (
          <li key={r.id}>
            <span>{r.title}</span>
            <meter min={0} max={max} value={v ?? 0} aria-label={r.title} className={r.mine ? "mine" : undefined} />
            <b>{v === null ? "—" : nf.format(v)}</b>
          </li>
        ))}
      </ul>
      <p className="dash-legend"><DataKind kind="actual" /></p>
    </Card>
  );
}

function Sparkline({ points }: { points: number[] }) {
  const W = 160, H = 40;
  const min = Math.min(...points), max = Math.max(...points);
  const d = points.map((v, i) => `${i ? "L" : "M"}${((i * W) / (points.length - 1)).toFixed(1)},${(H - 4 - ((v - min) * (H - 8)) / (max - min || 1)).toFixed(1)}`).join("");
  return <svg viewBox={`0 0 ${W} ${H}`} className="dash-spark" aria-hidden="true"><path d={d} /></svg>;
}

function GrowthTracking({ rows }: { rows: Row[] }) {
  return (
    <Card title="Growth Tracking" action={<DataKind kind="history" />}>
      <ul className="dash-growth">
        {rows.map((r) => {
          const pts = r.history.filter((h) => h.subscriber_count !== null && !h.hidden_subscribers);
          const first = pts[0], last = pts.at(-1);
          return (
            <li key={r.id}>
              <span className="name">{r.title}</span>
              {pts.length < 2 || !first || !last ? (
                <small className="muted">
                  {pts.length === 1 ? `Baru 1 titik (${pts[0].day}). ` : "Belum ada titik. "}
                  Histori mulai dikumpulkan saat refresh; ZOI tidak mengarang data sebelumnya.
                </small>
              ) : (
                <>
                  <Sparkline points={pts.map((p) => p.subscriber_count as number)} />
                  <small>
                    {first.day} → {last.day}: {(last.subscriber_count as number) - (first.subscriber_count as number) >= 0 ? "+" : ""}
                    {nf.format((last.subscriber_count as number) - (first.subscriber_count as number))} subscriber
                  </small>
                </>
              )}
            </li>
          );
        })}
      </ul>
      <p className="muted dash-note">Channel lain: maksimal 30 hari ke belakang (aturan YouTube). Channel sendiri: sejak
        pertama terhubung.</p>
    </Card>
  );
}

function TopVideos({ rows }: { rows: Row[] }) {
  const all = rows.flatMap((r) => (r.videos ?? []).map((v) => ({ ...v, owner: r.title })))
    .filter((v) => v.view_count !== null).sort((a, b) => (b.view_count ?? 0) - (a.view_count ?? 0)).slice(0, 8);
  return (
    <Card title="Top Performing Videos" action={<DataKind kind="actual" />}>
      {all.length === 0 ? (
        <EmptyState icon={Trophy} title="Belum ada video">Tekan segarkan pada kompetitor untuk mengambil 25 unggahan terbarunya.</EmptyState>
      ) : (
        <ol className="dash-videos">
          {all.map((v, i) => (
            <li key={v.id ?? i}>
              <span className="rank">{i + 1}</span>
              <span className="title">{v.title}<small className="muted"> · {v.owner}</small></span>
              <span className="nums"><b>{nf.format(v.view_count as number)}</b> views</span>
            </li>
          ))}
        </ol>
      )}
      <p className="muted dash-note">Diurutkan menurut jumlah tayangan dari YouTube, di antara 25 unggahan terbaru tiap kompetitor.</p>
    </Card>
  );
}

function UploadTimeline({ rows }: { rows: Row[] }) {
  const [now] = useState(() => Date.now());
  const span = 90 * DAY;
  const withVideos = rows.filter((r) => r.videos && r.videos.length > 0);
  return (
    <Card title="Upload Frequency" action={<DataKind kind="actual" />}>
      {withVideos.length === 0 ? (
        <EmptyState icon={CalendarDays} title="Belum ada tanggal unggah">Segarkan kompetitor untuk mengambil video terbarunya.</EmptyState>
      ) : (
        <ul className="dash-timeline" aria-label="Tanggal unggah 90 hari terakhir">
          {withVideos.map((r) => (
            <li key={r.id}>
              <span className="name">{r.title}</span>
              <span className="track">
                {(r.videos ?? []).filter((v) => v.published_at && now - Date.parse(v.published_at) <= span).map((v) => (
                  <i key={v.id} title={`${v.title} — ${v.published_at?.slice(0, 10)}`}
                    style={{ left: `${100 - ((now - Date.parse(v.published_at as string)) / span) * 100}%` }} />
                ))}
              </span>
            </li>
          ))}
        </ul>
      )}
      <p className="muted dash-note"><History size={14} aria-hidden="true" /> Tiap titik = satu video menurut tanggal publish dari
        YouTube (90 hari terakhir, kanan = hari ini). Hanya 25 unggahan terbaru yang diambil.</p>
    </Card>
  );
}
