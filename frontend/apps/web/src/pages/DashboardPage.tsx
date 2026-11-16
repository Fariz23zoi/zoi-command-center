import type { YouTubeData, YouTubeReport } from "@zoi/api-client";
import {
  BarChart3, Clapperboard, Clock, Eye, Inbox, Lightbulb, ListChecks, MonitorSmartphone, PlaySquare, Search, Sparkles,
  Users,
} from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";

import { formatTime } from "../lib/format";
import { useYouTubeData } from "../lib/youtube";
import { useApp } from "../stores/appStore";
import { Badge, Card, EmptyState, StatCard } from "../ui";
import "./dashboard.css";

const nf = new Intl.NumberFormat("id-ID", { notation: "compact", maximumFractionDigits: 1 });
const pf = new Intl.NumberFormat("id-ID", { maximumFractionDigits: 1 });

/** Label resmi dimensi YouTube Analytics (insightTrafficSourceType / deviceType). Kode lain ditampilkan apa adanya. */
const TRAFFIC: Record<string, string> = {
  YT_SEARCH: "YouTube Search", SUGGESTED: "Suggested Videos", BROWSE: "Browse Features", EXT_URL: "External",
  SHORTS: "Shorts Feed", PLAYLIST: "Playlist", CHANNEL: "Halaman channel", NOTIFICATION: "Notifikasi",
  SUBSCRIBER: "Subscriber", YT_OTHER_PAGE: "Halaman YouTube lain", END_SCREEN: "End screen", NO_LINK_OTHER: "Langsung/tak dikenal",
  RELATED_VIDEO: "Video terkait", HASHTAGS: "Hashtag", YT_CHANNEL: "Channel",
};
const DEVICES: Record<string, string> = {
  MOBILE: "Mobile", DESKTOP: "Desktop", TABLET: "Tablet", TV: "TV", GAME_CONSOLE: "Konsol game",
  UNKNOWN_PLATFORM: "Lainnya",
};
const SLICE_COLORS = ["#a78bfa", "#6366f1", "#22d3ee", "#fbbf24", "#9292a8"];

const num = (v: unknown): number | null => (typeof v === "number" && Number.isFinite(v) ? v : null);
const total = (r: YouTubeReport | undefined, key: string) => num(r?.rows[0]?.[key]);

function delta(now: number | null, before: number | null) {
  if (now === null || before === null || before === 0) return null;
  const pct = ((now - before) / before) * 100;
  return { text: `${pct >= 0 ? "+" : ""}${pf.format(pct)}%`, up: pct >= 0 };
}

/** Dashboard ZOI Universe: semua angka dari YouTube Analytics milik pengguna; tanpa data → kartu kosong. */
export function DashboardPage() {
  const { data } = useYouTubeData();
  const connected = Boolean(data?.connected);

  return (
    <section className="page dash" data-testid="dashboard-page">
      <Welcome />
      {!data ? (
        <p className="muted">Memuat data channel…</p>
      ) : connected ? (
        <ChannelPanels data={data} />
      ) : (
        <Card>
          <EmptyState icon={PlaySquare} title="Channel YouTube belum terhubung"
            action={<Link className="dash-cta" to="/settings/youtube">Hubungkan YouTube</Link>}>
            Statistik, performa, sumber traffic, dan video terbaik muncul setelah channel-mu terhubung lewat OAuth resmi.
            ZOI tidak menampilkan angka contoh.
          </EmptyState>
        </Card>
      )}
      <div className="dash-row dash-row-2">
        <RecentActivity />
        <QuickAccess />
      </div>
    </section>
  );
}

