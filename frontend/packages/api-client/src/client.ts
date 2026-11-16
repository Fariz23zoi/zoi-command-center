import type {
  AdapterStatus, AgentRunInfo, AgentStatusInfo, AgentToolInfo, AiModelSource, ApprovalInfo, MemoryInfo, MemoryKind, AiStatus, ChatMessageInfo, ConversationInfo, EvaluationInfo, ModelDetails, Preferences,
  ProviderStatus, PublicConfig, RunningModel, SendChatResponse, SystemStatus, TaskInfo, TranscriptInfo,
  VoicePreferences, VoiceStatus, YouTubeData, YouTubeStatus, ZoiEvent,
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

async function raiseFor(response: Response): Promise<never> {
  const text = await response.text();
  let message = `HTTP ${response.status}`;
  let code: string | undefined;
  try {
    const data = JSON.parse(text);
    message = data?.error?.message ?? (Array.isArray(data?.detail) ? "Isian tidak valid." : message);
    code = data?.error?.code;
  } catch { /* bukan JSON */ }
  throw new ApiError(response.status, message, code);
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
  stopChat: (messageId: string) =>
    request<{ stopped: boolean }>("POST", `/api/chat/${encodeURIComponent(messageId)}/stop`),
  preferences: () => request<Preferences>("GET", "/api/preferences"),
  savePreferences: (prefs: Preferences) => request<Preferences>("PUT", "/api/preferences", prefs),
  memories: {
    list: (query?: string) =>
      request<{ items: MemoryInfo[]; total: number }>("GET", `/api/memories${query ? `?q=${encodeURIComponent(query)}` : ""}`),
    create: (content: string, kind: MemoryKind) => request<MemoryInfo>("POST", "/api/memories", { content, kind }),
    update: (id: string, content: string, kind: MemoryKind) =>
      request<MemoryInfo>("PUT", `/api/memories/${encodeURIComponent(id)}`, { content, kind }),
    remove: (id: string) => request<null>("DELETE", `/api/memories/${encodeURIComponent(id)}`),
    removeAll: (confirm: string) =>
      request<{ deleted: number }>("DELETE", `/api/memories?confirm=${encodeURIComponent(confirm)}`),
  },
  agent: {
    status: () => request<AgentStatusInfo>("GET", "/api/agent/status"),
    plan: (text: string, conversationId?: string | null) =>
      request<{ run: AgentRunInfo; user_message: ChatMessageInfo }>("POST", "/api/agent/plan",
        { request: text, conversation_id: conversationId ?? null }),
    runs: (conversationId?: string | null) =>
      request<{ runs: AgentRunInfo[] }>("GET", `/api/agent/runs${conversationId ? `?conversation_id=${encodeURIComponent(conversationId)}` : ""}`),
    approve: (id: string) => request<AgentRunInfo>("POST", `/api/agent/runs/${encodeURIComponent(id)}/approve`),
    reject: (id: string) => request<AgentRunInfo>("POST", `/api/agent/runs/${encodeURIComponent(id)}/reject`),
    cancel: (id: string) => request<AgentRunInfo>("POST", `/api/agent/runs/${encodeURIComponent(id)}/cancel`),
    decide: (approvalId: string, decision: "approve" | "reject") =>
      request<AgentRunInfo>("POST", `/api/agent/approvals/${encodeURIComponent(approvalId)}`, { decision }),
    approvals: () => request<{ approvals: ApprovalInfo[] }>("GET", "/api/agent/approvals"),
    setPermission: (name: string, mode: "ask" | "auto") =>
      request<{ tools: AgentToolInfo[] }>("PUT", `/api/agent/tools/${encodeURIComponent(name)}/permission`, { mode }),
  },
  youtube: {
    status: () => request<YouTubeStatus>("GET", "/api/youtube/status"),
    /** Isi file client OAuth dikirim ke backend ZOI di komputer ini saja, dan tidak pernah dikembalikan ke browser. */
    putClient: (config: unknown) => request<{ client_id_hint: string }>("PUT", "/api/youtube/client", { config }),
    deleteClient: () => request<null>("DELETE", "/api/youtube/client"),
    connect: () => request<{ auth_url: string; expires_in_s: number }>("POST", "/api/youtube/connect"),
    cancelConnect: () => request<null>("POST", "/api/youtube/connect/cancel"),
    disconnect: () => request<{ revoked_at_google: boolean; note: string | null }>("POST", "/api/youtube/disconnect"),
    refresh: (what: "all" | "channel" | "videos" | "analytics" = "all") =>
      request<YouTubeData>("POST", "/api/youtube/refresh", { what }),
    data: () => request<YouTubeData>("GET", "/api/youtube/data"),
  },
  voice: {
    status: () => request<VoiceStatus>("GET", "/api/voice/status"),
    preferences: () => request<VoicePreferences>("GET", "/api/voice/preferences"),
    savePreferences: (prefs: VoicePreferences) => request<VoicePreferences>("PUT", "/api/voice/preferences", prefs),
    /** Mengirim rekaman ke backend ZOI di komputer ini saja. Rekaman tidak disimpan. */
    async transcribe(audio: Blob, language?: "id" | "en" | "auto"): Promise<TranscriptInfo> {
      const query = language ? `?language=${language}` : "";
      const response = await fetch(`/api/voice/transcribe${query}`, {
        method: "POST", headers: { ...CLIENT_HEADER, "Content-Type": audio.type || "application/octet-stream" }, body: audio,
      });
      if (!response.ok) return raiseFor(response);
      return response.json() as Promise<TranscriptInfo>;
    },
    async speak(text: string, signal?: AbortSignal): Promise<Blob> {
      const response = await fetch("/api/voice/speak", {
        method: "POST", headers: { ...CLIENT_HEADER, "Content-Type": "application/json" }, body: JSON.stringify({ text }), signal,
      });
      if (!response.ok) return raiseFor(response);
      return response.blob();
    },
  },
  ai: {
    status: () => request<AiStatus>("GET", "/api/ai/status"),
    test: () => request<{ ok: boolean; detail: string; latency_ms: number | null }>("POST", "/api/ai/test"),
    model: (name: string) => request<ModelDetails>("GET", `/api/ai/model?name=${encodeURIComponent(name)}`),
    setActive: (model: string) =>
      request<{ active_model: string | null; active_source: AiModelSource }>("PUT", "/api/ai/active-model", { model }),
    resetActive: () =>
      request<{ active_model: string | null; active_source: AiModelSource }>("DELETE", "/api/ai/active-model"),
    unload: (model: string) => request<{ running: RunningModel[] }>("POST", "/api/ai/unload", { model }),
    evaluations: () =>
      request<{ evaluations: EvaluationInfo[]; prompts: { id: string; category: string; prompt: string }[] }>(
        "GET", "/api/ai/evaluations"),
    evaluation: (id: string) => request<EvaluationInfo>("GET", `/api/ai/evaluations/${encodeURIComponent(id)}`),
    startEvaluation: (model: string) => request<TaskInfo>("POST", "/api/ai/evaluations", { model }),
    rate: (id: string, promptId: string, rating: "up" | "down" | null) =>
      request<EvaluationInfo>("PUT", `/api/ai/evaluations/${encodeURIComponent(id)}/rating`,
        { prompt_id: promptId, rating }),
  },
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
