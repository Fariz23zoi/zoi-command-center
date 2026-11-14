import { SentenceSplitter, speakable } from "./sentences";

export interface ReaderDeps {
  /** Piper: teks → audio (WAV). Browser: undefined. */
  fetchAudio?: (text: string, signal: AbortSignal) => Promise<Blob>;
  /** Memutar audio Piper (avatar 3D dengan lip-sync, atau <audio> biasa). */
  playAudio?: (audio: Blob, signal: AbortSignal) => Promise<void>;
  /** Suara browser lokal. */
  speakText?: (text: string, signal: AbortSignal) => Promise<void>;
  onSpeaking: (speaking: boolean) => void;
  onError: (message: string) => void;
}

/**
 * Membacakan jawaban kalimat demi kalimat. Audio kalimat berikutnya disiapkan saat kalimat sekarang diputar.
 * stop() menghentikan semuanya seketika (permintaan audio dibatalkan, pemutaran dihentikan).
 */
export class ReplyReader {
  private splitter = new SentenceSplitter();
  private queue: { text: string; audio?: Promise<Blob> }[] = [];
  private controller = new AbortController();
  private running = false;

  constructor(private deps: ReaderDeps) {}

  feed(text: string) {
    this.enqueue(this.splitter.feed(text));
  }

  finish() {
    this.enqueue(this.splitter.flush());
    if (!this.running && !this.queue.length) this.deps.onSpeaking(false);
  }

  stop() {
    this.controller.abort();
    this.controller = new AbortController();
    this.queue = [];
    this.splitter = new SentenceSplitter();
    if (this.running) this.deps.onSpeaking(false);
    this.running = false;
  }

  get active(): boolean {
    return this.running || this.queue.length > 0;
  }

  private enqueue(sentences: string[]) {
    for (const raw of sentences) {
      const text = speakable(raw);
      if (!text) continue;
      this.queue.push({ text });
    }
    this.prefetch();
    if (!this.running && this.queue.length) void this.run();
  }

  private prefetch() {
    const { fetchAudio } = this.deps;
    if (!fetchAudio) return;
    const signal = this.controller.signal;
    for (const item of this.queue.slice(0, 2)) {
      if (!item.audio) {
        item.audio = fetchAudio(item.text, signal);
        item.audio.catch(() => undefined); // ditangani saat giliran diputar
      }
    }
  }

  private async run() {
    this.running = true;
    const signal = this.controller.signal;
    this.deps.onSpeaking(true);
    try {
      while (this.queue.length && !signal.aborted) {
        const item = this.queue[0];
        this.prefetch();
        if (item.audio && this.deps.playAudio) {
          await this.deps.playAudio(await item.audio, signal);
        } else if (this.deps.speakText) {
          await this.deps.speakText(item.text, signal);
        }
        this.queue.shift();
        this.prefetch();
      }
    } catch (err) {
      if (!signal.aborted) {
        this.queue = [];
        this.deps.onError((err as Error).message || "Suara gagal diputar.");
      }
    } finally {
      if (!signal.aborted) {
        this.running = false;
        if (!this.queue.length) this.deps.onSpeaking(false);
      }
    }
  }
}
