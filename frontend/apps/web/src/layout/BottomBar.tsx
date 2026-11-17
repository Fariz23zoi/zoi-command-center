import { api, ApiError, type ChatAttachment, type ChatMessageInfo } from "@zoi/api-client";
import { Paperclip, X } from "lucide-react";
import { type FormEvent, useRef, useState } from "react";

import { MicrophoneError, type Recording, recordingSupported, startRecording } from "../lib/voice/recorder";
import { stopReading } from "../lib/voice/session";
import { useApp } from "../stores/appStore";

/** Pesan yang diawali /agen diperlakukan sama dengan tombol Rencanakan. */
const AGENT_PREFIX = /^\/agen\b\s*(.*)$/is;

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
  const fileRef = useRef<HTMLInputElement>(null);
  const [files, setFiles] = useState<ChatAttachment[]>([]);
  const [reading, setReading] = useState(false);

  async function addFiles(list: FileList | null) {
    if (!list?.length) return;
    setError(null);
    setReading(true);
    try {
      for (const file of Array.from(list)) {
        if (files.length >= 3) { setError("Maksimal 3 lampiran per pesan."); break; }
        if (file.size > 10 * 1024 * 1024) { setError(`${file.name} lebih dari 10 MB.`); continue; }
        const bytes = new Uint8Array(await file.arrayBuffer());
        let bin = "";
        for (let i = 0; i < bytes.length; i += 0x8000) bin += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
        try {
          const item = await api.extractAttachment(file.name, btoa(bin));
          setFiles((cur) => (cur.length >= 3 ? cur : [...cur, item]));
        } catch (err) {
          setError(err instanceof ApiError ? err.message : `${file.name} tidak bisa dibaca.`);
        }
      }
    } finally {
      setReading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  async function send(message: string) {
    const { conversationId, addMessages, setConversation, setSending } = useApp.getState();
    setSending(true);
    setError(null);
    try {
      const res = await api.sendChat(message, conversationId, files);
      if (res.conversation_id !== conversationId) setConversation(res.conversation_id, []);
      addMessages([res.user_message, res.assistant_message]);
      setText("");
      setFiles([]);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Pesan gagal dikirim. Periksa koneksi ke backend.");
    } finally {
      setSending(false);
    }
  }

  async function plan(request: string) {
    const { conversationId, addMessages, setConversation, setSending, setAgentRuns } = useApp.getState();
    setSending(true);
    setError(null);
    try {
      const res = await api.agent.plan(request, conversationId);
      setAgentRuns([res.run]);
      if (res.user_message.conversation_id !== conversationId) setConversation(res.user_message.conversation_id, []);
      addMessages([res.user_message]);
      setText("");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Rencana gagal dibuat. Periksa koneksi ke backend.");
    } finally {
      setSending(false);
    }
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    const message = text.trim() || (files.length ? "Tolong baca dan ringkas lampiran ini." : "");
    if (!message || sending || reading) return;
    stopReading();
    const agent = files.length ? null : AGENT_PREFIX.exec(message);
    if (agent) {
      if (agent[1].trim()) await plan(agent[1].trim());
      else setError("Tulis permintaan setelah /agen, mis. \"/agen cek status sistem\".");
      return;
    }
    await send(message);
  }

  async function planClicked() {
    const message = text.trim().replace(AGENT_PREFIX, "$1").trim();
    if (!message || sending) return;
    stopReading();
    await plan(message);
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
      {files.length > 0 && (
        <ul className="attach-list" aria-label="Lampiran">
          {files.map((f, i) => (
            <li key={`${f.name}-${i}`} className="attach-chip" title={`${(f.chars ?? f.text.length).toLocaleString("id-ID")} karakter${f.truncated ? " — dipotong" : ""}`}>
              📄 {f.name}{f.truncated ? " (dipotong)" : ""}
              <button type="button" className="icon-btn" aria-label={`Hapus lampiran ${f.name}`}
                onClick={() => setFiles((cur) => cur.filter((_, j) => j !== i))}><X size={14} /></button>
            </li>
          ))}
        </ul>
      )}
      <input ref={fileRef} type="file" hidden multiple data-testid="attach-input"
        accept=".txt,.md,.csv,.tsv,.json,.srt,.vtt,.html,.htm,.xml,.yaml,.yml,.log,.py,.js,.ts,.css,.sql,.pdf,.docx"
        onChange={(e) => void addFiles(e.target.files)} />
      <button type="button" className="icon-btn" onClick={() => fileRef.current?.click()} disabled={reading || files.length >= 3}
        aria-label="Lampirkan file" title="Lampirkan file teks, PDF, atau DOCX (maks 3, 10 MB). Isi dibaca di laptop ini."
        data-testid="attach-button">
        {reading ? "…" : <Paperclip size={18} />}
      </button>
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
        <>
          <button type="button" onClick={planClicked} disabled={sending || !text.trim() || isRecording || files.length > 0}
            title="ZOI menyusun rencana langkah memakai tool. Rencana ditampilkan dulu sebelum dijalankan."
            data-testid="plan-button">
            Rencanakan
          </button>
          <button type="submit" className="primary"
            disabled={sending || reading || (!text.trim() && files.length === 0) || isRecording}>
            {sending ? "Mengirim…" : "Kirim"}
          </button>
        </>
      )}
      {(error || voiceError) && <p className="form-error" role="alert">{error ?? voiceError}</p>}
    </form>
  );
}
