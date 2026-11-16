/** Rekaman tekan-untuk-bicara. Audio hanya dikirim ke backend ZOI di komputer ini, lalu dibuang. */
export const MAX_RECORD_MS = 60_000;
const TYPES = ["audio/webm;codecs=opus", "audio/ogg;codecs=opus", "audio/webm", "audio/mp4"];

export interface Recording {
  stop(): Promise<Blob>;
  cancel(): void;
}

export class MicrophoneError extends Error {}

export function recordingSupported(): boolean {
  return typeof navigator !== "undefined" && !!navigator.mediaDevices?.getUserMedia && typeof MediaRecorder !== "undefined";
}

export async function startRecording(onAutoStop: () => void): Promise<Recording> {
  if (!recordingSupported()) throw new MicrophoneError("Browser ini tidak mendukung perekaman suara.");
  let stream: MediaStream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } });
  } catch (err) {
    const name = (err as DOMException).name;
    throw new MicrophoneError(name === "NotAllowedError"
      ? "Izin mikrofon ditolak. Izinkan mikrofon untuk alamat ZOI di pengaturan browser."
      : name === "NotFoundError" ? "Mikrofon tidak ditemukan." : "Mikrofon tidak dapat dipakai.");
  }
  const mimeType = TYPES.find((t) => MediaRecorder.isTypeSupported(t));
  const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
  const chunks: Blob[] = [];
  recorder.ondataavailable = (e) => { if (e.data.size) chunks.push(e.data); };
  const finished = new Promise<Blob>((resolve) => {
    recorder.onstop = () => {
      stream.getTracks().forEach((t) => t.stop());
      resolve(new Blob(chunks, { type: recorder.mimeType || mimeType || "audio/webm" }));
    };
  });
  recorder.start(250);
  const timer = setTimeout(onAutoStop, MAX_RECORD_MS);
  return {
    stop() {
      clearTimeout(timer);
      if (recorder.state !== "inactive") recorder.stop();
      return finished;
    },
    cancel() {
      clearTimeout(timer);
      chunks.length = 0;
      if (recorder.state !== "inactive") recorder.stop();
      stream.getTracks().forEach((t) => t.stop());
    },
  };
}
