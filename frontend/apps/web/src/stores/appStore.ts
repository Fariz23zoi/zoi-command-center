import type {
  AdapterStatus, AgentStateName, ChatMessageInfo, PublicConfig, ProviderStatus, TaskInfo, ZoiEvent,
} from "@zoi/api-client";
import { create } from "zustand";

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
  setConfig(config: PublicConfig): void;
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
  setConfig: (config) => set({ config }),
  setConnected: (connected) => set({ connected }),
  setTasks: (tasks) => set({ tasks }),
  setProvider: (provider) => set({ provider }),
  setAdapters: (adapters) => set({ adapters }),
  setConversation: (conversationId, messages) => set({ conversationId, messages }),
  addMessages: (incoming) =>
    set((s) => ({ messages: [...s.messages.filter((m) => !incoming.some((i) => i.id === m.id)), ...incoming] })),
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
          if (event.payload.conversation_id !== s.conversationId) return {};
          return {
            messages: s.messages.map((m) =>
              m.id === event.payload.message_id ? { ...m, content: m.content + event.payload.text } : m),
          };
        case "chat.done":
          if (event.payload.conversation_id !== s.conversationId) return {};
          return { messages: s.messages.map((m) => (m.id === event.payload.message.id ? event.payload.message : m)) };
        default:
          return {};
      }
    }),
}));
