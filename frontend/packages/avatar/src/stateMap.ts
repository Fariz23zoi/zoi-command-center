import type { AgentState } from "./states";

/** talking-avatar hanya punya "listening" dan "thinking"; "speaking" terdeteksi otomatis dari audio. */
export type TalkingStatus = "listening" | "thinking";

const THINKING: ReadonlySet<AgentState> = new Set([
  "THINKING", "PLANNING", "RESEARCHING", "ANALYZING", "CREATING", "EXECUTING",
]);

export function toTalkingStatus(state: AgentState): TalkingStatus {
  return THINKING.has(state) ? "thinking" : "listening";
}
