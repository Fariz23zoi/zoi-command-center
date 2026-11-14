import { afterEach, describe, expect, it, vi } from "vitest";

import { localVoices, pickVoice } from "./browserVoices";
import { ReplyReader } from "./replyReader";
import { MAX_CHUNK, SentenceSplitter, speakable } from "./sentences";

describe("SentenceSplitter", () => {
  it("memotong per kalimat walau datang bertahap", () => {
    const s = new SentenceSplitter();
    expect(s.feed("Halo, saya ZO")).toEqual([]);
    expect(s.feed("I. Apa kabar")).toEqual(["Halo, saya ZOI."]);
    expect(s.feed("? Baik")).toEqual(["Apa kabar?"]);
    expect(s.flush()).toEqual(["Baik"]);
  });

  it("menunggu tanda baca di ujung (bisa jadi angka desimal)", () => {
    const s = new SentenceSplitter();
    expect(s.feed("Versi 3.")).toEqual([]);
    expect(s.feed("5 sudah rilis. ")).toEqual(["Versi 3.5 sudah rilis."]);
  });

  it("kalimat sangat panjang dipotong di koma/spasi", () => {
    const parts = new SentenceSplitter().feed(`${"kata ".repeat(120)}`);
    expect(parts.length).toBeGreaterThan(0);
    expect(parts.every((p) => p.length <= MAX_CHUNK)).toBe(true);
  });

  it("label MOCK dan markdown tidak dibacakan", () => {
    expect(speakable("[MOCK] **Halo** `ZOI`")).toBe("Halo ZOI");
  });
});

describe("suara lokal browser", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("hanya suara localService, Bahasa Indonesia lebih dulu; suara cloud tidak pernah muncul", () => {
    const voices = [
      { name: "Microsoft Ardi Online (Natural)", lang: "id-ID", localService: false },
      { name: "Microsoft David", lang: "en-US", localService: true },
      { name: "Microsoft Andika", lang: "id-ID", localService: true },
    ];
    vi.stubGlobal("speechSynthesis", { getVoices: () => voices });
    vi.stubGlobal("SpeechSynthesisUtterance", class {});
    expect(localVoices().map((v) => v.name)).toEqual(["Microsoft Andika", "Microsoft David"]);
    expect(pickVoice(null, "id")?.name).toBe("Microsoft Andika");
    expect(pickVoice("Microsoft Ardi Online (Natural)", "id")?.name).toBe("Microsoft Andika");
  });
});

describe("ReplyReader", () => {
  const tick = () => new Promise((r) => setTimeout(r, 0));

  it("membacakan berurutan, menyiapkan audio berikutnya lebih dulu, lalu selesai", async () => {
    const played: string[] = [];
    const fetched: string[] = [];
    const speaking: boolean[] = [];
    const reader = new ReplyReader({
      fetchAudio: async (text) => { fetched.push(text); return new Blob([text]); },
      playAudio: async (blob) => { played.push(await blob.text()); },
      onSpeaking: (v) => speaking.push(v),
      onError: () => undefined,
    });
    reader.feed("Satu. Dua. ");
    reader.feed("Tiga");
    reader.finish();
    for (let i = 0; i < 10; i += 1) await tick();
    expect(played).toEqual(["Satu.", "Dua.", "Tiga"]);
    expect(fetched).toEqual(["Satu.", "Dua.", "Tiga"]);
    expect(speaking.at(0)).toBe(true);
    expect(speaking.at(-1)).toBe(false);
  });

  it("stop() membatalkan permintaan dan pemutaran seketika", async () => {
    let aborted = false;
    const reader = new ReplyReader({
      fetchAudio: (_t, signal) => new Promise((_, reject) => signal.addEventListener("abort", () => { aborted = true; reject(new Error("abort")); })),
      playAudio: async () => undefined,
      onSpeaking: () => undefined,
      onError: () => { throw new Error("tidak boleh melapor error saat dihentikan"); },
    });
    reader.feed("Kalimat panjang sekali. ");
    await tick();
    reader.stop();
    await tick();
    expect(aborted).toBe(true);
    expect(reader.active).toBe(false);
  });

  it("kegagalan suara dilaporkan, bukan didiamkan", async () => {
    const errors: string[] = [];
    const reader = new ReplyReader({
      speakText: async () => { throw new Error("Tidak ada suara lokal"); },
      onSpeaking: () => undefined,
      onError: (m) => errors.push(m),
    });
    reader.feed("Halo. ");
    for (let i = 0; i < 5; i += 1) await tick();
    expect(errors).toEqual(["Tidak ada suara lokal"]);
  });
});
