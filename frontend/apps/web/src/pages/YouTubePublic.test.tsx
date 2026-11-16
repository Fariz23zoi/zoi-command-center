import type { CompetitorsData, IdeaSet, ScriptItem, TaskInfo, ViralData, YouTubeData } from "@zoi/api-client";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useApp } from "../stores/appStore";
import { mockFetch } from "../test/helpers";
import { CompetitorsPage } from "./CompetitorsPage";
import { IdeasPage } from "./IdeasPage";
import { PerformancePage } from "./PerformancePage";
import { ScriptPage, scriptToMarkdown } from "./ScriptPage";
import { TrendsPage } from "./TrendsPage";
import { ViralPage } from "./ViralPage";

const quota = { source: "hitungan ZOI sendiri", day: "2026-11-14", units_used: 6, unit_limit: 9000, units_official: 10000,
  search_used: 2, search_limit: 90, search_official: 100, analytics_calls: 0, resets_at: "2026-11-15T08:00:00+00:00" };
const info = { retention_days: 30, region: "ID", test_endpoint: false, connected: true,
  source: "YouTube Data API v3 (data publik)", quota };
const stamp = { fetched_at: "2026-11-14T02:00:00+00:00", expires_at: "2026-12-14T02:00:00+00:00" };
const video = (title: string, views: number | null) => ({ id: `id-${title}`, title, channel_title: "Kopi Harian",
  channel_id: "UCx", published_at: null, category_id: "26", duration: "PT9M", view_count: views, like_count: null,
  comment_count: null });

function viral(overrides: Partial<ViralData> = {}): ViralData {
  return { ...info, categories: { key: "categories:ID", ...stamp, payload: [{ id: "26", title: "Cara & Gaya" }] },
    trending: [{ key: "trending:ID:all", ...stamp, payload: { category_id: null, region: "ID",
      items: [video("Cara seduh kopi", 500000), video("Resep kopi susu", 499000)] } }],
    searches: [{ key: "search:abc", ...stamp, payload: { query: "kopi", items: [video("Kopi tubruk", null)] } }],
    themes: [], ...overrides };
}

const task = (overrides: Partial<TaskInfo> = {}): TaskInfo => ({ id: "t1", name: "x", kind: "content_ideas",
  status: "QUEUED", progress: 0, message: "", created_at: "2026-11-14T02:00:00+00:00", started_at: null,
  finished_at: null, result: null, error: null, ...overrides });

function show(element: React.ReactElement, path = "/") {
  return render(<MemoryRouter initialEntries={[path]}>{element}</MemoryRouter>);
}

beforeEach(() => useApp.setState({ youtubeRevision: 0, contentRevision: 0, tasks: [] }));
afterEach(() => vi.unstubAllGlobals());

