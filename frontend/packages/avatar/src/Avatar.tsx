import { lazy, Suspense, useCallback, useEffect, useMemo, useState } from "react";

import { Avatar2D } from "./Avatar2D";
import type { AvatarCharacter } from "./Avatar3D";
import { MIN_FPS, readCachedFps } from "./benchmark";
import { detectCapabilities } from "./capabilities";
import { type AvatarControllerRef, controller2D } from "./controller";
import type { AgentState } from "./states";

// three.js dan model avatar hanya diunduh bila renderer 3D benar-benar dipakai.
const Avatar3D = lazy(() => import("./Avatar3D"));

export type AvatarRenderMode = "auto" | "2d" | "3d";

export interface AvatarProps {
  /** Status nyata dari backend (event agent.state). */
  state: AgentState;
  /** "auto": 3D bila perangkat mampu (diuji FPS), "2d": selalu 2D, "3d": 3D bila browser mendukung. */
  mode?: AvatarRenderMode;
  character?: AvatarCharacter;
  size?: number;
  /** Lokasi aset avatar yang di-host sendiri. */
  assetBase?: string;
  controllerRef?: AvatarControllerRef;
  onRendererChange?(renderer: "2d" | "3d", note: string | null): void;
}

export const AVATAR_3D_AVAILABLE = true;

interface Decision { renderer: "2d" | "3d"; note: string | null }

function decide(mode: AvatarRenderMode): Decision {
  if (mode === "2d") return { renderer: "2d", note: null };
  const caps = detectCapabilities();
  if (!caps.ok) return { renderer: "2d", note: caps.reason };
  if (mode === "auto") {
    const fps = readCachedFps();
    if (fps !== null && fps < MIN_FPS) {
      return { renderer: "2d", note: `Avatar 3D dimatikan otomatis: perangkat ini sekitar ${Math.round(fps)} fps. `
        + "Bisa diuji ulang di Settings." };
    }
  }
  return { renderer: "3d", note: null };
}

/** Satu-satunya komponen avatar yang boleh dipakai aplikasi. Renderer dipilih di sini, bukan di aplikasi. */
export function Avatar({ state, mode = "auto", character = "female", size = 220, assetBase = "/avatar-assets",
  controllerRef, onRendererChange }: AvatarProps) {
  const initial = useMemo(() => decide(mode), [mode]);
  // Fallback terikat pada mode tempat ia terjadi: ganti mode = coba lagi, tanpa efek reset.
  const [fallback, setFallback] = useState<{ mode: AvatarRenderMode; note: string } | null>(null);
  const fallbackNote = fallback && fallback.mode === mode ? fallback.note : null;

  const renderer = fallbackNote ? "2d" : initial.renderer;
  const note = fallbackNote ?? initial.note;

  useEffect(() => {
    if (renderer === "2d" && controllerRef) controllerRef.current = controller2D;
    onRendererChange?.(renderer, note);
  }, [renderer, note, controllerRef, onRendererChange]);

  const onFallback = useCallback((reason: string) => setFallback({ mode, note: reason }), [mode]);
  const fallback2D = <Avatar2D state={state} size={size} />;

  return (
    <div className="zoi-avatar" data-renderer={renderer}>
      {renderer === "3d" ? (
        <Suspense fallback={fallback2D}>
          <Avatar3D state={state} character={character} assetBase={assetBase} size={size}
            benchmark={mode === "auto"} controllerRef={controllerRef} onFallback={onFallback} />
        </Suspense>
      ) : fallback2D}
      {note && <p className="zoi-avatar-note" role="status">{note}</p>}
    </div>
  );
}
