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
  status: "streaming" | "complete" | "error"; error: string | null; created_at: string | null;
}

export interface ConversationInfo { id: string; title: string; is_mock: boolean; updated_at: string }

export interface SendChatResponse {
  conversation_id: string; user_message: ChatMessageInfo; assistant_message: ChatMessageInfo;
}

export interface Preferences { ui_language: "id" | "en"; avatar_mode_preference: "auto" | "2d" | "3d" }

export type ZoiEvent =
  | { type: "hello"; payload: { mode: string; agent: { state: AgentStateName; reason: string }; is_mock: boolean } }
  | { type: "agent.state"; at: string; payload: { state: AgentStateName; reason: string } }
  | { type: "task.updated"; at: string; payload: TaskInfo }
  | { type: "chat.delta"; at: string; payload: { conversation_id: string; message_id: string; text: string } }
  | { type: "chat.done"; at: string; payload: { conversation_id: string; message: ChatMessageInfo } }
  | { type: "preferences.updated"; at: string; payload: Preferences };
