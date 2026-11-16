import type { AgentState } from "@zoi/avatar";

export type ZoneId = "lounge" | "booth" | "desk" | "board" | "meeting" | "library";

/** Zona kantor: titik berdiri robot (x, z), arah hadap, dan label yang ditampilkan. */
export const ZONES: Record<ZoneId, { spot: [number, number]; face: number; label: string }> = {
  lounge: { spot: [-4.3, 3.4], face: 0.8, label: "Lounge" },
  booth: { spot: [-5, -2.1], face: Math.PI, label: "Phone booth" },
  desk: { spot: [0, -1.7], face: Math.PI, label: "Meja kerja" },
  board: { spot: [1.6, 3.4], face: Math.PI, label: "Papan tugas" },
  meeting: { spot: [4.3, -1], face: 0.8, label: "Ruang rapat" },
  library: { spot: [5.1, 2.6], face: Math.PI, label: "Perpustakaan" },
};

/** Status nyata ZOI → zona. */
export const ZONE_OF: Record<AgentState, ZoneId> = {
  IDLE: "lounge", COMPLETED: "lounge", LISTENING: "booth", THINKING: "desk", PLANNING: "desk", ANALYZING: "desk",
  CREATING: "board", EXECUTING: "board", WAITING_APPROVAL: "board", FAILED: "board", SPEAKING: "meeting",
  RESEARCHING: "library",
};
