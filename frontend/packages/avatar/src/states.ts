/** Status yang bisa ditampilkan avatar. Sama persis dengan AgentState di backend. */
export const AGENT_STATES = [
  "IDLE", "LISTENING", "THINKING", "RESEARCHING", "ANALYZING", "PLANNING", "CREATING",
  "EXECUTING", "WAITING_APPROVAL", "SPEAKING", "COMPLETED", "FAILED",
] as const;

export type AgentState = (typeof AGENT_STATES)[number];

export const STATE_LABELS: Record<AgentState, string> = {
  IDLE: "Siap",
  LISTENING: "Mendengarkan",
  THINKING: "Berpikir",
  RESEARCHING: "Meriset",
  ANALYZING: "Menganalisis",
  PLANNING: "Merencanakan",
  CREATING: "Membuat",
  EXECUTING: "Bekerja",
  WAITING_APPROVAL: "Menunggu persetujuan",
  SPEAKING: "Berbicara",
  COMPLETED: "Selesai",
  FAILED: "Gagal",
};

export function isAgentState(value: unknown): value is AgentState {
  return typeof value === "string" && (AGENT_STATES as readonly string[]).includes(value);
}
