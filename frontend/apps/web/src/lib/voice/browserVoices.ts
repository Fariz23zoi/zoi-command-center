/** Suara bawaan sistem lewat speechSynthesis. HANYA suara lokal (localService) — suara cloud tidak pernah dipakai. */
export interface LocalVoice { name: string; lang: string }

export function speechSupported(): boolean {
  return typeof window !== "undefined" && "speechSynthesis" in window && typeof SpeechSynthesisUtterance !== "undefined";
}

export function localVoices(): SpeechSynthesisVoice[] {
  if (!speechSupported()) return [];
  return window.speechSynthesis.getVoices()
    .filter((v) => v.localService)
    .sort((a, b) => rank(a) - rank(b) || a.name.localeCompare(b.name));
}

function rank(v: SpeechSynthesisVoice): number {
  const lang = v.lang.toLowerCase();
  return lang.startsWith("id") ? 0 : lang.startsWith("en") ? 1 : 2;
}

/** Daftar suara bisa terlambat dimuat browser; tunggu sebentar. */
export function whenVoicesReady(timeoutMs = 1500): Promise<SpeechSynthesisVoice[]> {
  if (!speechSupported()) return Promise.resolve([]);
  const now = localVoices();
  if (window.speechSynthesis.getVoices().length) return Promise.resolve(now);
  return new Promise((resolve) => {
    const done = () => { window.speechSynthesis.removeEventListener("voiceschanged", done); resolve(localVoices()); };
    window.speechSynthesis.addEventListener("voiceschanged", done);
    setTimeout(done, timeoutMs);
  });
}

export function pickVoice(preferred: string | null, language: string): SpeechSynthesisVoice | null {
  const voices = localVoices();
  return voices.find((v) => v.name === preferred)
    ?? voices.find((v) => v.lang.toLowerCase().startsWith(language === "en" ? "en" : "id"))
    ?? null;
}

export function speakWithBrowser(text: string, voice: SpeechSynthesisVoice | null, rate: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (!voice) {
      reject(new Error("Tidak ada suara lokal di komputer ini. Tambahkan paket bahasa Indonesia di Windows."));
      return;
    }
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.voice = voice;
    utterance.lang = voice.lang;
    utterance.rate = rate;
    utterance.onend = () => resolve();
    utterance.onerror = (e) => (e.error === "interrupted" || e.error === "canceled" ? resolve() : reject(new Error(e.error)));
    signal.addEventListener("abort", () => window.speechSynthesis.cancel(), { once: true });
    window.speechSynthesis.speak(utterance);
  });
}
