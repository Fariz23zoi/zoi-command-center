import { api, ApiError, type ChatMessageInfo } from "@zoi/api-client";
import { type FormEvent, useRef, useState } from "react";

import { MicrophoneError, type Recording, recordingSupported, startRecording } from "../lib/voice/recorder";
import { stopReading } from "../lib/voice/session";
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
  const voicePhase = useApp((s) => s.voicePhase);
  const voiceError = useApp((s) => s.voiceError);
  const stt = useApp((s) => s.voiceStatus?.stt);
  const recording = useRef<Recording | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  async function send(message: string) {
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

  async function submit(event: FormEvent) {
    event.preventDefault();
    const message = text.trim();
    if (!message || sending) return;
    stopReading();
    await send(message);
  }

  async function stop() {
    stopReading();
    if (!streamingId) return;
    try {
      await api.stopChat(streamingId);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Gagal menghentikan jawaban.");
    }
  }

  async function toggleMic() {
    const { setVoicePhase, setVoiceError } = useApp.getState();
    setError(null);
    setVoiceError(null);
    if (recording.current) {
      await finishRecording();
      return;
    }
    stopReading();
    try {
      recording.current = await startRecording(() => void finishRecording());
      setVoicePhase("recording");
    } catch (err) {
      setError(err instanceof MicrophoneError ? err.message : "Mikrofon tidak dapat dipakai.");
    }
  }

  async function finishRecording() {
    const current = recording.current;
    if (!current) return;
    recording.current = null;
    const { setVoicePhase, voicePrefs } = useApp.getState();
    setVoicePhase("transcribing");
    try {
      const audio = await current.stop();
      const result = await api.voice.transcribe(audio, voicePrefs?.language);
      const heard = result.text.trim();
      if (!heard) {
        setError("Tidak ada suara yang terdengar. Coba lagi lebih dekat ke mikrofon.");
        return;
      }
      if (voicePrefs?.auto_send) {
        await send(heard);
      } else {
        setText((prev) => (prev.trim() ? `${prev.trim()} ${heard}` : heard));
        inputRef.current?.focus();
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Suara gagal dikenali.");
    } finally {
      setVoicePhase(null);
    }
  }

  function cancelRecording() {
    recording.current?.cancel();
    recording.current = null;
    useApp.getState().setVoicePhase(null);
  }

  const micReady = !!stt?.available && recordingSupported();
  const micTitle = !recordingSupported() ? "Browser ini tidak mendukung perekaman suara."
    : !stt ? "Memuat status suara…" : stt.available ? "Bicara ke ZOI (rekaman tidak disimpan)" : stt.detail;
  const isRecording = voicePhase === "recording";
  const showStop = !!streamingId || voicePhase === "speaking";

  return (
    <form className="bottombar" onSubmit={submit} aria-label="Kirim pesan ke ZOI">
      <label htmlFor="chat-input" className="sr-only">Pesan untuk ZOI</label>
      <input id="chat-input" ref={inputRef} value={text} onChange={(e) => setText(e.target.value)} maxLength={4000}
        placeholder={isRecording ? "Mendengarkan…" : "Tulis pesan untuk ZOI…"} autoComplete="off" />
      {isRecording ? (
        <>
          <button type="button" className="primary recording" onClick={toggleMic} data-testid="mic-finish">
            ■ Selesai
          </button>
          <button type="button" onClick={cancelRecording}>Batal</button>
        </>
      ) : (
        <button type="button" className="icon-btn" onClick={toggleMic} disabled={!micReady || voicePhase === "transcribing"}
          title={micTitle} aria-label={micReady ? "Bicara ke ZOI" : `Input suara tidak tersedia: ${micTitle}`}
          data-testid="mic-button">
          {voicePhase === "transcribing" ? "…" : "🎙"}
        </button>
      )}
      {showStop ? (
        <button type="button" onClick={stop} data-testid="stop-button">Berhenti</button>
      ) : (
        <button type="submit" className="primary" disabled={sending || !text.trim() || isRecording}>
          {sending ? "Mengirim…" : "Kirim"}
        </button>
      )}
      {(error || voiceError) && <p className="form-error" role="alert">{error ?? voiceError}</p>}
    </form>
  );
}
