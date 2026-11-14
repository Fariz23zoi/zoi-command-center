import { afterEach, describe, expect, it, vi } from "vitest";

import { clearCachedFps, measureFps, readCachedFps, storeCachedFps } from "./benchmark";
import { detectCapabilities } from "./capabilities";
import { AGENT_STATES } from "./states";
import { toTalkingStatus } from "./stateMap";

describe("toTalkingStatus", () => {
  it("status kerja → thinking, sisanya → listening", () => {
    const thinking = AGENT_STATES.filter((s) => toTalkingStatus(s) === "thinking");
    expect(thinking.sort()).toEqual(["ANALYZING", "CREATING", "EXECUTING", "PLANNING", "RESEARCHING", "THINKING"]);
    expect(toTalkingStatus("IDLE")).toBe("listening");
    expect(toTalkingStatus("SPEAKING")).toBe("listening");
  });
});

describe("measureFps", () => {
  it("menghitung frame per detik dari raf dan jam palsu", async () => {
    let t = 0;
    const raf = (cb: (t: number) => void) => { t += 50; queueMicrotask(() => cb(t)); return 0; }; // 20 fps
    const fps = await measureFps(1000, raf, () => t);
    expect(fps).toBeCloseTo(20, 0);
  });
});

describe("cache FPS", () => {
  afterEach(() => { clearCachedFps(); vi.restoreAllMocks(); });

  it("disimpan, dibaca, dan dihapus", () => {
    expect(readCachedFps()).toBeNull();
    storeCachedFps(14.26);
    expect(readCachedFps()).toBe(14.3);
    clearCachedFps();
    expect(readCachedFps()).toBeNull();
  });

  it("penyimpanan browser yang diblokir tidak membuat crash", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => { throw new Error("blocked"); });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("blocked"); });
    expect(() => storeCachedFps(30)).not.toThrow();
    expect(readCachedFps()).toBeNull();
  });
});

describe("detectCapabilities", () => {
  afterEach(() => vi.restoreAllMocks());

  it("jsdom tanpa WebGL 2 → tidak ok, dengan alasan", () => {
    const caps = detectCapabilities();
    expect(caps.ok).toBe(false);
    expect(caps.webgl2).toBe(false);
    expect(caps.reason).toMatch(/WebGL 2/);
  });

  it("WebGL 2 + AudioWorklet tersedia → ok", () => {
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue({ getExtension: () => null } as never);
    class FakeCtx { audioWorklet = {}; }
    Object.defineProperty(FakeCtx.prototype, "audioWorklet", { value: {} });
    vi.stubGlobal("AudioContext", FakeCtx);
    try {
      expect(detectCapabilities()).toEqual({ ok: true, webgl2: true, audioWorklet: true, reason: null });
    } finally {
      vi.unstubAllGlobals();
    }
  });
});
