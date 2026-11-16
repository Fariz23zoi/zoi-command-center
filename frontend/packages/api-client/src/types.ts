export type AgentStateName =
  | "IDLE" | "LISTENING" | "THINKING" | "RESEARCHING" | "ANALYZING" | "PLANNING" | "CREATING"
  | "EXECUTING" | "WAITING_APPROVAL" | "SPEAKING" | "COMPLETED" | "FAILED";

export interface AuthStatus { enabled: boolean; ready: boolean; logged_in: boolean }

export interface PublicConfig {
  version: string;
  mode: "development" | "local" | "online";
  banner: string | null;
  provider: "mock" | "ollama" | "nvidia" | "openrouter" | "none";
  is_mock: boolean;
  /** AI cloud gratis aktif (data dikirim ke penyedia di `cloud_providers`). */
  is_cloud?: boolean;
  /** Mode online (Render): login aktif; fitur laptop dimatikan. */
  online?: boolean;
  cloud_providers?: string[];
  ollama_url: string | null;
  ollama_model: string | null;
  avatar_mode: "auto" | "2d" | "3d";
  host: string;
  port: number;
  base_url: string;
  data_dir: string;
  warnings: string[];
  migration_backup: string | null;
  config_source: string;
}

export interface ToolInfo { name: string; found: boolean; version: string | null; path: string | null; error?: string }

export interface SystemStatus {
  source: string;
  checked_at: string;
  python: { version: string; implementation: string; supported: boolean };
  os: { system: string; release: string; machine: string };
  resources: {
    cpu: { physical_cores: number | null; logical_cores: number | null; model: string | null };
    memory: { total_bytes: number; available_bytes: number };
    disk: { path: string; total_bytes: number; free_bytes: number };
    gpu: { detected: boolean; note?: string; devices?: string[] };
  };
  tools: Record<string, ToolInfo>;
}

export interface ProviderStatus {
  name: string; available: boolean; is_mock: boolean; model: string | null; detail: string;
  models: string[]; checked_at: string;
}

export interface AdapterStatus {
  name: string; configured: boolean; found: boolean; checked_at: string;
  details: Record<string, unknown>; problems: string[]; integration_phase: number;
}

export type TaskStatus = "QUEUED" | "RUNNING" | "COMPLETED" | "FAILED" | "CANCELLED";

export interface TaskInfo {
  id: string; name: string; kind: string; status: TaskStatus; progress: number; message: string;
  created_at: string | null; started_at: string | null; finished_at: string | null;
  result: Record<string, unknown> | null; error: string | null;
  events?: { at: string; status: TaskStatus; progress: number; message: string }[];
}

export interface ChatMessageInfo {
  id: string; conversation_id: string; role: "user" | "assistant" | "system"; content: string;
  provider: string | null; model: string | null; is_mock: boolean;
  status: "streaming" | "complete" | "error" | "stopped"; error: string | null; created_at: string | null;
  /** Keterangan tentang jawaban, mis. dijawab penyedia cadangan dan alasannya. */
  note?: string | null;
  /** Proses berpikir model (bila model mendukung), terpisah dari jawaban. */
  thinking?: string | null;
  /** Pesan yang terkait permintaan agen (Phase 5). */
  agent_run_id?: string | null;
}

export interface ConversationInfo { id: string; title: string; is_mock: boolean; updated_at: string }

export interface SendChatResponse {
  conversation_id: string; user_message: ChatMessageInfo; assistant_message: ChatMessageInfo;
}

export interface Preferences {
  ui_language: "id" | "en";
  avatar_mode_preference: "auto" | "2d" | "3d";
  avatar_character: "female" | "male";
}

