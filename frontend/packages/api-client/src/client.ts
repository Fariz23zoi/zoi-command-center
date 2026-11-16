import type {
  AdapterStatus, ChatMessageInfo, ConversationInfo, Preferences, ProviderStatus, PublicConfig,
  SendChatResponse, SystemStatus, TaskInfo, ZoiEvent,
} from "./types";

/** Header wajib untuk permintaan yang mengubah data (perlindungan CSRF di backend). */
export const CLIENT_HEADER = { "X-ZOI-Client": "web" } as const;

export class ApiError extends Error {
  constructor(public status: number, message: string, public code?: string) {
    super(message);
  }
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = method === "GET" ? {} : { ...CLIENT_HEADER };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  const response = await fetch(path, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) });
  const text = await response.text();
  const data = text ? JSON.parse(text) : null;
  if (!response.ok) {
    const message = data?.error?.message ?? (Array.isArray(data?.detail) ? "Isian tidak valid." : `HTTP ${response.status}`);
    throw new ApiError(response.status, message, data?.error?.code);
  }
  return data as T;
}

export const api = {
  config: () => request<PublicConfig>("GET", "/api/config"),
  systemStatus: () => request<SystemStatus>("GET", "/api/system/status"),
  providerStatus: () => request<ProviderStatus>("GET", "/api/provider/status"),
  adapters: () => request<{ adapters: AdapterStatus[] }>("GET", "/api/adapters"),
  tasks: () => request<{ tasks: TaskInfo[] }>("GET", "/api/tasks"),
  task: (id: string) => request<TaskInfo>("GET", `/api/tasks/${encodeURIComponent(id)}`),
  runSystemCheck: () => request<TaskInfo>("POST", "/api/tasks/system-check"),
  cancelTask: (id: string) => request<TaskInfo>("POST", `/api/tasks/${encodeURIComponent(id)}/cancel`),
  sendChat: (message: string, conversationId?: string | null) =>
    request<SendChatResponse>("POST", "/api/chat", { message, conversation_id: conversationId ?? null }),
  conversations: () => request<{ conversations: ConversationInfo[] }>("GET", "/api/conversations"),
  messages: (conversationId: string) =>
    request<{ messages: ChatMessageInfo[] }>("GET", `/api/conversations/${encodeURIComponent(conversationId)}/messages`),
  preferences: () => request<Preferences>("GET", "/api/preferences"),
  savePreferences: (prefs: Preferences) => request<Preferences>("PUT", "/api/preferences", prefs),
};

export interface EventConnection { close(): void }

/** Sambungan WebSocket dengan reconnect otomatis (jeda bertambah sampai 10 detik). */
export function connectEvents(
  onEvent: (event: ZoiEvent) => void,
  onStatus: (connected: boolean) => void = () => {},
  url = `${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws`,
): EventConnection {
  let socket: WebSocket | null = null;
  let closed = false;
  let delay = 500;
  let timer: ReturnType<typeof setTimeout> | undefined;

  const open = () => {
    socket = new WebSocket(url);
    socket.onopen = () => { delay = 500; onStatus(true); };
    socket.onmessage = (message) => {
      try { onEvent(JSON.parse(message.data) as ZoiEvent); } catch { /* abaikan pesan rusak */ }
    };
    socket.onclose = () => {
      onStatus(false);
      if (!closed) { timer = setTimeout(open, delay); delay = Math.min(delay * 2, 10_000); }
    };
  };
  open();
  return { close: () => { closed = true; clearTimeout(timer); socket?.close(); } };
}
