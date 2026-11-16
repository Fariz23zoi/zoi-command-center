import type { ChatMessageInfo, CloudStatus } from "@zoi/api-client";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useApp } from "../stores/appStore";
import { mockFetch } from "../test/helpers";
import { AiCloudPage } from "./AiCloudPage";
import { ChatTranscript } from "./ChatTranscript";

const limits = { source: "hitungan ZOI sendiri (bukan angka dari penyedia)", minute_used: 2, minute_limit: 30,
  minute_official: 40, day_used: 0, day_limit: null, day_official: null };

function status(overrides: Partial<CloudStatus> = {}): CloudStatus {
  return { enabled: true, provider: "nvidia", test_endpoint: false, token_storage: "keyring", storage_warning: null,
    data_sent: ["Isi chat dan permintaan agen"], never_sent: ["Rekaman suara (suara tetap diproses di komputer ini)"],
    how_to_enable: ["ZOI_AI_PROVIDER=nvidia", "ZOI_NVIDIA_MODEL=<nama model>"],
    selection: "Penyedia dan model hanya bisa diubah lewat file .env, lalu ZOI dijalankan ulang.",
    providers: [
      { name: "nvidia", label: "NVIDIA NIM", signup_url: "https://build.nvidia.com", key_prefix: "nvapi-", has_key: true,
        role: "utama", model: "meta/llama-uji", model_problem: null, free_only: false, limits },
      { name: "openrouter", label: "OpenRouter", signup_url: "https://openrouter.ai", key_prefix: "sk-or-", has_key: false,
        role: "cadangan", model: "uji/model:free", model_problem: null, free_only: true,
        limits: { ...limits, minute_limit: 15, minute_official: 20, day_used: 3, day_limit: 45, day_official: 50 } },
    ], ...overrides };
}

const show = () => render(<MemoryRouter><AiCloudPage /></MemoryRouter>);

beforeEach(() => useApp.setState({ aiRevision: 0, agentRuns: {} }));
afterEach(() => vi.unstubAllGlobals());

describe("Settings › AI Cloud", () => {
  it("tidak aktif → dinyatakan jelas, cara mengaktifkan lewat .env", async () => {
    mockFetch({ "/api/ai/cloud/status": status({ enabled: false,
      providers: status().providers.map((p) => ({ ...p, role: null, model: null, limits: null, has_key: false })) }) });
    show();
    expect(await screen.findByTestId("cloud-state")).toHaveTextContent("TIDAK aktif");
    expect(screen.getByTestId("cloud-howto")).toHaveTextContent("ZOI_AI_PROVIDER=nvidia");
    expect(screen.getByTestId("cloud-nvidia")).toHaveTextContent("tidak dipakai (.env)");
    expect(screen.queryByTestId("cloud-nvidia-test")).not.toBeInTheDocument();
  });

  it("aktif → peran, batas, data yang dikirim, penyimpanan key", async () => {
    mockFetch({ "/api/ai/cloud/status": status() });
    show();
    expect(await screen.findByTestId("cloud-state")).toHaveTextContent("AKTIF");
    expect(screen.getByTestId("cloud-nvidia")).toHaveTextContent("NVIDIA NIM — utama");
    expect(screen.getByTestId("cloud-nvidia")).toHaveTextContent("2 dari batas aman 30 (batas gratis 40)");
    expect(screen.getByTestId("cloud-openrouter")).toHaveTextContent("3 dari batas aman 45 (batas gratis 50)");
    expect(screen.getByTestId("cloud-openrouter")).toHaveTextContent("Jangan membeli kredit");
    expect(screen.getByTestId("cloud-data-sent")).toHaveTextContent("Isi chat");
    expect(screen.getByTestId("cloud-storage")).toHaveTextContent("Windows Credential Manager");
    expect(screen.getByTestId("cloud-nvidia-key")).toHaveTextContent("tersimpan (tidak ditampilkan)");
    expect(screen.queryByTestId("cloud-openrouter-test")).not.toBeInTheDocument(); // belum ada key
  });

  it("menyimpan API key: dikirim sekali, kolom dikosongkan, key tidak tampil", async () => {
    const fetchFn = mockFetch({ "/api/ai/cloud/status": status(), "/api/ai/cloud/keys/openrouter": status() });
    show();
    const input = await screen.findByLabelText(/API key \(diawali sk-or-\)/);
    expect(input).toHaveAttribute("type", "password");
    fireEvent.change(input, { target: { value: "sk-or-v1-rahasia-rahasia-rahasia" } });
    fireEvent.click(screen.getAllByRole("button", { name: "Simpan API key" })[1]);
    await waitFor(() => expect(fetchFn).toHaveBeenCalledWith("/api/ai/cloud/keys/openrouter", expect.objectContaining({
      method: "PUT", body: JSON.stringify({ key: "sk-or-v1-rahasia-rahasia-rahasia" }) })));
    expect(await screen.findByTestId("cloud-notice")).toHaveTextContent("tersimpan di komputer ini");
    expect(input).toHaveValue("");
    expect(document.body.textContent).not.toContain("rahasia-rahasia");
  });

  it("uji model menampilkan jawaban atau alasan gagal", async () => {
    mockFetch({ "/api/ai/cloud/status": status(), "/api/ai/cloud/test/nvidia": { name: "nvidia",
      model: "meta/llama-uji", ok: false, reply: "", limits,
      error: "NVIDIA NIM tidak bisa memanggil model 'meta/llama-uji' (404)." } });
    show();
    fireEvent.click(await screen.findByTestId("cloud-nvidia-test"));
    expect(await screen.findByTestId("cloud-nvidia-result")).toHaveTextContent("Gagal: NVIDIA NIM tidak bisa memanggil");
  });
});

describe("Label AI cloud di percakapan", () => {
  const message = (overrides: Partial<ChatMessageInfo>): ChatMessageInfo => ({ id: "m1", conversation_id: "c1",
    role: "assistant", content: "halo", provider: "nvidia", model: "meta/llama-uji", is_mock: false,
    status: "complete", error: null, created_at: null, ...overrides });

  it("jawaban cloud diberi label penyedia dan model", () => {
    render(<ChatTranscript messages={[message({})]} />);
    expect(screen.getByTestId("cloud-badge")).toHaveTextContent("AI cloud · NVIDIA NIM · meta/llama-uji");
    expect(screen.queryByTestId("msg-note")).not.toBeInTheDocument();
  });

  it("jawaban cadangan menampilkan alasannya", () => {
    render(<ChatTranscript messages={[message({ provider: "openrouter", model: "uji/model:free",
      note: "Dijawab OpenRouter (cadangan) karena NVIDIA NIM gagal: batas permintaan gratis tercapai (429)." })]} />);
    expect(screen.getByTestId("cloud-badge")).toHaveTextContent("AI cloud · OpenRouter · uji/model:free");
    expect(screen.getByTestId("msg-note")).toHaveTextContent("cadangan");
  });

  it("jawaban lokal dan mock tidak diberi label cloud", () => {
    render(<ChatTranscript messages={[message({ provider: "ollama" }), message({ id: "m2", provider: "mock", is_mock: true })]} />);
    expect(screen.queryByTestId("cloud-badge")).not.toBeInTheDocument();
  });
});
