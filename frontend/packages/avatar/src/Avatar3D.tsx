import { TalkingAvatar } from "@interviewflowai/talking-avatar";
import { useEffect, useRef, useState } from "react";

import { measureFps, MIN_FPS, storeCachedFps } from "./benchmark";
import type { AvatarControllerRef } from "./controller";
import type { AgentState } from "./states";
import { STATE_LABELS } from "./states";
import { toTalkingStatus } from "./stateMap";
import "./states.css";
import "./avatar3d.css";

export type AvatarCharacter = "female" | "male";

export interface Avatar3DProps {
  state: AgentState;
  character: AvatarCharacter;
  /** Folder aset yang di-host sendiri (tanpa CDN). */
  assetBase: string;
  size: number;
  /** Jalankan uji FPS setelah avatar tampil (mode otomatis). */
  benchmark: boolean;
  controllerRef?: AvatarControllerRef;
  /** Avatar 3D tidak layak dipakai → kembali ke 2D dengan alasan yang ditampilkan ke pengguna. */
  onFallback(reason: string): void;
}

/**
 * Avatar 3D (Microsoft Rocketbox via talking-avatar, MIT). Wajah close-up dengan lip-sync dari audio, kedip, dan alis.
 * Keterbatasan paket: tidak ada gerak kepala, arah pandang, atau ekspresi senyum/cemberut — status ZOI ditampilkan
 * lewat cincin warna dan label.
 */
export default function Avatar3D({ state, character, assetBase, size, benchmark, controllerRef, onFallback }: Avatar3DProps) {
  const box = useRef<HTMLDivElement>(null);
  const instance = useRef<TalkingAvatar | null>(null);
  const loadedCharacter = useRef(character);
  const fallback = useRef(onFallback);
  const [ready, setReady] = useState(false);
  const [warning, setWarning] = useState<string | null>(null);

  useEffect(() => { fallback.current = onFallback; }, [onFallback]);

  useEffect(() => {
    const container = box.current;
    if (!container) return;
    let cancelled = false;
    let avatar: TalkingAvatar;
    try {
      avatar = new TalkingAvatar({
        container,
        avatarUrl: `${assetBase}/${loadedCharacter.current}.glb`,
        modelUrl: `${assetBase}/viseme-model.bin`,
        onError: (error) => { if (!cancelled) setWarning(`Avatar 3D: ${error.message}`); },
      });
    } catch (error) {
      fallback.current(`Avatar 3D tidak dapat dibuat: ${(error as Error).message}`);
      return;
    }
    instance.current = avatar;
    if (controllerRef) {
      controllerRef.current = {
        renderer: "3d",
        speak: (audio) => avatar.speak(audio),
        stopSpeaking: () => avatar.stopSpeaking(),
      };
    }
    avatar.ready
      .then(async () => {
        if (cancelled) return;
        setReady(true);
        if (!benchmark) return;
        const fps = await measureFps();
        if (cancelled) return;
        storeCachedFps(fps);
        if (fps < MIN_FPS) {
          fallback.current(`Perangkat ini menampilkan avatar 3D sekitar ${Math.round(fps)} fps (minimal ${MIN_FPS}) — `
            + "beralih ke 2D agar tetap ringan. Bisa diuji ulang di Settings.");
        }
      })
      .catch((error: Error) => { if (!cancelled) fallback.current(`Avatar 3D gagal dimuat: ${error.message}`); });

    return () => {
      cancelled = true;
      if (controllerRef?.current?.renderer === "3d") controllerRef.current = null;
      avatar.dispose();
      instance.current = null;
    };
  }, [assetBase, benchmark, controllerRef]);

  useEffect(() => {
    if (!ready || loadedCharacter.current === character) return;
    loadedCharacter.current = character;
    instance.current?.setAvatar(`${assetBase}/${character}.glb`).catch((error: Error) =>
      setWarning(`Gagal mengganti karakter: ${error.message}`));
  }, [character, ready, assetBase]);

  useEffect(() => {
    instance.current?.setStatus(toTalkingStatus(state));
  }, [state, ready]);

  return (
    <figure className="zoi-avatar3d zoi-state" data-state={state} data-ready={ready}
      style={{ width: size }} aria-label={`Avatar ZOI 3D: ${STATE_LABELS[state]}`} role="img">
      <div className="zoi-avatar3d-stage" style={{ width: size, height: size }}>
        <div ref={box} className="zoi-avatar3d-canvas" data-testid="avatar-3d-canvas" />
        <svg className="zoi-avatar3d-ring" viewBox="0 0 200 200" aria-hidden="true">
          <circle cx="100" cy="100" r="96" />
        </svg>
        {!ready && <span className="zoi-avatar3d-loading">Memuat avatar 3D…</span>}
      </div>
      <figcaption className="zoi-avatar-label">{STATE_LABELS[state]}</figcaption>
      {warning && <p className="zoi-avatar-note" role="status">{warning}</p>}
    </figure>
  );
}
