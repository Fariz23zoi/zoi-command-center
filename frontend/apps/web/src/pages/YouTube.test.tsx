import type { YouTubeData, YouTubeStatus } from "@zoi/api-client";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useApp } from "../stores/appStore";
import { mockFetch } from "../test/helpers";
import { AnalyticsPage } from "./AnalyticsPage";
import { MonetizationPage } from "./MonetizationPage";
import { YouTubeSettingsPage } from "./YouTubeSettingsPage";

const quota = { source: "hitungan ZOI sendiri", day: "2026-11-14", units_used: 4, unit_limit: 9000, units_official: 10000,
  search_used: 0, search_limit: 90, search_official: 100, analytics_calls: 3, resets_at: "2026-11-15T08:00:00+00:00" };
const account = { channel_id: "UCx", title: "Channel Uji", custom_url: "@uji", connected_at: "2026-11-14T01:00:00+00:00",
  verified_at: "2026-11-14T01:00:00+00:00", scopes: ["https://www.googleapis.com/auth/youtube.readonly"],
  analytics_granted: true, needs_reauth: false };
const ypp = { checked_at: "2026-11-15", note: "Syarat bisa berubah.", caveats: ["Shorts Feed tidak dihitung."],
  unverified: ["Kabar perubahan Februari."],
  tiers: [{ name: "Bagi hasil iklan", source: "https://support.google.com/youtube/answer/72851",
    requirements: ["1.000 subscriber"] }] };

function status(overrides: Partial<YouTubeStatus> = {}): YouTubeStatus {
  return { client_configured: false, client_id_hint: null, connected: false, account: null, pending: false,
    last_error: null, token_storage: "keyring", storage_warning: null, test_endpoint: false, scopes: [],
    can_publish: false, quota, policy: { reverify_days: 30, summary: "Hanya data channel-mu sendiri yang disimpan." },
    ...overrides };
}

function data(overrides: Partial<YouTubeData> = {}): YouTubeData {
  return { connected: true, account, test_endpoint: false, source: "YouTube Data API v3 & YouTube Analytics API",
    purged_unverified: false, history: [], ypp, quota,
    channel: { fetched_at: "2026-11-14T02:00:00+00:00", payload: { id: "UCx", title: "Channel Uji", custom_url: "@uji",
      published_at: null, country: "ID", view_count: 45210, subscriber_count: 1530, hidden_subscribers: false,
      video_count: 37, uploads_playlist: "UUx" } },
    videos: { fetched_at: "2026-11-14T02:00:00+00:00", payload: [{ id: "v1", title: "Video satu", published_at: null,
      duration: "PT1M", privacy: "public", view_count: 1200, like_count: 80, comment_count: 12 }] },
    analytics: { fetched_at: "2026-11-14T02:00:00+00:00", payload: {
      last_28_days: { start: "2026-10-17", end: "2026-11-13", columns: ["views", "estimatedMinutesWatched"],
        rows: [{ views: 3080, estimatedMinutesWatched: 9240 }] },
      last_365_days: { start: "2025-11-14", end: "2026-11-13", columns: ["views", "estimatedMinutesWatched"],
        rows: [{ views: 40150, estimatedMinutesWatched: 120450 }] } } },
    ...overrides };
}

function show(element: React.ReactElement) {
  return render(<MemoryRouter>{element}</MemoryRouter>);
}

beforeEach(() => useApp.setState({ youtubeRevision: 0 }));
afterEach(() => vi.unstubAllGlobals());

