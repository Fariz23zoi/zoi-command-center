import type { ChatMessageInfo } from "@zoi/api-client";

import { useApp } from "../stores/appStore";

const CLOUD_LABEL: Record<string, string> = { nvidia: "NVIDIA NIM", openrouter: "OpenRouter" };
import { AgentRunCard } from "./AgentRunCard";

export function ChatTranscript({ messages }: { messages: ChatMessageInfo[] }) {
  const runs = useApp((s) => s.agentRuns);
  if (messages.length === 0) {
    return <p className="muted empty-chat">Belum ada percakapan. Tulis pesan di bawah.</p>;
  }
  return (
    <ol className="transcript" aria-live="polite">
      {messages.map((m) => (
        <li key={m.id} className={`msg msg-${m.role} msg-${m.status}`} data-testid={`msg-${m.role}`}>
          <div className="msg-meta">
            <span>{m.role === "user" ? "Kamu" : "ZOI"}</span>
            {m.role === "assistant" && m.is_mock && <span className="badge mock" data-testid="mock-badge">MOCK</span>}
            {m.role === "assistant" && m.provider && CLOUD_LABEL[m.provider] && (
              <span className="badge cloud" data-testid="cloud-badge">
                AI cloud · {CLOUD_LABEL[m.provider]}{m.model ? ` · ${m.model}` : ""}
              </span>
            )}
            {m.agent_run_id && <span className="badge">{m.role === "user" ? "permintaan agen" : "hasil agen"}</span>}
            {m.role === "assistant" && m.status === "streaming" && <span className="badge">menulis…</span>}
            {m.status === "stopped" && <span className="badge" data-testid="stopped-badge">dihentikan</span>}
          </div>
          {m.thinking && (
            <details className="msg-thinking" data-testid="msg-thinking">
              <summary>Proses berpikir model</summary>
              <p>{m.thinking}</p>
            </details>
          )}
          {m.content && <p className="msg-body">{m.content}</p>}
          {m.note && <p className="msg-note" data-testid="msg-note">{m.note}</p>}
          {m.status === "error" && <p className="msg-error" role="alert">{m.error}</p>}
          {m.role === "user" && m.agent_run_id && runs[m.agent_run_id] && <AgentRunCard run={runs[m.agent_run_id]} />}
          {m.role === "user" && m.agent_run_id && !runs[m.agent_run_id] && <p className="muted">Memuat permintaan agen…</p>}
        </li>
      ))}
    </ol>
  );
}
