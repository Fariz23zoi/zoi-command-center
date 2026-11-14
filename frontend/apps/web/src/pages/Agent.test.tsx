import type { AgentRunInfo } from "@zoi/api-client";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useApp } from "../stores/appStore";
import { mockFetch } from "../test/helpers";
import { AgentRunCard } from "./AgentRunCard";
import { MemoryPage } from "./MemoryPage";

function run(overrides: Partial<AgentRunInfo> = {}): AgentRunInfo {
  return {
    id: "r1", conversation_id: "c1", request: "catat memori", status: "planned", is_mock: true, provider: "mock",
    plan: { tujuan: "[MOCK] Rencana tiruan", langkah: [
      { tool: "cari_memori", argumen: { kata_kunci: "zoi" }, alasan: "cek", permission: "read" },
      { tool: "simpan_memori", argumen: { isi: "catatan" }, alasan: "simpan", permission: "write_local" },
    ] },
    errors: [], results: [], summary: null, warnings: [], task_id: null, created_at: "", updated_at: "", approvals: [],
    ...overrides,
  };
}

beforeEach(() => useApp.setState({ agentRuns: {}, memoryRevision: 0 }));
afterEach(() => vi.unstubAllGlobals());

describe("AgentRunCard", () => {
  it("rencana tampil dengan tingkat izin; dijalankan hanya lewat tombol", async () => {
    const fetchFn = mockFetch({ "/api/agent/runs/r1/approve": run({ status: "running", task_id: "t1" }) });
    render(<AgentRunCard run={run()} />);
    expect(screen.getAllByTestId("agent-step")).toHaveLength(2);
    expect(screen.getByText("ubah data — perlu izin")).toBeInTheDocument();
    expect(fetchFn).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Jalankan rencana" }));
    await waitFor(() => expect(useApp.getState().agentRuns.r1.status).toBe("running"));
    expect(fetchFn).toHaveBeenCalledWith("/api/agent/runs/r1/approve", expect.objectContaining({
      method: "POST", headers: expect.objectContaining({ "X-ZOI-Client": "web" }) }));
  });

  it("kartu izin muncul untuk langkah ubah-data dan bisa ditolak", async () => {
    const waiting = run({ status: "waiting_approval", results: [{ index: 0, tool: "cari_memori", args: {}, status: "ok",
      output: { jumlah: 0 }, error: null }],
      approvals: [{ id: "a1", run_id: "r1", step_index: 1, tool: "simpan_memori", args: { isi: "catatan" },
        status: "pending", is_mock: true, created_at: "", decided_at: null }] });
    const fetchFn = mockFetch({ "/api/agent/approvals/a1": run({ status: "stopped" }) });
    render(<AgentRunCard run={waiting} />);
    expect(screen.getByTestId("agent-approval")).toHaveTextContent("simpan_memori");
    fireEvent.click(screen.getByRole("button", { name: "Tolak" }));
    await waitFor(() => expect(fetchFn).toHaveBeenCalledWith("/api/agent/approvals/a1",
      expect.objectContaining({ body: JSON.stringify({ decision: "reject" }) })));
  });

  it("rencana tidak valid menampilkan alasan dan tidak bisa dijalankan", () => {
    render(<AgentRunCard run={run({ status: "invalid", errors: ["Langkah 1: tool 'unggah_video' tidak ada"] })} />);
    expect(screen.getByRole("alert")).toHaveTextContent("unggah_video");
    expect(screen.queryByRole("button", { name: "Jalankan rencana" })).not.toBeInTheDocument();
  });
});

describe("MemoryPage", () => {
  const memory = { id: "m1", kind: "fakta", content: "Channel tentang kopi", source: "agen", is_mock: false,
    created_at: "2026-11-14T00:00:00Z", updated_at: "2026-11-14T00:00:00Z" };

  it("menampilkan sumber memori, log izin, dan menolak hapus semua tanpa konfirmasi bernama", async () => {
    mockFetch({
      "/api/memories": { items: [memory], total: 1 },
      "/api/agent/status": { available: true, detail: "Agen siap.", can_publish: false, tools: [
        { name: "simpan_memori", description: "Menyimpan", permission: "write_local", args_schema: {}, mode: "ask" }] },
      "/api/agent/approvals": { approvals: [{ id: "a1", run_id: "r1", step_index: 1, tool: "simpan_memori", args: {},
        status: "approved", is_mock: false, created_at: "2026-11-14T00:00:00Z", decided_at: "2026-11-14T00:00:00Z" }] },
    });
    render(<MemoryRouter><MemoryPage /></MemoryRouter>);
    expect(await screen.findByTestId("memory-item")).toHaveTextContent("disimpan agen");
    expect(await screen.findByTestId("approval-log")).toHaveTextContent("disetujui");
    expect(screen.getByLabelText("Izinkan otomatis tanpa bertanya")).not.toBeChecked();
    const deleteAll = screen.getByRole("button", { name: "Hapus semua memori" });
    expect(deleteAll).toBeDisabled();
    fireEvent.change(screen.getByLabelText(/Hapus semua memori — ketik/), { target: { value: "HAPUS SEMUA" } });
    expect(deleteAll).toBeEnabled();
  });
});