function Welcome() {
  const flow = [
    { to: "/analytics", label: "Analisis Channel", icon: BarChart3 },
    { to: "/trends", label: "Riset Tren", icon: Search },
    { to: "/ideas", label: "Ide Konten", icon: Lightbulb },
    { to: "/production", label: "Buat Video", icon: Clapperboard },
  ];
  return (
    <div className="dash-hero">
      <div className="dash-orb" aria-hidden="true" />
      <div>
        <h1>Selamat datang di ZOI Universe</h1>
        <p>Pusat analisis, riset, dan produksi konten berbasis AI.</p>
        <ol className="dash-flow">
          {flow.map(({ to, label, icon: Icon }, i) => (
            <li key={to}>
              <Link to={to} className={i === 0 ? "first" : undefined}><Icon size={18} aria-hidden="true" />{label}</Link>
            </li>
          ))}
        </ol>
      </div>
    </div>
  );
}

function ChannelPanels({ data }: { data: YouTubeData }) {
  const channel = data.channel?.payload;
  const a = data.analytics?.payload;
  const now = a?.last_28_days;
  const prev = a?.previous_28_days;
  const views = total(now, "views");
  const minutes = total(now, "estimatedMinutesWatched");
  const gained = total(now, "subscribersGained");
  const lost = total(now, "subscribersLost");
  const net = gained !== null && lost !== null ? gained - lost : null;
  const subs = channel?.hidden_subscribers ? null : num(channel?.subscriber_count);

  return (
    <>
      <div className="dash-stats">
        <StatCard label="Total Views (28 hari)" icon={Eye} value={views === null ? null : nf.format(views)}
          delta={delta(views, total(prev, "views"))} hint="vs 28 hari sebelumnya" />
        <StatCard label="Subscribers" icon={Users} value={subs === null ? null : nf.format(subs)}
          delta={net === null ? null : { text: `${net >= 0 ? "+" : ""}${pf.format(net)} (28 hari)`, up: net >= 0 }}
          hint={channel?.hidden_subscribers ? "Jumlah disembunyikan di YouTube" : "bersih 28 hari"} />
        <StatCard label="Watch Time (28 hari)" icon={Clock} tone="info"
          value={minutes === null ? null : `${nf.format(minutes / 60)} jam`}
          delta={delta(minutes, total(prev, "estimatedMinutesWatched"))} hint="vs 28 hari sebelumnya" />
        <StatCard label="Total Video" icon={PlaySquare} tone="warn"
          value={channel?.video_count == null ? null : pf.format(channel.video_count)} hint="video publik di channel" />
      </div>
      {a?.error && <p className="notice bad" role="alert">{a.error}</p>}
      <div className="dash-row">
        <PerformanceChart report={a?.daily} />
        <div className="dash-col">
          <Breakdown title="Sumber Traffic" icon={Sparkles} report={a?.traffic_sources} labels={TRAFFIC}
            dim="insightTrafficSourceType" kind="donut" error={a?.breakdown_error} />
          <Breakdown title="Perangkat Penonton" icon={MonitorSmartphone} report={a?.devices} labels={DEVICES}
            dim="deviceType" kind="bars" error={a?.breakdown_error} />
        </div>
      </div>
      <TopVideos data={data} />
      <p className="source">Sumber: {data.source} · diambil {formatTime(data.analytics?.fetched_at)}</p>
    </>
  );
}

const SERIES = [
  { key: "views", label: "Views", pick: (r: Record<string, string | number>) => num(r.views) },
  { key: "subs", label: "Subscribers", pick: (r: Record<string, string | number>) => {
    const g = num(r.subscribersGained); const l = num(r.subscribersLost);
    return g === null || l === null ? null : g - l;
  } },
  { key: "watch", label: "Watch Time (jam)", pick: (r: Record<string, string | number>) => {
    const m = num(r.estimatedMinutesWatched); return m === null ? null : m / 60;
  } },
] as const;

