import type {
  AdapterStatus, AgentStateName, ChatMessageInfo, Preferences, PublicConfig, ProviderStatus, TaskInfo, ZoiEvent,
} from "@zoi/api-client";
import { create } from "zustand";

interface EarlyChat {
  delta: string;
  done?: ChatMessageInfo;
}

const EARLY_LIMIT = 20;

/** Simpan event yang datang terlalu awal; dibatasi agar event pesan dari tab lain tidak menumpuk. */
function bufferEarly(
  buffer: Record<string, EarlyChat>, id: string, add: { delta?: string; done?: ChatMessageInfo },
): Record<string, EarlyChat> {
  const prev = buffer[id] ?? { delta: "" };
  const next = { ...buffer, [id]: { delta: prev.delta + (add.delta ?? ""), done: add.done ?? prev.done } };
  const keys = Object.keys(next);
  for (const key of keys.slice(0, Math.max(0, keys.length - EARLY_LIMIT))) delete next[key];
  return next;
}

interface AppState {
  config: PublicConfig | null;
  connected: boolean;
  agent: { state: AgentStateName; reason: string };
  tasks: TaskInfo[];
  provider: ProviderStatus | null;
  adapters: AdapterStatus[];
  conversationId: string | null;
  messages: ChatMessageInfo[];
  sending: boolean;
  prefs: Preferences | null;
  bootstrapped: boolean;
  /** Event chat untuk pesan yang belum diketahui halaman ini (tiba sebelum respons POST). */
  earlyChat: Record<string, EarlyChat>;
  avatarRenderer: "2d" | "3d" | null;
  avatarNote: string | null;
  setConfig(config: PublicConfig): void;
  setPrefs(prefs: Preferences): void;
  setBootstrapped(): void;
  setAvatarRenderer(renderer: "2d" | "3d", note: string | null): void;
  setConnected(connected: boolean): void;
  setTasks(tasks: TaskInfo[]): void;
  setProvider(provider: ProviderStatus): void;
  setAdapters(adapters: AdapterStatus[]): void;
  setConversation(id: string | null, messages: ChatMessageInfo[]): void;
  addMessages(messages: ChatMessageInfo[]): void;
  setSending(sending: boolean): void;
  handleEvent(event: ZoiEvent): void;
}

export const useApp = create<AppState>((set) => ({
  config: null,
  connected: false,
  agent: { state: "IDLE", reason: "Menyambungkan…" },
  tasks: [],
  provider: null,
  adapters: [],
  conversationId: null,
  messages: [],
  sending: false,
  prefs: null,
  bootstrapped: false,
  earlyChat: {},
  avatarRenderer: null,
  avatarNote: null,
  setConfig: (config) => set({ config }),
  setPrefs: (prefs) => set({ prefs }),
  setBootstrapped: () => set({ bootstrapped: true }),
  setAvatarRenderer: (avatarRenderer, avatarNote) => set({ avatarRenderer, avatarNote }),
  setConnected: (connected) => set({ connected }),
  setTasks: (tasks) => set({ tasks }),
  setProvider: (provider) => set({ provider }),
  setAdapters: (adapters) => set({ adapters }),
  setConversation: (conversationId, messages) => set({ conversationId, messages }),
  addMessages: (incoming) =>
    set((s) => {
      // Event WebSocket bisa tiba sebelum respons POST (mis. Ollama langsung gagal) — terapkan yang tertunda di sini.
      const early = { ...s.earlyChat };
      const merged = incoming.map((m) => {
        const pending = early[m.id];
        if (!pending) return m;
        delete early[m.id];
        return pending.done ?? { ...m, content: m.content + pending.delta };
      });
      return {
        earlyChat: early,
        messages: [...s.messages.filter((m) => !merged.some((i) => i.id === m.id)), ...merged],
      };
    }),
  setSending: (sending) => set({ sending }),
  handleEvent: (event) =>
    set((s) => {
      switch (event.type) {
        case "hello":
          return { agent: event.payload.agent };
        case "agent.state":
          return { agent: event.payload };
        case "task.updated": {
          const others = s.tasks.filter((t) => t.id !== event.payload.id);
          return { tasks: [event.payload, ...others].sort((a, b) => (b.created_at ?? "").localeCompare(a.created_at ?? "")) };
        }
        case "chat.delta":
          if (!s.messages.some((m) => m.id === event.payload.message_id)) {
            return { earlyChat: bufferEarly(s.earlyChat, event.payload.message_id, { delta: event.payload.text }) };
          }
          if (event.payload.conversation_id !== s.conversationId) return {};
          return {
            messages: s.messages.map((m) =>
              m.id === event.payload.message_id ? { ...m, content: m.content + event.payload.text } : m),
          };
        case "chat.done":
          if (!s.messages.some((m) => m.id === event.payload.message.id)) {
            return { earlyChat: bufferEarly(s.earlyChat, event.payload.message.id, { done: event.payload.message }) };
          }
          if (event.payload.conversation_id !== s.conversationId) return {};
          return { messages: s.messages.map((m) => (m.id === event.payload.message.id ? event.payload.message : m)) };
        case "preferences.updated":
          return { prefs: event.payload };
        default:
          return {};
      }
    }),
}));