describe("Competitor Intelligence", () => {
  const competitors = (overrides: Partial<CompetitorsData> = {}): CompetitorsData => ({ ...info, max: 20, items: [{
    channel_id: "UCother", note: "pesaing", added_at: "", history: [],
    data: { key: "competitor:UCother", ...stamp, payload: { videos: [video("Review grinder", 15800)], channel: {
      id: "UCother", title: "Kopi Lain", custom_url: "@kopilain", published_at: null, country: "ID", view_count: 880000,
      subscriber_count: 12400, hidden_subscribers: false, video_count: 140, uploads_playlist: "UU" } } } }],
  ...overrides });

  it("angka apa adanya dengan sumber dan tanggal hapus; tanpa skor", async () => {
    mockFetch({ "/api/youtube/public/competitors": competitors() });
    show(<CompetitorsPage />);
    const item = await screen.findByTestId("competitor-item");
    expect(item).toHaveTextContent("Kopi Lain · @kopilain");
    expect(item).toHaveTextContent("12.400");
    expect(item).toHaveTextContent("Catatanmu: pesaing");
    expect(screen.getByTestId("youtube-source")).toHaveTextContent("dihapus otomatis");
    expect(screen.getByTestId("public-policy")).toHaveTextContent("30 hari");
    expect(document.querySelector("progress, meter, svg, canvas")).toBeNull();
    expect(item.textContent).not.toMatch(/%|skor|engagement|peringkat/i);
  });

  it("data kedaluwarsa → hanya ID dan catatan; belum terhubung → tombol mati", async () => {
    const base = competitors();
    mockFetch({ "/api/youtube/public/competitors": competitors({ connected: false,
      items: [{ ...base.items[0], data: null }] }) });
    show(<CompetitorsPage />);
    expect(await screen.findByTestId("competitor-expired")).toHaveTextContent("sudah dihapus");
    expect(screen.getByTestId("competitor-item")).toHaveTextContent("UCother");
    expect(screen.getByTestId("public-not-connected")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Tambah channel" })).toBeDisabled();
  });

  it("menambah channel mengirim isian dan menampilkan error backend", async () => {
    const fetchFn = mockFetch({ "/api/youtube/public/competitors": competitors({ items: [] }) });
    show(<CompetitorsPage />);
    await screen.findByTestId("competitors-empty");
    fireEvent.change(screen.getByLabelText("Handle, ID, atau tautan channel"), { target: { value: "@kopilain" } });
    fireEvent.click(screen.getByRole("button", { name: "Tambah channel" }));
    await waitFor(() => expect(fetchFn).toHaveBeenCalledWith("/api/youtube/public/competitors", expect.objectContaining({
      method: "POST", body: JSON.stringify({ ref: "@kopilain", note: "" }) })));
  });
});

describe("Viral Video Hunter & Trend Detector", () => {
  it("daftar dalam urutan YouTube; angka kosong tidak dikarang", async () => {
    mockFetch({ "/api/youtube/public/viral": viral() });
    show(<ViralPage />);
    const lists = await screen.findAllByTestId("viral-list");
    expect(lists[0]).toHaveTextContent("Trending Indonesia · semua kategori");
    const rows = lists[0].querySelectorAll("tbody tr");
    expect(rows[0]).toHaveTextContent("Cara seduh kopi");
    expect(rows[0]).toHaveTextContent("500.000");
    expect(lists[1]).toHaveTextContent("Pencarian: “kopi”");
    expect(lists[1].querySelector("tbody tr")).toHaveTextContent("—");
    expect(screen.getByTestId("search-quota")).toHaveTextContent("2 dari batas aman 90");
    for (const list of lists) expect(list.textContent).not.toMatch(/%|skor|engagement|peringkat/i);
  });

  it("ambil Trending per kategori", async () => {
    const fetchFn = mockFetch({ "/api/youtube/public/viral": viral(), "/api/youtube/public/trending": viral() });
    show(<ViralPage />);
    fireEvent.change(await screen.findByLabelText("Kategori"), { target: { value: "26" } });
    fireEvent.click(screen.getByTestId("trending-fetch"));
    await waitFor(() => expect(fetchFn).toHaveBeenCalledWith("/api/youtube/public/trending",
      expect.objectContaining({ body: JSON.stringify({ category_id: "26" }) })));
  });

  it("Trend Detector: label interpretasi AI, contoh yang dibuang disebut, tugas diikuti", async () => {
    const themes = [{ key: "themes:trending:ID:all", ...stamp, payload: { source_key: "trending:ID:all", titles_read: 2,
      is_mock: false, provider: "ollama", model: "qwen3:4b",
      label: "Interpretasi AI atas judul — bukan statistik dan bukan data dari YouTube.",
      themes: [{ nama: "Kopi rumahan", penjelasan: "Video cara membuat kopi.", contoh_judul: ["Cara seduh kopi"],
        contoh_dibuang: 1 }] } }];
    const fetchFn = mockFetch({ "/api/youtube/public/viral": viral({ themes }),
      "/api/youtube/public/themes": task({ kind: "trend_themes" }) });
    show(<TrendsPage />, "/trends?key=search:abc");
    expect(await screen.findByTestId("themes-disclaimer")).toHaveTextContent("bukan statistik");
    expect(screen.getByTestId("theme")).toHaveTextContent("Kopi rumahan");
    expect(screen.getByTestId("theme")).toHaveTextContent("1 contoh dari AI dibuang");
    expect(screen.getByTestId("ai-stamp")).toHaveTextContent("ollama · qwen3:4b");
    expect(screen.getByLabelText("Daftar")).toHaveValue("search:abc");
    fireEvent.click(screen.getByTestId("themes-start"));
    await waitFor(() => expect(fetchFn).toHaveBeenCalledWith("/api/youtube/public/themes",
      expect.objectContaining({ body: JSON.stringify({ key: "search:abc" }) })));
    expect(await screen.findByTestId("content-task")).toHaveTextContent("beberapa menit");
    useApp.getState().handleEvent({ type: "task.updated", at: "", payload: task({ kind: "trend_themes", status: "FAILED",
      error: "RuntimeError: AI lokal gagal" }) });
    await waitFor(() => expect(screen.getByTestId("content-task")).toHaveTextContent("AI lokal gagal"));
  });

  it("tanpa daftar → diarahkan ke Viral Video Hunter", async () => {
    mockFetch({ "/api/youtube/public/viral": viral({ trending: [], searches: [] }) });
    show(<TrendsPage />);
    expect(await screen.findByTestId("trends-empty")).toHaveTextContent("Viral Video Hunter");
    expect(screen.queryByTestId("themes-start")).not.toBeInTheDocument();
  });
});

describe("Content Ideas & Script", () => {
  const ideaSet: IdeaSet = { id: "i1", kind: "ideas", title: "kopi rumahan", is_mock: true, provider: "mock", model: null,
    created_at: "2026-11-14T02:00:00+00:00",
    request: { topik: "kopi rumahan", format: "shorts", jumlah: 1, pakai_channel: true, tema_key: null },
    payload: { ide: [{ judul: "[MOCK] Contoh ide", hook: "[MOCK] hook", garis_besar: "[MOCK] garis", cta: "" }] } };
  const script: ScriptItem = { id: "s1234567890", kind: "script", title: "Seduh kopi", is_mock: false, provider: "ollama",
    model: "qwen3:4b", created_at: "2026-11-14T02:00:00+00:00",
    request: { judul: "Seduh kopi", catatan: "", format: "panjang", durasi: "" },
    payload: { judul: "Seduh kopi", hook: "Pernah gagal?", cta: "Coba di rumah.",
      bagian: [{ judul: "Alat", narasi: "Siapkan V60.", visual: "Close-up alat", durasi: "±30 detik" }] } };

  it("Mock ditandai jelas; ide bisa diteruskan ke naskah", async () => {
    const fetchFn = mockFetch({ "/api/content/items": { items: [ideaSet], is_mock: true, provider: "mock" },
      "/api/content/ideas": task() });
    show(<IdeasPage />, "/ideas?tema=trending:ID:all");
    expect(await screen.findByTestId("content-mock-banner")).toHaveTextContent("MOCK");
    expect(screen.getByTestId("ai-stamp")).toHaveTextContent("bukan hasil AI");
    expect(screen.getByRole("link", { name: "Tulis naskah dari ide ini" })).toHaveAttribute("href",
      expect.stringContaining("/script?judul=%5BMOCK%5D%20Contoh%20ide"));
    fireEvent.change(screen.getByLabelText("Topik atau arahan"), { target: { value: "kopi susu" } });
    fireEvent.click(screen.getByRole("button", { name: "Susun ide" }));
    await waitFor(() => expect(fetchFn).toHaveBeenCalledWith("/api/content/ideas", expect.objectContaining({
      body: JSON.stringify({ topik: "kopi susu", format: "panjang", jumlah: 3, pakai_channel: true,
        tema_key: "trending:ID:all" }) })));
    expect(await screen.findByTestId("content-task")).toBeInTheDocument();
  });

  it("naskah: storyboard per bagian, isian dari tautan ide, Markdown berlabel draf", async () => {
    mockFetch({ "/api/content/items": { items: [script], is_mock: false, provider: "ollama" } });
    show(<ScriptPage />, "/script?judul=Kopi%20tubruk&catatan=poin&format=shorts");
    expect(await screen.findByTestId("storyboard")).toHaveTextContent("Siapkan V60.");
    expect(screen.getByLabelText("Judul video")).toHaveValue("Kopi tubruk");
    expect(screen.getByLabelText("Format")).toHaveValue("shorts");
    expect(screen.queryByTestId("content-mock-banner")).not.toBeInTheDocument();
    const markdown = scriptToMarkdown(script);
    expect(markdown).toContain("# Seduh kopi");
    expect(markdown).toContain("Draf AI lokal (ollama · qwen3:4b) — periksa sebelum dipakai.");
    expect(markdown).toContain("## 1. Alat (±30 detik)");
    expect(scriptToMarkdown({ ...script, is_mock: true })).toContain("MOCK — teks tiruan");
  });
});

describe("Performance", () => {
  it("laporan per video dari YouTube; judul dari daftar video; tanpa tebakan waktu upload", async () => {
    const data = { connected: true, account: { needs_reauth: false }, test_endpoint: false, source: "YouTube Data API v3 & YouTube Analytics API",
      purged_unverified: false, history: [], quota, ypp: {}, channel: null,
      videos: { ...stamp, payload: [{ id: "v1", title: "Video satu" }] },
      analytics: { ...stamp, payload: { by_video: { start: "2026-10-17", end: "2026-11-13",
        columns: ["video", "views", "averageViewPercentage"],
        rows: [{ video: "v1", views: 900, averageViewPercentage: 42.5 }, { video: "vX", views: 12, averageViewPercentage: 20 }] } } },
    } as unknown as YouTubeData;
    mockFetch({ "/api/youtube/data": data });
    show(<PerformancePage />);
    const table = await screen.findByTestId("performance-table");
    expect(table).toHaveTextContent("Video satu");
    expect(table).toHaveTextContent("42,5");
    expect(table).toHaveTextContent("ID vX (judul tidak ada di daftar video terbaru)");
    expect(table).toHaveTextContent("hitungan YouTube");
    expect(screen.getByTestId("upload-time-note")).toHaveTextContent("tidak menebaknya");
  });
});