describe("Settings › YouTube", () => {
  it("belum ada file client → tombol hubungkan mati, penjelasan jujur tampil", async () => {
    mockFetch({ "/api/youtube/status": status() });
    show(<YouTubeSettingsPage />);
    expect(await screen.findByTestId("youtube-connect")).toBeDisabled();
    expect(screen.getByText(/tidak pernah melihat atau meminta password/)).toBeInTheDocument();
    expect(screen.getByText(/tidak bisa mengunggah, mengubah, atau menghapus/)).toBeInTheDocument();
    expect(screen.getByTestId("youtube-storage")).toHaveTextContent("Windows Credential Manager");
    expect(screen.queryByTestId("youtube-test-banner")).not.toBeInTheDocument();
  });

  it("mengimpor file client lalu membuka halaman izin Google", async () => {
    const open = vi.fn();
    vi.stubGlobal("open", open);
    const fetchFn = mockFetch({
      "/api/youtube/status": status({ client_configured: true, client_id_hint: "…apps.googleusercontent.com" }),
      "/api/youtube/client": { client_id_hint: "…apps.googleusercontent.com" },
      "/api/youtube/connect": { auth_url: "https://accounts.google.com/o/oauth2/v2/auth?x=1", expires_in_s: 300 },
    });
    show(<YouTubeSettingsPage />);
    const file = new File([JSON.stringify({ installed: { client_id: "a", client_secret: "rahasia" } })], "client.json",
      { type: "application/json" });
    fireEvent.change(await screen.findByTestId("youtube-client-file"), { target: { files: [file] } });
    await waitFor(() => expect(fetchFn).toHaveBeenCalledWith("/api/youtube/client", expect.objectContaining({
      method: "PUT", headers: expect.objectContaining({ "X-ZOI-Client": "web" }) })));
    expect(await screen.findByTestId("youtube-notice")).toHaveTextContent("tersimpan di komputer ini");
    expect(document.body.textContent).not.toContain("rahasia");
    fireEvent.click(screen.getByTestId("youtube-connect"));
    await waitFor(() => expect(open).toHaveBeenCalledWith("https://accounts.google.com/o/oauth2/v2/auth?x=1", "_blank",
      "noopener,noreferrer"));
  });

  it("file bukan JSON ditolak tanpa memanggil backend", async () => {
    const fetchFn = mockFetch({ "/api/youtube/status": status() });
    show(<YouTubeSettingsPage />);
    fireEvent.change(await screen.findByTestId("youtube-client-file"),
      { target: { files: [new File(["bukan json"], "x.json")] } });
    expect(await screen.findByTestId("youtube-notice")).toHaveTextContent("bukan JSON");
    expect(fetchFn).not.toHaveBeenCalledWith("/api/youtube/client", expect.anything());
  });

  it("akun terhubung: putuskan butuh konfirmasi; penyimpanan file diberi peringatan", async () => {
    const fetchFn = mockFetch({
      "/api/youtube/status": status({ client_configured: true, connected: true, account, token_storage: "file",
        storage_warning: "Token disimpan sebagai FILE BIASA (tidak terenkripsi).", test_endpoint: true }),
      "/api/youtube/disconnect": { revoked_at_google: true, note: null },
    });
    show(<YouTubeSettingsPage />);
    expect(await screen.findByTestId("youtube-account")).toHaveTextContent("Channel Uji · @uji");
    expect(screen.getByTestId("youtube-storage")).toHaveTextContent("tidak terenkripsi");
    expect(screen.getByTestId("youtube-test-banner")).toHaveTextContent("ENDPOINT UJI");
    expect(screen.getByTestId("youtube-quota")).toHaveTextContent("4 dari batas aman 9.000");
    fireEvent.click(screen.getByTestId("youtube-disconnect"));
    expect(fetchFn).not.toHaveBeenCalledWith("/api/youtube/disconnect", expect.anything());
    fireEvent.click(screen.getByRole("button", { name: "Ya, putuskan dan hapus" }));
    await waitFor(() => expect(fetchFn).toHaveBeenCalledWith("/api/youtube/disconnect",
      expect.objectContaining({ method: "POST" })));
  });

  it("event youtube.updated memuat ulang status", async () => {
    const fetchFn = mockFetch({ "/api/youtube/status": status() });
    show(<YouTubeSettingsPage />);
    await screen.findByTestId("youtube-connect");
    const before = fetchFn.mock.calls.length;
    useApp.getState().handleEvent({ type: "youtube.updated", at: "", payload: {} });
    await waitFor(() => expect(fetchFn.mock.calls.length).toBeGreaterThan(before));
  });
});

