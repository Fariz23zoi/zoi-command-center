import { Avatar, isAgentState } from "@zoi/avatar";
import { useEffect, useRef } from "react";

import { ChatTranscript } from "../pages/ChatTranscript";
import { useApp } from "../stores/appStore";

export function CenterStage() {
  const agent = useApp((s) => s.agent);
  const avatarMode = useApp((s) => s.config?.avatar_mode ?? "auto");
  const messages = useApp((s) => s.messages);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // Blok eksplisit: di Chrome terbaru scrollIntoView() mengembalikan Promise, dan React menganggap
    // nilai kembali effect sebagai fungsi pembersih → crash. Jangan kembalikan apa pun.
    void endRef.current?.scrollIntoView?.({ block: "end" });
  }, [messages]);

  return (
    <div className="stage">
      <div className="avatar-wrap">
        <Avatar state={isAgentState(agent.state) ? agent.state : "IDLE"} mode={avatarMode} size={180} />
        <p className="agent-reason" data-testid="agent-reason">{agent.reason}</p>
      </div>
      <div className="stage-chat">
        <ChatTranscript messages={messages.slice(-12)} />
        <div ref={endRef} />
      </div>
    </div>
  );
}
