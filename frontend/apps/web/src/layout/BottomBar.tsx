import { api, ApiError, type ChatMessageInfo } from "@zoi/api-client";
import { type FormEvent, useState } from "react";

import { useApp } from "../stores/appStore";

function streamingMessageId(messages: ChatMessageInfo[]): string | undefined {
  for (let i = messages.length - 1; i >= 0; i -= 1) {
    if (messages[i].role === "assistant" && messages[i].status === "streaming") return messages[i].id;
  }
  return undefined;
}

export function BottomBar() {
  const [text, setText] = useState("");
  const [error, setError] = useState<string | null>(null);
  const sending = useApp((s) => s.sending);
  const streamingId = useApp((s) => streamingMessageId(s.messages));

  async function stop(messageId: string) {
    try {
      await api.stopChat(messageId);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Gagal menghentikan jawaban.");
    }
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    const message = text.trim();
    if (!message || sending) return;
    const { conversationId, addMessages, setConversation, setSending } = useApp.getState();
    setSending(true);
    setError(null);
    try {
      const res = await api.sendChat(message, conversationId);
      if (res.conversation_id !== conversationId) setConversation(res.conversation_id, []);
      addMessages([res.user_message, res.assistant_message]);
      setText("");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Pesan gagal dikirim. Periksa koneksi ke backend.");
    } finally {
      setSending(false);
    }
  }

  return (
    <form className="bottombar" onSubmit={submit} aria-label="Kirim pesan ke ZOI">
      <label htmlFor="chat-input" className="sr-only">Pesan untuk ZOI</label>
      <input id="chat-input" value={text} onChange={(e) => setText(e.target.value)} maxLength={4000}
        placeholder="Tulis pesan untuk ZOI…" autoComplete="off" />
      <button type="button" className="icon-btn" disabled title="Input suara tersedia di Phase 4"
        aria-label="Input suara (tersedia di Phase 4)">🎙</button>
      {streamingId ? (
        <button type="button" onClick={() => stop(streamingId)} data-testid="stop-button">Berhenti</button>
      ) : (
        <button type="submit" className="primary" disabled={sending || !text.trim()}>
          {sending ? "Mengirim…" : "Kirim"}
        </button>
      )}
      {error && <p className="form-error" role="alert">{error}</p>}
    </form>
  );
}
