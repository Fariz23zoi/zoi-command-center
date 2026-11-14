/** Uji FPS: menghitung frame requestAnimationFrame selama avatar 3D berjalan. Hasil disimpan per browser. */
export const MIN_FPS = 20;
export const BENCHMARK_MS = 5000;
const STORAGE_KEY = "zoi.avatar.fps.v1";

type Raf = (cb: (t: number) => void) => number;

export function measureFps(
  durationMs = BENCHMARK_MS,
  raf: Raf = (cb) => requestAnimationFrame(cb),
  now: () => number = () => performance.now(),
): Promise<number> {
  return new Promise((resolve) => {
    const start = now();
    let frames = 0;
    const step = () => {
      frames += 1;
      const elapsed = now() - start;
      if (elapsed >= durationMs) resolve((frames / elapsed) * 1000);
      else raf(step);
    };
    raf(step);
  });
}

/** Penyimpanan browser bisa tidak tersedia/dibatasi — selalu dibungkus try/catch. */
export function readCachedFps(): number | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    const value = raw === null ? NaN : Number(raw);
    return Number.isFinite(value) ? value : null;
  } catch {
    return null;
  }
}

export function storeCachedFps(fps: number): void {
  try { localStorage.setItem(STORAGE_KEY, fps.toFixed(1)); } catch { /* abaikan */ }
}

export function clearCachedFps(): void {
  try { localStorage.removeItem(STORAGE_KEY); } catch { /* abaikan */ }
}