describe("Channel Analytics & Monetization", () => {
  it("belum terhubung → tanpa angka, tanpa tabel", async () => {
    mockFetch({ "/api/youtube/data": data({ connected: false, account: null, channel: null, videos: null,
      analytics: null }) });
    show(<AnalyticsPage />);
    const box = await screen.findByTestId("youtube-not-connected");
    expect(box.textContent).not.toMatch(/\d/);
    expect(box.querySelector("table, svg, canvas, progress")).toBeNull();
  });

  it("angka tampil persis dengan sumber dan waktu ambil", async () => {
    mockFetch({ "/api/youtube/data": data() });
    show(<AnalyticsPage />);
    expect(await screen.findByTestId("channel-stats")).toHaveTextContent("1.530");
    expect(screen.getByTestId("channel-stats")).toHaveTextContent("45.210");
    expect(screen.getByTestId("report-28")).toHaveTextContent("3.080");
    expect(screen.getByTestId("video-table")).toHaveTextContent("Video satu");
    expect(screen.getAllByTestId("youtube-source")[0]).toHaveTextContent("YouTube Data API v3");
    expect(document.querySelector("progress, meter")).toBeNull();
    expect(document.body.textContent).not.toMatch(/%|skor|score/i);
  });

  it("kegagalan laporan Analytics ditampilkan, data channel tetap ada", async () => {
    mockFetch({ "/api/youtube/data": data({ analytics: { fetched_at: "2026-11-14T02:00:00+00:00",
      payload: { error: "YouTube menolak permintaan (403): Forbidden" } } }) });
    show(<AnalyticsPage />);
    expect(await screen.findByTestId("analytics-report-error")).toHaveTextContent("403");
    expect(screen.getByTestId("channel-stats")).toHaveTextContent("1.530");
  });

  it("gagal mengambil data → pesan error dari backend", async () => {
    const fetchFn = mockFetch({ "/api/youtube/data": data() });
    show(<AnalyticsPage />);
    fireEvent.click(await screen.findByTestId("youtube-refresh"));
    expect(await screen.findByTestId("analytics-error")).toHaveTextContent("tidak ada");
    expect(fetchFn).toHaveBeenCalledWith("/api/youtube/refresh", expect.objectContaining({ method: "POST" }));
  });

  it("Monetization: syarat resmi berdampingan dengan angka, tanpa persentase atau sisa", async () => {
    mockFetch({ "/api/youtube/data": data() });
    show(<MonetizationPage />);
    expect(await screen.findByTestId("ypp-channel-numbers")).toHaveTextContent("1.530");
    expect(screen.getByTestId("ypp-channel-numbers")).toHaveTextContent("120.450 menit");
    expect(screen.getByTestId("ypp-tier")).toHaveTextContent("1.000 subscriber");
    expect(screen.getByTestId("ypp-unverified")).toHaveTextContent("Belum terverifikasi");
    expect(screen.getByTestId("ypp-disclaimer")).toHaveTextContent("YouTube Studio");
    expect(document.querySelector("progress, meter, svg, canvas")).toBeNull();
    expect(document.body.textContent).not.toMatch(/\d\s?%|kurang \d|sisa \d|tercapai/i);
  });

  it("Monetization tanpa akun tetap menampilkan syarat resmi", async () => {
    mockFetch({ "/api/youtube/data": data({ connected: false, account: null, channel: null, videos: null,
      analytics: null }) });
    show(<MonetizationPage />);
    expect(await screen.findByTestId("youtube-not-connected")).toBeInTheDocument();
    expect(screen.getByTestId("ypp-tier")).toHaveTextContent("1.000 subscriber");
    expect(screen.queryByTestId("ypp-channel-numbers")).not.toBeInTheDocument();
  });
});
