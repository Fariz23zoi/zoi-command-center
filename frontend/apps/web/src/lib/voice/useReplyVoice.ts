import type { ChatMessageInfo } from "@zoi/api-client";
import { useEffect } from "react";

import { useApp } from "../../stores/appStore";
import { startReading, stopReading } from "./session";
import type { ReplyReader } from "./replyReader";

/**
 * Membacakan jawaban ZOI bila "Bacakan jawaban" aktif. Hanya jawaban yang mulai ditulis SETELAH halaman dibuka —
 * riwayat lama tidak pernah dibacakan.
 */
export function useReplyVoice() {
  useEffect(() => {
    let current: { id: string; read: number; reader: ReplyReader | null } | null = null;
    const seen = new Set(useApp.getState().messages.map((m) => m.id));

    const onMessages = (messages: ChatMessageInfo[]) => {
      const { voicePrefs } = useApp.getState();
      for (const m of messages) {
        if (m.role !== "assistant" || seen.has(m.id)) continue;
        seen.add(m.id);
        if (m.status !== "streaming") continue;
        current = { id: m.id, read: 0, reader: voicePrefs?.speak_replies ? startReading() : null };
      }
      if (!current) return;
      const message = messages.find((m) => m.id === current?.id);
      if (!message) return;
      if (message.status === "stopped" || message.status === "error") {
        if (current.reader) stopReading();
        current = null;
        return;
      }
      if (current.reader && message.content.length > current.read) {
        current.reader.feed(message.content.slice(current.read));
        current.read = message.content.length;
      }
      if (message.status === "complete") {
        current.reader?.finish();
        current = null;
      }
    };

    return useApp.subscribe((state, prev) => {
      if (state.messages !== prev.messages) onMessages(state.messages);
    });
  }, []);
}
