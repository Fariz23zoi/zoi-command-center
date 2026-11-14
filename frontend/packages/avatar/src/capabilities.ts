/** Deteksi kemampuan browser untuk avatar 3D (WebGL 2 + AudioWorklet). Tanpa efek samping. */
export interface Capabilities {
  ok: boolean;
  webgl2: boolean;
  audioWorklet: boolean;
  reason: string | null;
}

export function detectCapabilities(): Capabilities {
  let webgl2: boolean;
  try {
    const canvas = document.createElement("canvas");
    const gl = canvas.getContext("webgl2");
    webgl2 = !!gl;
    gl?.getExtension("WEBGL_lose_context")?.loseContext();
  } catch {
    webgl2 = false;
  }
  const AudioCtx = (globalThis as { AudioContext?: typeof AudioContext }).AudioContext;
  const audioWorklet = typeof AudioCtx === "function" && "audioWorklet" in AudioCtx.prototype;
  const missing = [!webgl2 && "WebGL 2", !audioWorklet && "AudioWorklet"].filter(Boolean);
  return {
    ok: missing.length === 0,
    webgl2,
    audioWorklet,
    reason: missing.length ? `Browser ini tidak mendukung ${missing.join(" dan ")} — avatar memakai mode 2D.` : null,
  };
}
