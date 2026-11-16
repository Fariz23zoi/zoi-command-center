import type { AutomationOverview } from "@zoi/api-client";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useApp } from "../stores/appStore";
import { mockFetch } from "../test/helpers";
import { AutomationPage } from "./AutomationPage";

const KINDS = { laporan_channel: "Laporan channel", pantau_kompetitor: "Pantau kompetitor", pantau_tren: "Pantau Trending",
  pengingat_produksi: "Pengingat produksi" };
const OVERVIEW: AutomationOverview = {
  kinds: KINDS, runs: [], wake_enabled: false, online: true, timezone: "Asia/Jakarta (WIB)",
  items: [{ id: "a1", kind: "pengingat_produksi", kind_label: "Pengingat produksi", name: "Upload Jumat", enabled: true,
    schedule: { frequency: "weekly", hour: 9, minute: 0, weekday: 4 }, schedule_text: "Setiap Jumat 09.00 WIB",
    params: { text: "Render video" }, next_due_at: "2026-11-20T02:00:00+00:00", last_run_at: null,
    last_run: { id: "r1", automation_id: "a1", task_id: "t1", trigger: "susulan", late: true, status: "COMPLETED",
      summary: "Render video", started_at: "2026-11-16T02:00:00+00:00", finished_at: "2026-11-16T02:00:01+00:00" } }],
};
const NOTES = { unread: 1, items: [{ id: "n1", kind: "pengingat_produksi", title: "Pengingat: Upload Jumat",
  body: "Render video", link: "/production", created_at: "2026-11-16T02:00:01+00:00", read: false }] };

beforeEach(() => useApp.setState({ automationRevision: 0, unreadNotifications: 0 }));
afterEach(() => vi.unstubAllGlobals());

describe("Automation", () => {
  it("menampilkan otomatisasi, label susulan, peringatan bangun, dan notifikasi", async () => {
    mockFetch({ "/api/automation": OVERVIEW, "/api/notifications": NOTES });
    render(<MemoryRouter><AutomationPage /></MemoryRouter>);
    expect(await screen.findByTestId("automation-item")).toHaveTextContent("Setiap Jumat 09.00 WIB");
    expect(screen.getByTestId("automation-last")).toHaveTextContent("susulan (terlambat)");
    expect(screen.getByTestId("automation-wake")).toHaveTextContent("ZOI bangun");
    expect(await screen.findByText("Pengingat: Upload Jumat")).toBeInTheDocument();
    await waitFor(() => expect(useApp.getState().unreadNotifications).toBe(1));
  });

  it("membuat pengingat mingguan dengan teks", async () => {
    const fetchFn = mockFetch({ "/api/automation": { ...OVERVIEW, items: [] }, "/api/notifications": { items: [], unread: 0 } });
    render(<MemoryRouter><AutomationPage /></MemoryRouter>);
    fireEvent.change(await screen.findByTestId("automation-kind"), { target: { value: "pengingat_produksi" } });
    fireEvent.change(screen.getByTestId("automation-text"), { target: { value: "Cek naskah" } });
    fireEvent.click(screen.getByTestId("automation-create"));
    await waitFor(() => expect(fetchFn).toHaveBeenCalledWith("/api/automation", expect.objectContaining({
      method: "POST", body: expect.stringContaining("\"text\":\"Cek naskah\"") })));
  });
});
