import type { VoiceStatus } from "@zoi/api-client";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "../App";
import { useApp } from "../stores/appStore";
import { config, FakeWebSocket, mockFetch } from "../test/helpers";

const provider = { name: "mock", available: true, is_mock: true, model: "mock-scripted", detail: "", models: [], checked_at: "" };

const prefs = { language: "id", speak_replies: false, auto_send: false, tts_engine: "auto", browser_voice: null,
  speech_rate: 1, piper_license_accepted: false } as const;

function voiceStatus(overrides: Partial<VoiceStatus> = {}): VoiceStatus {
  return {
    stt: { name: "mock", is_mock: true, available: true, detail: "Mode development: transkrip adalah MOCK.", model: "mock" },
    tts: { name: "mock", is_mock: true, available: true, detail: "Mode development: suara adalah nada MOCK.", model: "mock" },
    preferences: { ...prefs }, reply_engine: "piper", can_download: false, stores_recordings: false,
    catalog: {
      checked_at: "2026-11-14",
      whisper: { package: "faster-whisper 1.2.1 (MIT)", note: "catatan", install: ["pip install"],
        models: [{ name: "tiny", repo: "Systran/faster-whisper-tiny", download: "±75 MB", fit: "Ringan." }] },
      piper: { package: "piper-tts", voice: "id_ID-news_tts-medium", download: "±63 MB", license_note: "Dataset malayalam tidak jelas.",
        install: ["pip install piper-tts"] },
      browser: { note: "Tambahkan paket bahasa Indonesia di Windows.", lip_sync: false },
    },
    ...overrides,
  };
}

function renderApp(path: string, status: VoiceStatus, extra: Record<string, unknown> = {}) {
  const fetchFn = mockFetch({
    "/api/config": config({ avatar_mode: "2d" }),
    "/api/tasks": { tasks: [] }, "/api/provider/status": provider,
    "/api/adapters": { adapters: [] }, "/api/conversations": { conversations: [] },
    "/api/preferences": { ui_language: "id", avatar_mode_preference: "2d", avatar_character: "female" },
    "/api/voice/status": status,
    ...extra,
  });
  render(<MemoryRouter initialEntries={[path]}><App /></MemoryRouter>);
  return fetchFn;
}

class FakeRecorder {
  static isTypeSupported = (t: string) => t.startsWith("audio/webm");
  state = "inactive";
  mimeType = "audio/webm;codecs=opus";
  ondataavailable: ((e: { data: Blob }) => void) | null = null;
  onstop: (() => void) | null = null;
  start() { this.state = "recording"; }
  stop() {
    this.state = "inactive";
    this.ondataavailable?.({ data: new Blob(["rekaman"], { type: this.mimeType }) });
    this.onstop?.();
  }
}

beforeEach(() => {
  FakeWebSocket.instances = [];
  vi.stubGlobal("WebSocket", FakeWebSocket);
  vi.stubGlobal("MediaRecorder", FakeRecorder);
  const track = { stop: vi.fn() };
  Object.defineProperty(navigator, "mediaDevices", { configurable: true,
    value: { getUserMedia: vi.fn(async () => ({ getTracks: () => [track] })) } });
  useApp.setState({ config: null, prefs: null, bootstrapped: false, messages: [], conversationId: null, voiceStatus: null,
    voicePrefs: null, voicePhase: null, voiceError: null });
});
afterEach(() => vi.unstubAllGlobals());

describe("input suara", () => {
  it("rekam → transkrip masuk kotak pesan (tidak langsung dikirim), avatar mendengarkan", async () => {
    const fetchFn = renderApp("/ai", voiceStatus(), {
      "/api/voice/transcribe": { text: "[MOCK] transkrip suara tiruan", language: "id", audio_seconds: 1,
        elapsed_seconds: 0.1, is_mock: true },
    });
    const mic = await screen.findByTestId("mic-button");
    await waitFor(() => expect(mic).toBeEnabled());
    fireEvent.click(mic);
    expect(await screen.findByTestId("mic-finish")).toBeInTheDocument();
    expect(screen.getByTestId("agent-reason")).toHaveTextContent("Mendengarkan");
    fireEvent.click(screen.getByTestId("mic-finish"));
    await waitFor(() => expect(screen.getByLabelText("Pesan untuk ZOI")).toHaveValue("[MOCK] transkrip suara tiruan"));
    const calls = fetchFn.mock.calls as unknown as [string, RequestInit][];
    const call = calls.find(([url]) => url.startsWith("/api/voice/transcribe"));
    expect(call?.[0]).toBe("/api/voice/transcribe?language=id");
    expect(call?.[1].headers).toMatchObject({ "X-ZOI-Client": "web", "Content-Type": "audio/webm;codecs=opus" });
    expect(calls.some(([url]) => url === "/api/chat")).toBe(false);
  });

  it("pengenal suara tidak tersedia → tombol mati dengan alasan", async () => {
    renderApp("/ai", voiceStatus({ stt: { name: "whisper", is_mock: false, available: false,
      detail: "ZOI_WHISPER_MODEL_DIR belum diisi.", model: null } }));
    const mic = await screen.findByTestId("mic-button");
    await waitFor(() => expect(mic).toHaveAttribute("title", "ZOI_WHISPER_MODEL_DIR belum diisi."));
    expect(mic).toBeDisabled();
  });

  it("izin mikrofon ditolak → pesan jelas", async () => {
    Object.defineProperty(navigator, "mediaDevices", { configurable: true,
      value: { getUserMedia: vi.fn(async () => { throw new DOMException("no", "NotAllowedError"); }) } });
    renderApp("/ai", voiceStatus());
    const mic = await screen.findByTestId("mic-button");
    await waitFor(() => expect(mic).toBeEnabled());
    fireEvent.click(mic);
    expect(await screen.findByRole("alert")).toHaveTextContent("Izin mikrofon ditolak");
  });
});

describe("Settings › Suara", () => {
  it("development: status jujur, tanpa catatan lisensi Piper, perintah pemasangan tampil", async () => {
    renderApp("/settings/voice", voiceStatus());
    expect(await screen.findByTestId("voice-status")).toHaveTextContent("transkrip adalah MOCK");
    expect(screen.queryByTestId("piper-license")).not.toBeInTheDocument();
    expect(screen.getByText(/dibuang — tidak disimpan/)).toBeInTheDocument();
    expect(screen.getByTestId("whisper-models")).toHaveTextContent("±75 MB");
  });

  it("Piper asli: catatan lisensi wajib dibaca; menyimpan penerimaan", async () => {
    const piper = voiceStatus({
      tts: { name: "piper", is_mock: false, available: true, detail: "Server Piper siap.", model: "id_ID-news_tts-medium" },
      reply_engine: "browser",
    });
    const fetchFn = renderApp("/settings/voice", piper, {
      "/api/voice/preferences": { ...prefs, piper_license_accepted: true },
    });
    const box = await screen.findByTestId("piper-license");
    expect(box).toHaveTextContent("malayalam");
    expect(screen.getByTestId("reply-engine")).toHaveTextContent("Suara lokal");
    fireEvent.click(screen.getByLabelText(/pemakaian pribadi/));
    fireEvent.click(screen.getByRole("button", { name: "Simpan preferensi" }));
    await waitFor(() => expect(fetchFn).toHaveBeenCalledWith("/api/voice/preferences",
      expect.objectContaining({ method: "PUT", body: expect.stringContaining('"piper_license_accepted":true') })));
  });
});