export type ZoiEvent =
  | { type: "hello"; payload: { mode: string; agent: { state: AgentStateName; reason: string }; is_mock: boolean } }
  | { type: "agent.state"; at: string; payload: { state: AgentStateName; reason: string } }
  | { type: "task.updated"; at: string; payload: TaskInfo }
  | { type: "chat.delta"; at: string; payload: { conversation_id: string; message_id: string; text: string } }
  | { type: "chat.done"; at: string; payload: { conversation_id: string; message: ChatMessageInfo } }
  | { type: "chat.thinking"; at: string; payload: { conversation_id: string; message_id: string; text: string } }
  | { type: "preferences.updated"; at: string; payload: Preferences }
  | { type: "provider.updated"; at: string; payload: { active_model: string | null; active_source: AiModelSource } }
  | { type: "voice.preferences.updated"; at: string; payload: VoicePreferences }
  | { type: "chat.message"; at: string; payload: { conversation_id: string; message: ChatMessageInfo } }
  | { type: "agent.run.updated"; at: string; payload: { run: AgentRunInfo } }
  | { type: "memory.updated"; at: string; payload: { id: string | null } }
  | { type: "youtube.updated"; at: string; payload: Record<string, never> }
  | { type: "content.updated"; at: string; payload: { id: string; kind: string | null } };

// ── AI lokal (Phase 3) ─────────────────────────────────────────────────────
export type AiModelSource = "ui" | "env" | "none";

export interface InstalledModel {
  name: string; size_bytes: number | null; family: string | null; parameter_size: string | null;
  quantization: string | null; modified_at: string | null; is_cloud: boolean;
}

export interface RunningModel {
  name: string; size_bytes: number | null; vram_bytes: number | null; context_tokens: number | null;
  expires_at: string | null;
}

export interface ModelDetails {
  name: string; capabilities: string[]; context_tokens: number | null; architecture: string | null;
  parameter_size: string | null; quantization: string | null; license_line: string | null;
}

export interface CatalogModel { tag: string; family: string; license: string; download: string; context: string; fit: string }

export interface AiCatalog {
  checked_at: string; source: string; models: CatalogModel[]; not_default: { family: string; reason: string }[];
}

export interface AiStatus {
  provider: string; is_mock: boolean; reachable: boolean; ready: boolean; detail: string;
  url: string | null; location: "lokal" | "jaringan" | null; version: string | null;
  active_model: string | null; active_source: AiModelSource; env_model: string | null;
  installed: InstalledModel[]; running: RunningModel[]; catalog: AiCatalog; can_download: false;
}

export interface EvalSummary {
  json: { passed: number; total: number }; tool: { passed: number; total: number }; chat_errors: number;
  median_first_token_s: number | null; median_tokens_per_s: number | null; errors: number;
}

export interface EvalPromptResult {
  id: string; category: "chat" | "json" | "tool"; prompt: string; passed: boolean | null; response: string;
  error: string | null; first_token_s: number | null; tokens_per_s: number | null; output_tokens: number | null;
  thinking_chars: number; attempts: number | null; detail: string;
}

export interface EvaluationInfo {
  id: string; model: string; machine: string; ollama_version: string | null; prompts_version: number;
  started_at: string; finished_at: string; summary: EvalSummary; ratings: { up: number; down: number };
  results?: EvalPromptResult[]; rating_by_prompt?: Record<string, "up" | "down">;
}

// ── Suara (Phase 4) ────────────────────────────────────────────────────────
export interface VoicePreferences {
  language: "id" | "en" | "auto";
  speak_replies: boolean;
  auto_send: boolean;
  tts_engine: "auto" | "piper" | "browser";
  browser_voice: string | null;
  speech_rate: number;
  piper_license_accepted: boolean;
}

export interface VoiceEngineStatus { name: string; is_mock: boolean; available: boolean; detail: string; model: string | null }

export interface VoiceCatalog {
  checked_at: string;
  whisper: { package: string; note: string; models: { name: string; repo: string; download: string; fit: string }[]; install: string[] };
  piper: { package: string; voice: string; download: string; license_note: string; install: string[] };
  browser: { note: string; lip_sync: false };
}

export interface VoiceStatus {
  stt: VoiceEngineStatus; tts: VoiceEngineStatus; preferences: VoicePreferences;
  reply_engine: "piper" | "browser"; catalog: VoiceCatalog; can_download: false; stores_recordings: false;
}

export interface TranscriptInfo {
  text: string; language: string | null; audio_seconds: number | null; elapsed_seconds: number; is_mock: boolean;
}

