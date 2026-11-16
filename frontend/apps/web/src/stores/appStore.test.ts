import type { ChatMessageInfo } from "@zoi/api-client";
import { beforeEach, describe, expect, it } from "vitest";

import { useApp } from "./appStore";

const msg = (over: Partial<ChatMessageInfo>): ChatMessageInfo => ({
  id: "a1", conversation_id: "c1", role: "assistant", content: "", provider: "ollama", model: "m", is_mock: false,
  status: "streaming", error: null, created_at: "", ...over,
});

beforeEach(() => useApp.setState({ conversationId: null, messages: [], earlyChat: {} }));

describe("event chat yang tiba sebelum respons POST", () => {
  it("chat.done lebih dulu tetap diterapkan saat pesan ditambahkan", () => {
    const failed = msg({ status: "error", error: "Ollama tidak dapat dihubungi (ConnectError)." });
    useApp.getState().handleEvent({ type: "chat.done", at: "", payload: { conversation_id: "c1", message: failed } });
    useApp.getState().setConversation("c1", []);
    useApp.getState().addMessages([msg({ id: "u1", role: "user", status: "complete" }), msg({})]);
    expect(useApp.getState().messages.find((m) => m.id === "a1")).toEqual(failed);
    expect(useApp.getState().earlyChat).toEqual({});
  });

  it("chat.delta lebih dulu digabung ke isi pesan", () => {
    useApp.getState().handleEvent({ type: "chat.delta", at: "", payload: { conversation_id: "c1", message_id: "a1", text: "Ha" } });
    useApp.getState().handleEvent({ type: "chat.delta", at: "", payload: { conversation_id: "c1", message_id: "a1", text: "lo" } });
    useApp.getState().setConversation("c1", []);
    useApp.getState().addMessages([msg({})]);
    expect(useApp.getState().messages[0].content).toBe("Halo");
  });

  it("buffer dibatasi", () => {
    for (let i = 0; i < 50; i++) {
      useApp.getState().handleEvent({ type: "chat.delta", at: "", payload: { conversation_id: "x", message_id: `m${i}`, text: "." } });
    }
    expect(Object.keys(useApp.getState().earlyChat)).toHaveLength(20);
  });

  it("chat.thinking lebih dulu ikut digabung", () => {
    useApp.getState().handleEvent({ type: "chat.thinking", at: "", payload: { conversation_id: "c1", message_id: "a1", text: "Pikir" } });
    useApp.getState().setConversation("c1", []);
    useApp.getState().addMessages([msg({})]);
    expect(useApp.getState().messages[0].thinking).toBe("Pikir");
  });
});

describe("provider.updated", () => {
  it("menaikkan revisi AI dan memperbarui model penyedia", () => {
    useApp.setState({ aiRevision: 0, provider: { name: "ollama", available: true, is_mock: false, model: "a", detail: "",
      models: [], checked_at: "" } });
    useApp.getState().handleEvent({ type: "provider.updated", at: "", payload: { active_model: "b", active_source: "ui" } });
    expect(useApp.getState().aiRevision).toBe(1);
    expect(useApp.getState().provider?.model).toBe("b");
  });
});

describe("agentRuns", () => {
  it("respons HTTP yang lebih lama tidak menimpa status terbaru dari WebSocket", () => {
    const base = { id: "r1", conversation_id: "c1", request: "x", plan: null, errors: [], results: [], summary: null,
      warnings: [], task_id: null, provider: "mock", is_mock: true, created_at: "", approvals: [] };
    useApp.setState({ agentRuns: {} });
    useApp.getState().handleEvent({ type: "agent.run.updated", at: "", payload: { run: { ...base, status: "waiting_approval",
      updated_at: "2026-11-14T10:00:02.000000+00:00" } } });
    useApp.getState().setAgentRuns([{ ...base, status: "running", updated_at: "2026-11-14T10:00:01.000000+00:00" }]);
    expect(useApp.getState().agentRuns.r1.status).toBe("waiting_approval");
  });
});
