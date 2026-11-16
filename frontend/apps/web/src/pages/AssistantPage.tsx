import { api, type ConversationInfo } from "@zoi/api-client";
import { useEffect, useState } from "react";

import { useApp } from "../stores/appStore";
import { ChatTranscript } from "./ChatTranscript";

export function AssistantPage() {
  const [conversations, setConversations] = useState<ConversationInfo[]>([]);
  const conversationId = useApp((s) => s.conversationId);
  const messages = useApp((s) => s.messages);

  useEffect(() => {
    api.conversations().then((r) => setConversations(r.conversations)).catch(() => undefined);
  }, [conversationId, messages.length]);

  async function open(id: string) {
    const { messages: list } = await api.messages(id);
    useApp.getState().setConversation(id, list);
  }

  return (
    <section className="page">
      <h1>AI Assistant</h1>
      <p className="muted">Chat dasar Phase 1. Agent yang bisa menjalankan tools dibangun di Phase 5.</p>
      <div className="row">
        <button type="button" onClick={() => useApp.getState().setConversation(null, [])}>Percakapan baru</button>
      </div>
      <h2>Riwayat</h2>
      {conversations.length === 0 && <p className="muted">Belum ada percakapan.</p>}
      <ul className="conversation-list">
        {conversations.map((c) => (
          <li key={c.id}>
            <button type="button" className={c.id === conversationId ? "link active" : "link"} onClick={() => open(c.id)}>
              {c.title}
            </button>
            {c.is_mock && <span className="badge mock">MOCK</span>}
          </li>
        ))}
      </ul>
      <h2>Percakapan aktif</h2>
      <ChatTranscript messages={messages} />
    </section>
  );
}
