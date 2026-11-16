import { Avatar, isAgentState, STATE_LABELS, type AgentState } from "@zoi/avatar";
import { lazy, Suspense, useState } from "react";

import { avatarController } from "../lib/avatarBridge";
import { effectiveAvatarMode } from "../lib/avatarMode";
import { useApp } from "../stores/appStore";
import { ZONE_OF, ZONES } from "./zones";

const OfficeScene = lazy(() => import("./OfficeScene"));

const VOICE_STATE = {
  recording: { state: "LISTENING", reason: "Mendengarkan — tekan Selesai bila sudah" },
  transcribing: { state: "THINKING", reason: "Mengenali suara" },
  speaking: { state: "SPEAKING", reason: "Membacakan jawaban" },
} as const;

function hasWebGL2(): boolean {
  try {
    const gl = document.createElement("canvas").getContext("webgl2");
    gl?.getExtension("WEBGL_lose_context")?.loseContext();
    return !!gl;
  } catch {
    return false;
  }
}

/** Panggung workspace AI: kantor 3D (bila perangkat sanggup) atau avatar 2D. Status selalu dari backend/suara nyata. */
export function OfficeStage({ compact, allowOffice }: { compact: boolean; allowOffice: boolean }) {
  const agent = useApp((s) => s.agent);
  const voicePhase = useApp((s) => s.voicePhase);
  const shown = voicePhase ? VOICE_STATE[voicePhase] : { state: agent.state, reason: agent.reason };
  const state: AgentState = isAgentState(shown.state) ? shown.state : "IDLE";
  const serverMode = useApp((s) => s.config?.avatar_mode);
  const prefs = useApp((s) => s.prefs);
  const bootstrapped = useApp((s) => s.bootstrapped);
  const [fallback, setFallback] = useState<string | null>(null);
  const [webgl] = useState(hasWebGL2);
  const setAvatarRenderer = useApp((s) => s.setAvatarRenderer);

  if (!bootstrapped || !prefs) return <div className="ai-stage" aria-hidden="true" />;
  const mode = effectiveAvatarMode(serverMode, prefs.avatar_mode_preference);
  const office = allowOffice && mode !== "2d" && webgl && !fallback && !compact;
  const zone = ZONES[ZONE_OF[state]];

  return (
    <div className={`ai-stage${office ? " office" : ""}`} data-testid="ai-stage">
      {office ? (
        <div className="ai-office" role="img" aria-label={`Avatar ZOI di kantor — ${STATE_LABELS[state]} (${zone.label})`}>
          <Suspense fallback={<p className="muted ai-loading">Menyiapkan kantor 3D…</p>}>
            <OfficeScene state={state} onFallback={setFallback} />
          </Suspense>
          <p className="ai-zone"><span>{zone.label}</span> {STATE_LABELS[state]}</p>
        </div>
      ) : (
        <Avatar state={state} mode={fallback ? "2d" : mode} character={prefs.avatar_character} size={compact ? 96 : 150}
          controllerRef={avatarController} onRendererChange={setAvatarRenderer} />
      )}
      <p className="agent-reason" data-testid="agent-reason">{shown.reason}</p>
      {fallback && <p className="zoi-avatar-note">{fallback}</p>}
    </div>
  );
}
