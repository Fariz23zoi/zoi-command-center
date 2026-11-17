import type {
  AdapterStatus, AuthStatus, AutomationInfo, AutomationOverview, AutomationSchedule, NotificationInfo,
  ProductionPackage, ProductionStatus, AgentRunInfo, AgentStatusInfo, AgentToolInfo, AiModelSource, ApprovalInfo, MemoryInfo, MemoryKind, AiStatus, ChatMessageInfo, ConversationInfo, EvaluationInfo, ModelDetails, Preferences,
  ProviderStatus, PublicConfig, RunningModel, SendChatResponse, SystemStatus, TaskInfo, TranscriptInfo,
  VoicePreferences, VoiceStatus, YouTubeCached, YouTubeChannel, YouTubeData, YouTubeReport, YouTubeStatus, ZoiEvent,
  ClipperLaunch, CloudModels, CloudStatus, UpdateStatus, CloudTestResult, CompetitorsData, IdeaRequest, IdeaSet, ScriptItem, ScriptRequest, ViralData,
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
    if (response.status === 401 && data?.error?.code === "belum_login" && typeof window !== "undefined") {
      window.dispatchEvent(new Event("zoi-unauthorized")); // sesi habis → AuthGate menampilkan halaman masuk
    }
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
  deleteConversation: (id: string) => request<void>("DELETE", `/api/conversations/${encodeURIComponent(id)}`),
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
    retention: (videoId: string) =>
      request<YouTubeCached<YouTubeReport & { video_id: string }>>("POST",
        `/api/youtube/videos/${encodeURIComponent(videoId)}/retention`),
  },
  auth: {
    status: () => request<AuthStatus>("GET", "/api/auth/status"),
    setup: (token: string, password: string) => request<{ ok: boolean }>("POST", "/api/auth/setup", { token, password }),
    login: (password: string) => request<{ ok: boolean }>("POST", "/api/auth/login", { password }),
    logout: () => request<{ ok: boolean }>("POST", "/api/auth/logout", {}),
    logoutAll: () => request<{ ok: boolean }>("POST", "/api/auth/logout-all", {}),
  },
  automation: {
    overview: () => request<AutomationOverview>("GET", "/api/automation"),
    create: (body: { kind: string; name?: string; schedule: AutomationSchedule; params?: Record<string, unknown> }) =>
      request<AutomationInfo>("POST", "/api/automation", body),
    update: (id: string, body: Partial<{ enabled: boolean; name: string; schedule: AutomationSchedule;
      params: Record<string, unknown> }>) => request<AutomationInfo>("PATCH", `/api/automation/${id}`, body),
    remove: (id: string) => request<void>("DELETE", `/api/automation/${id}`),
    run: (id: string) => request<{ run_id: string; task: TaskInfo }>("POST", `/api/automation/${id}/run`),
  },
  notifications: {
    list: () => request<{ items: NotificationInfo[]; unread: number }>("GET", "/api/notifications"),
    readAll: () => request<{ items: NotificationInfo[]; unread: number }>("POST", "/api/notifications/read", {}),
    read: (id: string) =>
      request<{ items: NotificationInfo[]; unread: number }>("POST", `/api/notifications/${id}/read`, {}),
  },
  production: {
    status: () => request<ProductionStatus>("GET", "/api/production/status"),
    packages: () => request<{ items: ProductionPackage[] }>("GET", "/api/production/packages"),
    importPackage: (pkg: unknown) => request<ProductionPackage>("POST", "/api/production/packages", { package: pkg }),
    fromScript: (scriptId: string) =>
      request<ProductionPackage>("POST", "/api/production/packages", { script_id: scriptId }),
    remove: (id: string) => request<void>("DELETE", `/api/production/packages/${id}`),
    narrate: (id: string) => request<TaskInfo>("POST", `/api/production/packages/${id}/narrate`),
    render: (id: string) => request<TaskInfo>("POST", `/api/production/packages/${id}/render`),
    fileUrl: (id: string, name: string) => `/api/production/packages/${id}/files/${name}`,
    buildBlueprint: () => request<NonNullable<ProductionStatus["blueprint"]>>("POST", "/api/production/blueprint/build"),
  },
  backup: {
    downloadUrl: "/api/backup/download",
    /** Pulihkan arsip cadangan ZOI (.zip). Rahasia tidak pernah ada di arsip. */
    async restore(file: Blob): Promise<{ ok: boolean; note: string }> {
      const response = await fetch("/api/backup/restore", {
        method: "POST", headers: { ...CLIENT_HEADER, "Content-Type": "application/zip" }, body: file,
      });
      if (!response.ok) return raiseFor(response);
      return response.json() as Promise<{ ok: boolean; note: string }>;
    },
  },
  aiCloud: {
    status: () => request<CloudStatus>("GET", "/api/ai/cloud/status"),
    /** API key hanya dikirim ke backend ZOI di komputer ini dan tidak pernah dikembalikan. */
    putKey: (name: string, key: string) => request<CloudStatus>("PUT", `/api/ai/cloud/keys/${name}`, { key }),
    deleteKey: (name: string) => request<CloudStatus>("DELETE", `/api/ai/cloud/keys/${name}`),
    models: (name: string) => request<CloudModels>("GET", `/api/ai/cloud/models/${name}`),
    test: (name: string) => request<CloudTestResult>("POST", `/api/ai/cloud/test/${name}`),
  },
  update: {
    status: () => request<UpdateStatus>("GET", "/api/update/status"),
    check: () => request<UpdateStatus>("POST", "/api/update/check", {}),
    install: () => request<UpdateStatus>("POST", "/api/update/install", {}),
  },
  clipper: {
    status: () => request<ClipperLaunch>("GET", "/api/clipper/status"),
    start: () => request<ClipperLaunch>("POST", "/api/clipper/start", {}),
    stop: () => request<ClipperLaunch>("POST", "/api/clipper/stop", {}),
  },
  youtubePublic: {
    competitors: () => request<CompetitorsData>("GET", "/api/youtube/public/competitors"),
    addCompetitor: (ref: string, note: string) =>
      request<CompetitorsData>("POST", "/api/youtube/public/competitors", { ref, note }),
    refreshCompetitor: (id: string, force = false) =>
      request<CompetitorsData>("POST",
        `/api/youtube/public/competitors/${encodeURIComponent(id)}/refresh${force ? "?force=true" : ""}`),
    /** Cari channel berdasarkan nama — 100 unit kuota per pencarian. */
    searchChannels: (query: string) =>
      request<{ query: string; items: YouTubeChannel[] }>("POST", "/api/youtube/public/channels/search", { query }),
    removeCompetitor: (id: string) =>
      request<CompetitorsData>("DELETE", `/api/youtube/public/competitors/${encodeURIComponent(id)}`),
    viral: () => request<ViralData>("GET", "/api/youtube/public/viral"),
    trending: (categoryId: string | null) =>
      request<ViralData>("POST", "/api/youtube/public/trending", { category_id: categoryId }),
    search: (query: string) => request<ViralData>("POST", "/api/youtube/public/search", { query }),
    removeList: (key: string) => request<ViralData>("POST", "/api/youtube/public/lists/remove", { key }),
    /** Memulai tugas: AI lokal merangkum tema dari judul satu daftar tersimpan. */
    themes: (key: string) => request<TaskInfo>("POST", "/api/youtube/public/themes", { key }),
  },
  content: {
    packageUrl: (id: string) => `/api/content/items/${encodeURIComponent(id)}/package`,
    ideas: () => request<{ items: IdeaSet[]; is_mock: boolean; provider: string }>("GET", "/api/content/items?kind=ideas"),
    scripts: () => request<{ items: ScriptItem[]; is_mock: boolean; provider: string }>("GET", "/api/content/items?kind=script"),
    makeIdeas: (body: IdeaRequest) => request<TaskInfo>("POST", "/api/content/ideas", body),
    makeScript: (body: ScriptRequest) => request<TaskInfo>("POST", "/api/content/scripts", body),
    remove: (id: string) => request<null>("DELETE", `/api/content/items/${encodeURIComponent(id)}`),
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

  let beat: ReturnType<typeof setInterval> | undefined;
  const open = () => {
    socket = new WebSocket(url);
    socket.onopen = () => {
      delay = 500; onStatus(true);
      // Detak tiap 4 menit: lalu lintas masuk agar hosting gratis (Render) tidak menidurkan ZOI selagi dipakai.
      clearInterval(beat);
      beat = setInterval(() => { if (socket?.readyState === WebSocket.OPEN) socket.send("detak"); }, 240_000);
    };
    socket.onmessage = (message) => {
      try { onEvent(JSON.parse(message.data) as ZoiEvent); } catch { /* abaikan pesan rusak */ }
    };
    socket.onclose = () => {
      onStatus(false); clearInterval(beat);
      if (!closed) { timer = setTimeout(open, delay); delay = Math.min(delay * 2, 10_000); }
    };
  };
  open();
  return { close: () => { closed = true; clearTimeout(timer); clearInterval(beat); socket?.close(); } };
}
