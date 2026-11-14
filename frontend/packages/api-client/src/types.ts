export type AgentStateName =
  | "IDLE" | "LISTENING" | "THINKING" | "RESEARCHING" | "ANALYZING" | "PLANNING" | "CREATING"
  | "EXECUTING" | "WAITING_APPROVAL" | "SPEAKING" | "COMPLETED" | "FAILED";

export interface PublicConfig {
  version: string;
  mode: "development" | "local";
  banner: string | null;
  provider: "mock" | "ollama" | "none";
  is_mock: boolean;
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
  /** Proses berpikir model (bila model mendukung), terpisah dari jawaban. */
  thinking?: string | null;
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
  | { type: "provider.updated"; at: string; payload: { active_model: string | null; active_source: AiModelSource } };

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