// ── Agen & memori (Phase 5) ────────────────────────────────────────────────
export type MemoryKind = "fakta" | "preferensi" | "proyek";

export interface MemoryInfo {
  id: string; kind: MemoryKind; content: string; source: "pengguna" | "agen"; is_mock: boolean;
  created_at: string; updated_at: string;
}

export type ToolPermission = "read" | "write_local" | "external";

export interface AgentToolInfo {
  name: string; description: string; permission: ToolPermission; args_schema: Record<string, unknown>;
  mode: "ask" | "auto";
}

export interface AgentStep { tool: string; argumen: Record<string, unknown>; alasan: string; permission: ToolPermission | null }

export interface AgentStepResult {
  index: number; tool: string; args: Record<string, unknown>; status: "ok" | "error" | "rejected";
  output: unknown; error: string | null;
}

export interface ApprovalInfo {
  id: string; run_id: string; step_index: number; tool: string; args: Record<string, unknown>;
  status: "pending" | "approved" | "rejected" | "expired" | "auto"; is_mock: boolean;
  created_at: string; decided_at: string | null;
}

export type AgentRunStatus = "planning" | "invalid" | "planned" | "rejected" | "running" | "waiting_approval"
  | "completed" | "failed" | "stopped" | "cancelled";

export interface AgentRunInfo {
  id: string; conversation_id: string | null; request: string; status: AgentRunStatus;
  plan: { tujuan: string; langkah: AgentStep[] } | null; errors: string[]; results: AgentStepResult[];
  summary: string | null; warnings: string[]; task_id: string | null; provider: string; is_mock: boolean;
  created_at: string; updated_at: string; approvals: ApprovalInfo[];
}

export interface AgentStatusInfo { available: boolean; detail: string; tools: AgentToolInfo[]; can_publish: false }

// ── YouTube (Phase 6A) — hanya data channel milik pengguna, angka persis dari YouTube ──────────────────
export interface YouTubeQuotaInfo {
  source: string; day: string; units_used: number; unit_limit: number; units_official: number;
  search_used: number; search_limit: number; search_official: number; analytics_calls: number; resets_at: string;
}

export interface YouTubeAccount {
  channel_id: string; title: string; custom_url: string | null; connected_at: string; verified_at: string;
  scopes: string[]; analytics_granted: boolean; needs_reauth: boolean;
}

export interface YouTubeStatus {
  client_configured: boolean; client_id_hint: string | null; connected: boolean; account: YouTubeAccount | null;
  pending: boolean; last_error: string | null; token_storage: "keyring" | "file" | "database"; storage_warning: string | null;
  test_endpoint: boolean; scopes: string[]; can_publish: false; quota: YouTubeQuotaInfo;
  web_flow?: boolean; callback_url?: string | null; client_kind?: "installed" | "web";
  policy: { reverify_days: number; summary: string };
}

export interface YouTubeChannel {
  id: string; title: string; custom_url: string | null; published_at: string | null; country: string | null;
  view_count: number | null; subscriber_count: number | null; hidden_subscribers: boolean; video_count: number | null;
  uploads_playlist: string | null;
}

export interface YouTubeVideo {
  id: string; title: string; published_at: string | null; duration: string | null; privacy: string | null;
  view_count: number | null; like_count: number | null; comment_count: number | null;
}

export interface YouTubeReport {
  start: string; end: string; columns: string[]; rows: Record<string, string | number>[];
}

export interface YouTubeAnalytics {
  error?: string; last_28_days?: YouTubeReport; daily?: YouTubeReport; last_365_days?: YouTubeReport;
  by_video?: YouTubeReport; by_video_error?: string;
}

export interface YouTubeCached<T> { payload: T; fetched_at: string }

export interface YouTubeSnapshot {
  day: string; fetched_at: string; view_count: number | null; subscriber_count: number | null;
  hidden_subscribers: boolean; video_count: number | null;
}

export interface YppRequirements {
  checked_at: string; note: string; caveats: string[]; unverified: string[];
  tiers: { name: string; source: string; requirements: string[] }[];
}

