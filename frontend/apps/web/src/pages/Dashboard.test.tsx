import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { mockFetch } from "../test/helpers";
import { DashboardPage } from "./DashboardPage";

const report = (columns: string[], rows: Record<string, string | number>[]) =>
  ({ start: "2026-10-19", end: "2026-11-15", columns, rows });

function renderWith(data: unknown) {
  mockFetch({ "/api/youtube/data": data });
  return render(<MemoryRouter><DashboardPage /></MemoryRouter>);
}

describe("DashboardPage", () => {
  it("belum terhubung → ajakan menghubungkan, tanpa angka", async () => {
    renderWith({ connected: false, source: "YouTube", channel: null, videos: null, analytics: null });
    expect(await screen.findByText("Channel YouTube belum terhubung")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Hubungkan YouTube" })).toHaveAttribute("href", "/settings/youtube");
    expect(screen.queryByText("Total Video")).not.toBeInTheDocument();
  });

  it("terhubung → angka dari YouTube, perubahan vs periode sebelumnya, rincian traffic", async () => {
    renderWith({
      connected: true, source: "YouTube Analytics API",
      channel: { fetched_at: "2026-11-16T00:00:00Z", payload: { subscriber_count: 1530, hidden_subscribers: false, video_count: 37 } },
      videos: { fetched_at: "2026-11-16T00:00:00Z", payload: [{ id: "v1", title: "Video uji pertama" }] },
      analytics: { fetched_at: "2026-11-16T00:00:00Z", payload: {
        last_28_days: report(["views", "estimatedMinutesWatched", "subscribersGained", "subscribersLost"],
          [{ views: 3080, estimatedMinutesWatched: 9240, subscribersGained: 84, subscribersLost: 28 }]),
        previous_28_days: report(["views", "estimatedMinutesWatched"], [{ views: 2800, estimatedMinutesWatched: 9240 }]),
        daily: report(["day", "views"], [{ day: "2026-11-14", views: 100 }, { day: "2026-11-15", views: 140 }]),
        traffic_sources: report(["insightTrafficSourceType", "views"], [{ insightTrafficSourceType: "YT_SEARCH", views: 75 },
          { insightTrafficSourceType: "SUGGESTED", views: 25 }]),
        by_video: report(["video", "views"], [{ video: "v1", views: 900 }]),
      } },
    });
    expect(await screen.findByText("1,5 rb")).toBeInTheDocument();
    expect(screen.getByText(/\+10%/)).toBeInTheDocument();
    expect(screen.getByText("YouTube Search")).toBeInTheDocument();
    expect(screen.getByText("75%")).toBeInTheDocument();
    expect(screen.getByText("Video uji pertama")).toBeInTheDocument();
    expect(screen.getByText("37")).toBeInTheDocument();
  });
});
