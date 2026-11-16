import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { mockFetch } from "../test/helpers";
import { CompetitorsTab } from "./CompetitorsTab";

const info = { retention_days: 30, region: "ID", test_endpoint: true, connected: true, source: "SERVER UJI",
  quota: { units_used: 0, daily_limit: 10000 } };
const channel = { id: "UCother", title: "Kopi Lain", custom_url: "@kopilain", published_at: null, country: "ID",
  view_count: 880000, subscriber_count: 12400, hidden_subscribers: false, video_count: 140, uploads_playlist: "UU" };

describe("CompetitorsTab", () => {
  it("cari nama → hasil → pantau; histori 1 titik tidak dikarang jadi tren", async () => {
    const fetchFn = mockFetch({
      "/api/youtube/public/competitors": () => (fetchFn.mock.calls.length > 2
        ? { ...info, max: 20, items: [{ channel_id: "UCother", note: "", added_at: "", data: { key: "competitor:UCother",
          fetched_at: "2026-11-16T00:00:00Z", expires_at: "2026-12-16T00:00:00Z", payload: { channel, videos: null } },
          history: [{ day: "2026-11-16", view_count: 880000, subscriber_count: 12400, hidden_subscribers: false, video_count: 140 }] }] }
        : { ...info, max: 20, items: [] }),
      "/api/youtube/public/channels/search": { query: "kopi", items: [channel] },
    });
    render(<CompetitorsTab mine={null} />);
    expect(await screen.findByText("Belum ada kompetitor")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Nama, tautan, atau ID channel"), { target: { value: "kopi" } });
    fireEvent.click(screen.getByRole("button", { name: /Cari/ }));
    fireEvent.click(await screen.findByRole("button", { name: /Pantau/ }));
    await waitFor(() => expect(fetchFn).toHaveBeenCalledWith("/api/youtube/public/competitors",
      expect.objectContaining({ method: "POST" })));
    expect(await screen.findByTestId("compare-table")).toHaveTextContent("Kopi Lain");
    expect(screen.getByText(/Baru 1 titik/)).toBeInTheDocument();
    expect(screen.getAllByText("Aktual · YouTube").length).toBeGreaterThan(0);
    vi.unstubAllGlobals();
  });
});
