import { Avatar, isAgentState } from "@zoi/avatar";
import { useEffect, useRef } from "react";

import { avatarController } from "../lib/avatarBridge";
import { effectiveAvatarMode } from "../lib/avatarMode";
import { ChatTranscript } from "../pages/ChatTranscript";
import { useApp } from "../stores/appStore";

export function CenterStage() {
  const agent = useApp((s) => s.agent);
  const serverMode = useApp((s) => s.config?.avatar_mode);
  const prefs = useApp((s) => s.prefs);
  const setAvatarRenderer = useApp((s) => s.setAvatarRenderer);
  const messages = useApp((s) => s.messages);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // Blok eksplisit: di Chrome terbaru scrollIntoView() mengembalikan Promise, dan React menganggap
    // nilai kembali effect sebagai fungsi pembersih → crash. Jangan kembalikan apa pun.
    void endRef.current?.scrollIntoView?.({ block: "end" });
  }, [messages]);

  // Tunggu konfigurasi & preferensi agar avatar tidak dibuat dua kali (2D lalu 3D) saat halaman dibuka.
  const bootstrapped = useApp((s) => s.bootstrapped);
  const loaded = bootstrapped && prefs !== null;

  return (
    <div className="stage">
      <div className="avatar-wrap">
        {loaded ? (
          <Avatar
            state={isAgentState(agent.state) ? agent.state : "IDLE"}
            mode={effectiveAvatarMode(serverMode, prefs.avatar_mode_preference)}
            character={prefs.avatar_character}
            size={180}
            controllerRef={avatarController}
            onRendererChange={setAvatarRenderer}
          />
        ) : <div className="avatar-placeholder" aria-hidden="true" />}
        <p className="agent-reason" data-testid="agent-reason">{agent.reason}</p>
      </div>
      <div className="stage-chat">
        <ChatTranscript messages={messages.slice(-12)} />
        <div ref={endRef} />
      </div>
    </div>
  );
}
