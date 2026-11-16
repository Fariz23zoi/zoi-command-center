// API publik paket avatar. Aplikasi hanya boleh mengimpor dari "@zoi/avatar".
export { Avatar, AVATAR_3D_AVAILABLE } from "./Avatar";
export type { AvatarProps, AvatarRenderMode } from "./Avatar";
export type { AvatarCharacter } from "./Avatar3D";
export { clearCachedFps, MIN_FPS, readCachedFps } from "./benchmark";
export type { AvatarController, AvatarControllerRef } from "./controller";
export { AGENT_STATES, STATE_LABELS, isAgentState } from "./states";
export type { AgentState } from "./states";
