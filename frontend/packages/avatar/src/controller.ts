/** Kendali avatar dari luar (mis. Phase 4: TTS lokal → speak()). */
export interface AvatarController {
  readonly renderer: "2d" | "3d";
  /** Putar audio dengan lip-sync. Hanya renderer 3D yang mendukung lip-sync. */
  speak(audio: Blob | ArrayBuffer | string): Promise<void>;
  stopSpeaking(): void;
}

export interface AvatarControllerRef {
  current: AvatarController | null;
}

export const controller2D: AvatarController = {
  renderer: "2d",
  speak: () => Promise.reject(new Error("Lip-sync hanya tersedia pada avatar 3D.")),
  stopSpeaking: () => undefined,
};
