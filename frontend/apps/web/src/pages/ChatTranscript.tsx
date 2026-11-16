import type { ChatMessageInfo } from "@zoi/api-client";

export function ChatTranscript({ messages }: { messages: ChatMessageInfo[] }) {
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
          {m.status === "error" && <p className="msg-error" role="alert">{m.error}</p>}
        </li>
      ))}
    </ol>
  );
}
