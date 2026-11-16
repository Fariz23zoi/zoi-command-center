import { Avatar2D } from "./Avatar2D";
import type { AgentState } from "./states";

export type AvatarRenderMode = "auto" | "2d" | "3d";

export interface AvatarProps {
  /** Status nyata dari backend (event agent.state). */
  state: AgentState;
  /** Preferensi renderer. "3d" baru tersedia di Phase 2 — sementara selalu memakai 2D dengan keterangan jujur. */
  mode?: AvatarRenderMode;
  size?: number;
}

export const AVATAR_3D_AVAILABLE = false;

/** Satu-satunya komponen avatar yang boleh dipakai aplikasi. Renderer bisa diganti tanpa mengubah pemakai. */
export function Avatar({ state, mode = "auto", size }: AvatarProps) {
  const fallbackNote = mode === "3d" && !AVATAR_3D_AVAILABLE;
  return (
    <div className="zoi-avatar" data-renderer="2d">
      <Avatar2D state={state} size={size} />
      {fallbackNote && <p className="zoi-avatar-note">Avatar 3D tersedia di Phase 2 — sementara memakai 2D.</p>}
    </div>
  );
}
