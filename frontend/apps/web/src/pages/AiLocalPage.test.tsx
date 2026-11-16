import type { AiStatus } from "@zoi/api-client";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useApp } from "../stores/appStore";
import { mockFetch } from "../test/helpers";
import { AiLocalPage } from "./AiLocalPage";

const catalog = {
  checked_at: "2026-11-14", source: "Halaman resmi ollama.com/library.",
  models: [{ tag: "qwen3:1.7b", family: "Qwen3", license: "Apache-2.0", download: "1,4 GB", context: "40K", fit: "Ringan." }],
  not_default: [{ family: "Llama", reason: "Lisensi kustom." }],
};

function status(overrides: Partial<AiStatus> = {}): AiStatus {
  return {
    provider: "ollama", is_mock: false, reachable: true, ready: true, detail: "Ollama 0.0.0-tiruan siap.",
    url: "http://127.0.0.1:11434", location: "lokal", version: "0.0.0-tiruan", active_model: "qwen3:4b",
    active_source: "env", env_model: "qwen3:4b", catalog, can_download: false,
    installed: [
      { name: "qwen3:4b", size_bytes: 2_684_354_560, family: "qwen3", parameter_size: "4.0B", quantization: "Q4_K_M",
        modified_at: null, is_cloud: false },
      { name: "uji-awan:cloud", size_bytes: null, family: null, parameter_size: null, quantization: null,
        modified_at: null, is_cloud: true },
    ],
    running: [{ name: "qwen3:4b", size_bytes: 3_221_225_472, vram_bytes: 0, context_tokens: 4096, expires_at: null }],
    ...overrides,
  };
}

function renderPage(routes: Record<string, unknown>) {
  const fetchFn = mockFetch({ "/api/ai/evaluations": { evaluations: [], prompts: [] }, ...routes });
  render(<MemoryRouter><AiLocalPage /></MemoryRouter>);
  return fetchFn;
}

beforeEach(() => useApp.setState({ tasks: [], aiRevision: 0 }));
afterEach(() => vi.unstubAllGlobals());

describe("AI Lokal", () => {
  it("mode development: jujur, tanpa daftar model dan tanpa uji model", async () => {
    renderPage({ "/api/ai/status": status({ provider: "mock", is_mock: true, reachable: false, ready: false,
      detail: "Mode development memakai Mock Provider — tidak ada model sungguhan di sini.", installed: [], running: [],
      url: null, version: null, active_model: "mock-scripted", active_source: "none" }) });
    expect(await screen.findByTestId("ai-status-detail")).toHaveTextContent("Mock Provider");
    expect(screen.queryByTestId("installed-models")).not.toBeInTheDocument();
    expect(screen.queryByText("Uji kecocokan model")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Uji koneksi" })).not.toBeInTheDocument();
    expect(screen.getByTestId("catalog")).toHaveTextContent("ollama pull qwen3:1.7b");
  });

  it("menampilkan angka dari Ollama dan tidak menawarkan model cloud", async () => {
    renderPage({ "/api/ai/status": status() });
    const models = await screen.findAllByTestId("installed-model");
    expect(models[0]).toHaveTextContent("2.5 GB · 4.0B · Q4_K_M · qwen3");
    expect(within(models[0]).getByTestId("active-badge")).toBeInTheDocument();
    expect(models[1]).toHaveTextContent("cloud — tidak diizinkan");
    expect(within(models[1]).queryByRole("button")).not.toBeInTheDocument();
    expect(screen.getByTestId("running-models")).toHaveTextContent("4.096 token");
    expect(screen.getByText(/ZOI tidak pernah mengunduh atau menghapus/)).toBeInTheDocument();
    expect(screen.queryByText(/Unduh model|Download/i)).not.toBeInTheDocument();
  });

  it("Ollama tidak terhubung → panduan instalasi, tanpa angka", async () => {
    renderPage({ "/api/ai/status": status({ reachable: false, ready: false, version: null, installed: [], running: [],
      detail: "Ollama tidak dapat dihubungi di http://127.0.0.1:11434 (ConnectError)." }) });
    expect(await screen.findByTestId("install-guide")).toHaveTextContent("OLLAMA_MODELS");
    expect(screen.queryByTestId("installed-models")).not.toBeInTheDocument();
  });

  it("memilih model aktif memanggil API dengan header klien", async () => {
    const fetchFn = renderPage({ "/api/ai/status": status(), "/api/ai/active-model": { active_model: "qwen3:4b",
      active_source: "ui" }, "/api/provider/status": { name: "ollama" } });
    const models = await screen.findAllByTestId("installed-model");
    expect(within(models[0]).getByRole("button", { name: "Model aktif" })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Uji koneksi" }));
    await waitFor(() => expect(fetchFn).toHaveBeenCalledWith("/api/ai/test", expect.objectContaining({
      method: "POST", headers: expect.objectContaining({ "X-ZOI-Client": "web" }) })));
  });
});
