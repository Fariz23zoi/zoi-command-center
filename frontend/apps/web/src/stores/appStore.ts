import type {
  AdapterStatus, AgentRunInfo, AgentStateName, ChatMessageInfo, Preferences, PublicConfig, ProviderStatus, TaskInfo, VoicePreferences,
  VoiceStatus, ZoiEvent,
} from "@zoi/api-client";
import { create } from "zustand";

/** Respons HTTP bisa tiba setelah event WebSocket yang lebih baru — versi lama tidak boleh menimpa yang baru. */
function mergeRuns(current: Record<string, AgentRunInfo>, incoming: AgentRunInfo[]): Record<string, AgentRunInfo> {
  const next = { ...current };
  for (const run of incoming) {
    const existing = next[run.id];
    if (!existing || Date.parse(run.updated_at) >= Date.parse(existing.updated_at)) next[run.id] = run;
  }
  return next;
}

export type VoicePhase = "recording" | "transcribing" | "speaking" | null;

interface EarlyChat {
  delta: string;
  thinking: string;
  done?: ChatMessageInfo;
}

const EARLY_LIMIT = 20;

/** Simpan event yang datang terlalu awal; dibatasi agar event pesan dari tab lain tidak menumpuk. */
function bufferEarly(
  buffer: Record<string, EarlyChat>, id: string, add: { delta?: string; thinking?: string; done?: ChatMessageInfo },
): Record<string, EarlyChat> {
  const prev = buffer[id] ?? { delta: "", thinking: "" };
  const next = {
    ...buffer,
    [id]: { delta: prev.delta + (add.delta ?? ""), thinking: prev.thinking + (add.thinking ?? ""), done: add.done ?? prev.done },
  };
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
  /** Naik setiap model aktif berubah (event provider.updated) — halaman AI Lokal memuat ulang datanya. */
  aiRevision: number;
  /** Suara (Phase 4). voicePhase menimpa tampilan status avatar selama merekam/mengenali/berbicara. */
  /** Permintaan agen (Phase 5) menurut id. memoryRevision naik setiap memori berubah. */
  agentRuns: Record<string, AgentRunInfo>;
  memoryRevision: number;
  /** Naik setiap status/data YouTube berubah (Phase 6A). */
  youtubeRevision: number;
  /** Naik setiap draf konten (ide/naskah) berubah (Phase 6B). */
  contentRevision: number;
  setAgentRuns(runs: AgentRunInfo[]): void;
  voiceStatus: VoiceStatus | null;
  voicePrefs: VoicePreferences | null;
  voicePhase: VoicePhase;
  voiceError: string | null;
  setVoiceStatus(status: VoiceStatus): void;
  setVoicePrefs(prefs: VoicePreferences): void;
  setVoicePhase(phase: VoicePhase): void;
  setVoiceError(message: string | null): void;
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
  aiRevision: 0,
  agentRuns: {},
  memoryRevision: 0,
  youtubeRevision: 0,
  contentRevision: 0,
  setAgentRuns: (runs) => set((s) => ({ agentRuns: mergeRuns(s.agentRuns, runs) })),
  voiceStatus: null,
  voicePrefs: null,
  voicePhase: null,
  voiceError: null,
  setVoiceStatus: (voiceStatus) => set({ voiceStatus, voicePrefs: voiceStatus.preferences }),
  setVoicePrefs: (voicePrefs) =>
    set((s) => ({ voicePrefs, voiceStatus: s.voiceStatus ? { ...s.voiceStatus, preferences: voicePrefs } : s.voiceStatus })),
  setVoicePhase: (voicePhase) => set({ voicePhase }),
  setVoiceError: (voiceError) => set({ voiceError }),
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
        return pending.done
          ?? { ...m, content: m.content + pending.delta, thinking: ((m.thinking ?? "") + pending.thinking) || null };
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
        case "chat.thinking":
          if (!s.messages.some((m) => m.id === event.payload.message_id)) {
            return { earlyChat: bufferEarly(s.earlyChat, event.payload.message_id, { thinking: event.payload.text }) };
          }
          if (event.payload.conversation_id !== s.conversationId) return {};
          return {
            messages: s.messages.map((m) =>
              m.id === event.payload.message_id ? { ...m, thinking: (m.thinking ?? "") + event.payload.text } : m),
          };
        case "agent.run.updated":
          return { agentRuns: mergeRuns(s.agentRuns, [event.payload.run]) };
        case "memory.updated":
          return { memoryRevision: s.memoryRevision + 1 };
        case "youtube.updated":
          return { youtubeRevision: s.youtubeRevision + 1 };
        case "content.updated":
          return { contentRevision: s.contentRevision + 1 };
        case "chat.message": {
          const { message } = event.payload;
          if (event.payload.conversation_id !== s.conversationId || s.messages.some((m) => m.id === message.id)) return {};
          const extra = message.agent_run_id && message.role === "assistant" ? { memoryRevision: s.memoryRevision + 1 } : {};
          return { messages: [...s.messages, message], ...extra };
        }
        case "voice.preferences.updated":
          return { voicePrefs: event.payload };
        case "provider.updated":
          return {
            aiRevision: s.aiRevision + 1,
            provider: s.provider ? { ...s.provider, model: event.payload.active_model } : s.provider,
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
