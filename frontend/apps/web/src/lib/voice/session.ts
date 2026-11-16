import { api, type VoicePreferences } from "@zoi/api-client";

import { useApp } from "../../stores/appStore";
import { avatarController } from "../avatarBridge";
import { pickVoice, speakWithBrowser } from "./browserVoices";
import { ReplyReader } from "./replyReader";

/** Memutar WAV: lewat avatar 3D (lip-sync) bila aktif, selain itu lewat <audio> biasa. */
export async function playAudio(audio: Blob, signal: AbortSignal): Promise<void> {
  const avatar = avatarController.current;
  if (avatar?.renderer === "3d") {
    const stop = () => avatar.stopSpeaking();
    signal.addEventListener("abort", stop, { once: true });
    try {
      await avatar.speak(audio);
    } finally {
      signal.removeEventListener("abort", stop);
    }
    return;
  }
  const url = URL.createObjectURL(audio);
  const element = new Audio(url);
  try {
    await new Promise<void>((resolve, reject) => {
      element.onended = () => resolve();
      element.onerror = () => reject(new Error("Audio tidak dapat diputar."));
      signal.addEventListener("abort", () => { element.pause(); resolve(); }, { once: true });
      element.play().catch(reject);
    });
  } finally {
    URL.revokeObjectURL(url);
  }
}

function makeReader(prefs: VoicePreferences, engine: "piper" | "browser"): ReplyReader {
  const { setVoicePhase, setVoiceError } = useApp.getState();
  const common = {
    onSpeaking: (speaking: boolean) => setVoicePhase(speaking ? "speaking" : null),
    onError: (message: string) => setVoiceError(message),
  };
  if (engine === "piper") {
    return new ReplyReader({ ...common, fetchAudio: (text, signal) => api.voice.speak(text, signal), playAudio });
  }
  const voice = pickVoice(prefs.browser_voice, prefs.language);
  return new ReplyReader({
    ...common,
    speakText: (text, signal) => speakWithBrowser(text, voice, prefs.speech_rate, signal),
  });
}

let reader: ReplyReader | null = null;

/** Pembaca untuk satu jawaban. Jawaban baru menghentikan pembacaan sebelumnya. */
export function startReading(): ReplyReader | null {
  const { voicePrefs, voiceStatus } = useApp.getState();
  if (!voicePrefs || !voiceStatus) return null;
  reader?.stop();
  reader = makeReader(voicePrefs, voiceStatus.reply_engine);
  return reader;
}

export function stopReading() {
  reader?.stop();
  reader = null;
  useApp.getState().setVoicePhase(null);
}

/** "Coba suara" di Settings: memakai mesin & preferensi yang sedang aktif. */
export function speakSample(text: string): ReplyReader | null {
  const r = startReading();
  r?.feed(text);
  r?.finish();
  return r;
}
