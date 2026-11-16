import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";
import { MENU } from "./menu";
import { useApp } from "./stores/appStore";
import { config, FakeWebSocket, mockFetch } from "./test/helpers";

const provider = { name: "mock", available: true, is_mock: true, model: "mock-scripted", detail: "Mock", models: [],
  checked_at: "2026-11-14T00:00:00Z" };

function renderApp(path = "/ai", cfg = config()) {
  mockFetch({
    "/api/config": cfg, "/api/tasks": { tasks: [] }, "/api/provider/status": provider,
    "/api/adapters": { adapters: [] }, "/api/conversations": { conversations: [] },
    "/api/preferences": { ui_language: "id", avatar_mode_preference: "auto", avatar_character: "female" },
  });
  return render(<MemoryRouter initialEntries={[path]}><App /></MemoryRouter>);
}

beforeEach(() => {
  FakeWebSocket.instances = [];
  vi.stubGlobal("WebSocket", FakeWebSocket);
  useApp.setState({ config: null, prefs: null, bootstrapped: false, avatarRenderer: null, avatarNote: null, tasks: [], messages: [],
    conversationId: null, agent: { state: "IDLE", reason: "" } });
});
afterEach(() => vi.unstubAllGlobals());

describe("Command Center", () => {
  it("menampilkan 18 menu", async () => {
    renderApp();
    const nav = screen.getByRole("navigation", { name: "Menu utama" });
    expect(within(nav).getAllByRole("link")).toHaveLength(18);
    expect(MENU).toHaveLength(18);
  });

  it("banner development tampil di mode development", async () => {
    renderApp();
    expect(await screen.findByTestId("dev-banner")).toHaveTextContent("MOCK");
  });

  it("banner tidak tampil di mode local", async () => {
    renderApp("/ai", config({ mode: "local", banner: null, provider: "ollama", is_mock: false }));
    await waitFor(() => expect(useApp.getState().config?.mode).toBe("local"));
    expect(screen.queryByTestId("dev-banner")).not.toBeInTheDocument();
  });

  it.each(MENU.filter((m) => !m.ready && !["/clipper", "/blueprint"].includes(m.path)))(
    "halaman $label tidak berisi angka/data contoh",
    async (item) => {
      renderApp(item.path);
      const page = await screen.findByTestId("not-yet-available");
      const text = (page.textContent ?? "").replace(/Phase \d+/g, "");
      expect(text).not.toMatch(/\d/);
      expect(page.querySelector("svg, canvas, table, progress")).toBeNull();
    },
  );

  it("avatar mengikuti event status dari backend", async () => {
    renderApp();
    await waitFor(() => expect(document.querySelector("[data-state]")).not.toBeNull());
    const ws = FakeWebSocket.instances[0];
    act(() => ws.emit({ type: "agent.state", at: "", payload: { state: "THINKING", reason: "Menyusun jawaban" } }));
    expect(document.querySelector("[data-state]")?.getAttribute("data-state")).toBe("THINKING");
    expect(screen.getByTestId("agent-reason")).toHaveTextContent("Menyusun jawaban");
  });

  it("jawaban mock diberi lencana MOCK dan teks mengalir dari event", async () => {
    renderApp();
    const user = { id: "u1", conversation_id: "c1", role: "user", content: "halo", provider: null, model: null,
      is_mock: true, status: "complete", error: null, created_at: null };
    const assistant = { ...user, id: "a1", role: "assistant", content: "", provider: "mock", status: "streaming" };
    mockFetch({ "/api/chat": { conversation_id: "c1", user_message: user, assistant_message: assistant } });
    fireEvent.change(screen.getByLabelText("Pesan untuk ZOI"), { target: { value: "halo" } });
    fireEvent.click(screen.getByRole("button", { name: "Kirim" }));
    expect((await screen.findAllByTestId("mock-badge")).length).toBeGreaterThan(0);
    const ws = FakeWebSocket.instances[0];
    act(() => ws.emit({ type: "chat.delta", at: "", payload: { conversation_id: "c1", message_id: "a1", text: "[MOCK] Halo" } }));
    expect(screen.getAllByText("[MOCK] Halo").length).toBeGreaterThan(0);
  });

  it("tombol suara dinonaktifkan dengan alasan yang jujur", () => {
    renderApp();
    expect(screen.getByRole("button", { name: /Input suara/ })).toBeDisabled();
  });

  it("Settings: server memaksa 2D → pilihan avatar dikunci dan dijelaskan", async () => {
    renderApp("/ai/settings", config({ avatar_mode: "2d" }));
    expect(await screen.findByLabelText("Avatar")).toBeDisabled();
    expect(screen.getByText(/Server memaksa 2D/)).toBeInTheDocument();
    await waitFor(() => expect(screen.getByTestId("avatar-renderer")).toHaveTextContent("2d"));
    expect(screen.getByLabelText(/Uji lip-sync/)).toBeDisabled();
  });

  it("Settings: tanpa WebGL 2 avatar memakai 2D dengan catatan jujur", async () => {
    renderApp("/ai/settings");
    await waitFor(() => expect(screen.getByTestId("avatar-renderer")).toHaveTextContent("2d"));
    expect(screen.getAllByText(/tidak mendukung WebGL 2/).length).toBeGreaterThan(0);
    expect(screen.getByLabelText("Karakter 3D")).toHaveValue("female");
  });

  it("tombol Berhenti muncul selama ZOI menulis dan memanggil API stop", async () => {
    renderApp();
    const fetchFn = vi.mocked(globalThis.fetch);
    useApp.setState({ conversationId: "c1", messages: [{ id: "a1", conversation_id: "c1", role: "assistant", content: "",
      provider: "mock", model: "m", is_mock: true, status: "streaming", error: null, created_at: null }] });
    fireEvent.click(await screen.findByTestId("stop-button"));
    await waitFor(() => expect(fetchFn).toHaveBeenCalledWith("/api/chat/a1/stop", expect.objectContaining({ method: "POST" })));
  });

  it("/agen meminta rencana, bukan mengirim chat biasa", async () => {
    renderApp();
    const fetchFn = vi.mocked(globalThis.fetch);
    const input = await screen.findByLabelText("Pesan untuk ZOI");
    fireEvent.change(input, { target: { value: "/agen cek status sistem" } });
    fireEvent.click(screen.getByRole("button", { name: "Kirim" }));
    await waitFor(() => expect(fetchFn).toHaveBeenCalledWith("/api/agent/plan", expect.objectContaining({
      method: "POST", body: JSON.stringify({ request: "cek status sistem", conversation_id: null }) })));
    expect(fetchFn.mock.calls.some(([url]) => url === "/api/chat")).toBe(false);
  });
});