export interface YouTubeData {
  connected: boolean; account: YouTubeAccount | null; test_endpoint: boolean; source: string;
  purged_unverified: boolean; channel: YouTubeCached<YouTubeChannel> | null;
  videos: YouTubeCached<YouTubeVideo[]> | null; analytics: YouTubeCached<YouTubeAnalytics> | null;
  history: YouTubeSnapshot[]; ypp: YppRequirements; quota: YouTubeQuotaInfo;
}

// ── Data publik YouTube (Phase 6B) — disimpan ≤30 hari, urutan dari YouTube, tanpa skor buatan ZOI ─────
export interface PublicEntry<T> { key: string; payload: T; fetched_at: string; expires_at: string }

export interface PublicVideo {
  id: string | null; title: string; channel_title: string; channel_id: string | null; published_at: string | null;
  category_id: string | null; duration: string | null; view_count: number | null; like_count: number | null;
  comment_count: number | null;
}

export interface PublicInfo {
  retention_days: number; region: string; test_endpoint: boolean; connected: boolean; source: string;
  quota: YouTubeQuotaInfo;
}

export interface CompetitorItem {
  channel_id: string; note: string; added_at: string;
  data: PublicEntry<{ channel: YouTubeChannel; videos: PublicVideo[] | null }> | null;
}

export interface CompetitorsData extends PublicInfo { max: number; items: CompetitorItem[] }

export interface ThemeInfo { nama: string; penjelasan: string; contoh_judul: string[]; contoh_dibuang: number }

export interface ThemesPayload {
  source_key: string; titles_read: number; themes: ThemeInfo[]; is_mock: boolean; provider: string;
  model: string | null; label: string;
}

export interface ViralData extends PublicInfo {
  categories: PublicEntry<{ id: string; title: string }[]> | null;
  trending: PublicEntry<{ category_id: string | null; region: string; items: PublicVideo[] }>[];
  searches: PublicEntry<{ query: string; items: PublicVideo[] }>[];
  themes: PublicEntry<ThemesPayload>[];
}

// ── Draf konten AI lokal (Phase 6B) ────────────────────────────────────────
export type ContentFormat = "panjang" | "shorts";
export interface IdeaInfo { judul: string; hook: string; garis_besar: string; cta: string }
export interface ScriptPart { judul: string; narasi: string; visual: string; durasi: string }
export interface ScriptInfo { judul: string; hook: string; bagian: ScriptPart[]; cta: string }

export interface ContentItemInfo<P, R> {
  id: string; kind: "ideas" | "script"; title: string; is_mock: boolean; provider: string; model: string | null;
  created_at: string; request: R; payload: P;
}
export interface IdeaRequest { topik: string; format: ContentFormat; jumlah: number; pakai_channel: boolean; tema_key: string | null }
export interface ScriptRequest { judul: string; catatan: string; format: ContentFormat; durasi: string }
export type IdeaSet = ContentItemInfo<{ ide: IdeaInfo[] }, IdeaRequest>;
export type ScriptItem = ContentItemInfo<ScriptInfo, ScriptRequest>;

// ── AI cloud gratis (NVIDIA NIM + cadangan OpenRouter) ─────────────────────
export interface CloudLimits {
  source: string; minute_used: number; minute_limit: number; minute_official: number;
  day_used: number; day_limit: number | null; day_official: number | null;
}

export interface CloudProviderInfo {
  name: "nvidia" | "openrouter"; label: string; signup_url: string; key_prefix: string; has_key: boolean;
  role: "utama" | "cadangan" | null; model: string | null; model_problem: string | null; free_only: boolean;
  limits: CloudLimits | null;
}

export interface CloudStatus {
  enabled: boolean; provider: string; test_endpoint: boolean; token_storage: "keyring" | "file" | "database";
  storage_warning: string | null; providers: CloudProviderInfo[]; data_sent: string[]; never_sent: string[];
  how_to_enable: string[]; selection: string;
}

export interface CloudModels { name: string; models: string[]; current: string | null; current_listed: boolean; note: string }
export interface CloudTestResult {
  name: string; model: string | null; ok: boolean; reply: string; error: string | null; limits: CloudLimits;
}