function PerformanceChart({ report }: { report: YouTubeReport | undefined }) {
  const [series, setSeries] = useState<(typeof SERIES)[number]["key"]>("views");
  const def = SERIES.find((s) => s.key === series) ?? SERIES[0];
  const rows = report?.rows ?? [];
  const points = rows.map((r) => ({ day: String(r.day ?? ""), v: def.pick(r) })).filter((p) => p.v !== null) as
    { day: string; v: number }[];

  const W = 640, H = 220, P = 28;
  const max = Math.max(1, ...points.map((p) => p.v));
  const min = Math.min(0, ...points.map((p) => p.v));
  const x = (i: number) => P + (i * (W - 2 * P)) / Math.max(1, points.length - 1);
  const y = (v: number) => H - P - ((v - min) * (H - 2 * P)) / (max - min || 1);
  const line = points.map((p, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(p.v).toFixed(1)}`).join("");
  const last = points.at(-1);

  return (
    <Card title="Performa Channel" className="dash-chart" action={
      <div className="dash-tabs" role="tablist" aria-label="Metrik">
        {SERIES.map((s) => (
          <button key={s.key} type="button" role="tab" aria-selected={s.key === series}
            className={s.key === series ? "on" : undefined} onClick={() => setSeries(s.key)}>{s.label}</button>
        ))}
      </div>}>
      {points.length < 2 ? (
        <EmptyState icon={BarChart3} title="Belum ada data harian">YouTube belum mengirim laporan harian untuk 28 hari terakhir.</EmptyState>
      ) : (
        <figure className="dash-svg">
          <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`${def.label} harian, 28 hari terakhir`}>
            <defs>
              <linearGradient id="dashFill" x1="0" x2="0" y1="0" y2="1">
                <stop offset="0" stopColor="#8b5cf6" stopOpacity=".45" />
                <stop offset="1" stopColor="#8b5cf6" stopOpacity="0" />
              </linearGradient>
            </defs>
            {[0, 0.5, 1].map((t) => (
              <line key={t} x1={P} x2={W - P} y1={P + t * (H - 2 * P)} y2={P + t * (H - 2 * P)} className="grid" />
            ))}
            <path d={`${line}L${x(points.length - 1)},${H - P}L${x(0)},${H - P}Z`} fill="url(#dashFill)" />
            <path d={line} className="stroke" />
            {last && <circle cx={x(points.length - 1)} cy={y(last.v)} r="4.5" className="dot" />}
          </svg>
          <figcaption>
            <span>{points[0].day}</span>
            {last && <b>{last.day}: {pf.format(last.v)}</b>}
            <span>{last?.day}</span>
          </figcaption>
        </figure>
      )}
    </Card>
  );
}

interface BreakdownProps {
  title: string; icon: typeof Sparkles; report: YouTubeReport | undefined; labels: Record<string, string>;
  dim: string; kind: "donut" | "bars"; error?: string;
}

function Breakdown({ title, icon, report, labels, dim, kind, error }: BreakdownProps) {
  const rows = (report?.rows ?? []).map((r) => ({ key: String(r[dim]), v: num(r.views) ?? 0 }));
  const sum = rows.reduce((s, r) => s + r.v, 0);
  if (!sum) {
    return <Card title={title}><EmptyState icon={icon} title="Belum ada data">{error ?? "YouTube belum mengirim rincian ini."}</EmptyState></Card>;
  }
  const top = rows.slice(0, 4);
  const rest = sum - top.reduce((s, r) => s + r.v, 0);
  const items = [...top.map((r) => ({ label: labels[r.key] ?? r.key, v: r.v })), ...(rest > 0 ? [{ label: "Lainnya", v: rest }] : [])];

  return (
    <Card title={title}>
      <div className={`dash-break dash-${kind}`}>
        {kind === "donut" && <Donut items={items} sum={sum} />}
        <ul>
          {items.map((it, i) => (
            <li key={it.label}>
              <i style={{ background: SLICE_COLORS[i % SLICE_COLORS.length] }} aria-hidden="true" />
              <span>{it.label}</span>
              {kind === "bars" && <meter min={0} max={sum} value={it.v} aria-label={it.label} />}
              <b>{pf.format((it.v / sum) * 100)}%</b>
            </li>
          ))}
        </ul>
      </div>
    </Card>
  );
}

function Donut({ items, sum }: { items: { label: string; v: number }[]; sum: number }) {
  const R = 42, C = 2 * Math.PI * R;
  const lens = items.map((it) => (it.v / sum) * C);
  const offsets = lens.map((_, i) => lens.slice(0, i).reduce((s, l) => s + l, 0));
  return (
    <svg viewBox="0 0 120 120" className="dash-donut-svg" role="img" aria-label={`${nf.format(sum)} views`}>
      {items.map((it, i) => (
        <circle key={it.label} cx="60" cy="60" r={R} fill="none" strokeWidth="16"
          stroke={SLICE_COLORS[i % SLICE_COLORS.length]} strokeDasharray={`${lens[i]} ${C - lens[i]}`}
          strokeDashoffset={-offsets[i]} transform="rotate(-90 60 60)" />
      ))}
      <text x="60" y="58" textAnchor="middle" className="big">{nf.format(sum)}</text>
      <text x="60" y="74" textAnchor="middle" className="small">Views</text>
    </svg>
  );
}

function TopVideos({ data }: { data: YouTubeData }) {
  const rows = data.analytics?.payload.by_video?.rows ?? [];
  const titles = new Map((data.videos?.payload ?? []).map((v) => [v.id, v]));
  const top = rows.slice(0, 5).map((r) => ({ id: String(r.video), views: num(r.views), pct: num(r.averageViewPercentage) }));
  return (
    <Card title={<>Video Terbaik <small className="muted">(28 hari)</small></>}
      action={<Link to="/performance">Lihat semua →</Link>}>
      {top.length === 0 ? (
        <EmptyState icon={PlaySquare} title="Belum ada laporan per video">
          {data.analytics?.payload.by_video_error ?? "YouTube belum mengirim laporan per video."}
        </EmptyState>
      ) : (
        <ol className="dash-videos">
          {top.map((v, i) => (
            <li key={v.id}>
              <span className="rank">{i + 1}</span>
              <span className="title">{titles.get(v.id)?.title ?? v.id}</span>
              <span className="nums">
                <b>{v.views === null ? "—" : nf.format(v.views)}</b> views
                {v.pct !== null && <small> · ditonton {pf.format(v.pct)}%</small>}
              </span>
            </li>
          ))}
        </ol>
      )}
    </Card>
  );
}

function RecentActivity() {
  const tasks = useApp((s) => s.tasks);
  const recent = [...tasks].sort((a, b) => (b.created_at ?? "").localeCompare(a.created_at ?? "")).slice(0, 5);
  const tone = { done: "ok", failed: "bad", running: "info", queued: "neutral", cancelled: "warn" } as const;
  return (
    <Card title="Aktivitas Terbaru" action={<Link to="/tasks">Semua tugas →</Link>}>
      {recent.length === 0 ? (
        <EmptyState icon={Inbox} title="Belum ada aktivitas">Tugas yang dijalankan ZOI akan muncul di sini.</EmptyState>
      ) : (
        <ul className="dash-activity">
          {recent.map((t) => (
            <li key={t.id}>
              <span>{t.name}</span>
              <Badge tone={tone[t.status as keyof typeof tone] ?? "neutral"}>{t.status}</Badge>
              <small className="muted">{formatTime(t.finished_at ?? t.started_at ?? t.created_at)}</small>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

function QuickAccess() {
  const items = [
    { to: "/ai", label: "Open ZOI AI", icon: Sparkles },
    { to: "/ideas", label: "Ide konten", icon: Lightbulb },
    { to: "/viral", label: "Video viral", icon: Eye },
    { to: "/tasks", label: "Tugas", icon: ListChecks },
  ];
  return (
    <Card title="Akses Cepat">
      <div className="dash-quick">
        {items.map(({ to, label, icon: Icon }) => (
          <Link key={to} to={to}><Icon size={20} aria-hidden="true" />{label}</Link>
        ))}
      </div>
    </Card>
  );
}
