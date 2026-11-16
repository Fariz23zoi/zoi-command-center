import type { ProductionPackage, ProductionStatus } from "@zoi/api-client";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useApp } from "../stores/appStore";
import { mockFetch } from "../test/helpers";
import { ProductionPage } from "./ProductionPage";

const READY: ProductionStatus = {
  available: true,
  blueprint: { configured: true, original_found: true, copy_exists: true, up_to_date: true, problem: null,
    url: "/blueprint-studio/" },
  hyperframes: { enabled: false, problems: ["ZOI_HYPERFRAMES_DIR belum diisi."], node: "v22.0.0", ffmpeg: true,
    version: null, tested_version: "0.9.55", browser: null, folder: null },
  narration: { available: true, problem: null, mock: false, engine: "piper" },
};
const PKG: ProductionPackage = { id: "abcdef123456", judul: "Kenapa langit biru", rasio: "9:16", mock: false,
  beats: 3, created: 1, files: { "paket.json": 900, "narasi.srt": 120 }, blueprint_url: "/blueprint-studio/?paket=abcdef123456",
  narration: [{ start: 0, speech: 1.2, duration: 1.5, file: "narasi/beat-01.wav" }] };

const show = () => render(<MemoryRouter><ProductionPage /></MemoryRouter>);

beforeEach(() => useApp.setState({ productionRevision: 0, tasks: [] }));
afterEach(() => vi.unstubAllGlobals());

describe("Content Production", () => {
  it("mode online → hanya penjelasan jujur 'hanya di laptop'", async () => {
    useApp.setState({ config: { online: true } as never });
    mockFetch({ "/api/production/status": { available: false, blueprint: null, hyperframes: null, narration: null },
      "/api/production/packages": { items: [] } });
    show();
    expect(await screen.findByTestId("production-laptop-only")).toHaveTextContent("Unduh paket produksi");
    expect(screen.queryByTestId("production-import")).not.toBeInTheDocument();
  });

  it("menampilkan paket, unduhan, tautan Blueprint; render mati dengan alasan HyperFrames", async () => {
    useApp.setState({ config: { online: false } as never });
    const fetchFn = mockFetch({
      "/api/production/status": READY,
      "/api/production/packages": { items: [PKG] },
      "/api/content/items": { items: [], is_mock: false, provider: "ollama" },
      "/api/production/packages/abcdef123456/narrate": { id: "t1", kind: "production_narrate", status: "QUEUED" },
    });
    show();
    expect(await screen.findByTestId("production-item")).toHaveTextContent("Kenapa langit biru");
    expect(screen.getByTestId("production-blueprint")).toHaveAttribute("href", "/blueprint-studio/?paket=abcdef123456");
    expect(screen.getByTestId("production-render")).toBeDisabled();
    expect(screen.getByTestId("hyperframes-status")).toHaveTextContent("ZOI_HYPERFRAMES_DIR");
    expect(screen.getByTestId("production-files")).toHaveTextContent("SRT narasi");
    fireEvent.click(screen.getByTestId("production-narrate"));
    await waitFor(() => expect(fetchFn).toHaveBeenCalledWith("/api/production/packages/abcdef123456/narrate",
      expect.objectContaining({ method: "POST" })));
  });

  it("file impor yang bukan JSON ditolak di browser", async () => {
    useApp.setState({ config: { online: false } as never });
    mockFetch({ "/api/production/status": READY, "/api/production/packages": { items: [] },
      "/api/content/items": { items: [], is_mock: false, provider: "ollama" } });
    show();
    const input = await screen.findByTestId("production-import");
    fireEvent.change(input, { target: { files: [new File(["bukan json"], "x.json", { type: "application/json" })] } });
    expect(await screen.findByRole("alert")).toHaveTextContent("bukan JSON");
  });
});
