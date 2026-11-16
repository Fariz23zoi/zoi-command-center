import { expect, type Page, test } from "@playwright/test";

const HEADERS = { "X-ZOI-Client": "web", "Content-Type": "application/json" };

async function setAvatarPref(page: Page, mode: "auto" | "2d" | "3d", character: "female" | "male" = "female") {
  const res = await page.request.put("/api/preferences", {
    headers: HEADERS,
    data: { ui_language: "id", avatar_mode_preference: mode, avatar_character: character },
  });
  expect(res.ok()).toBeTruthy();
}

/** WAV mono 16 kHz berisi nada naik-turun selama ±1,2 detik — dibuat di tes, tidak diunduh. */
function wav(): Buffer {
  const rate = 16_000;
  const n = Math.round(rate * 1.2);
  const buf = Buffer.alloc(44 + n * 2);
  buf.write("RIFF", 0); buf.writeUInt32LE(36 + n * 2, 4); buf.write("WAVEfmt ", 8);
  buf.writeUInt32LE(16, 16); buf.writeUInt16LE(1, 20); buf.writeUInt16LE(1, 22);
  buf.writeUInt32LE(rate, 24); buf.writeUInt32LE(rate * 2, 28); buf.writeUInt16LE(2, 32); buf.writeUInt16LE(16, 34);
  buf.write("data", 36); buf.writeUInt32LE(n * 2, 40);
  for (let i = 0; i < n; i++) {
    const env = Math.abs(Math.sin((i / rate) * Math.PI * 3));
    buf.writeInt16LE(Math.round(Math.sin((2 * Math.PI * 220 * i) / rate) * env * 12_000), 44 + i * 2);
  }
  return buf;
}

test.afterEach(async ({ page }) => { await setAvatarPref(page, "auto"); });

test("avatar 3D: aset lokal, tanpa permintaan keluar, lip-sync dari file perangkat", async ({ page }) => {
  test.setTimeout(60_000);
  const external: string[] = [];
  const base = new URL(test.info().project.use.baseURL!);
  page.on("request", (req) => {
    const url = new URL(req.url());
    if (["http:", "https:", "ws:", "wss:"].includes(url.protocol) && url.hostname !== base.hostname) external.push(req.url());
  });
  const consoleErrors: string[] = [];
  page.on("console", (msg) => { if (msg.type() === "error") consoleErrors.push(msg.text()); });

  await setAvatarPref(page, "3d", "male");
  await page.goto("/settings");
  await expect(page.getByTestId("avatar-renderer")).toHaveText("3d");
  const canvas = page.getByTestId("avatar-3d-canvas").locator("canvas");
  await expect(canvas).toHaveCount(1);
  await expect(page.locator(".zoi-avatar3d")).toHaveAttribute("data-ready", "true", { timeout: 30_000 });

  await page.getByLabel(/Uji lip-sync/).setInputFiles({ name: "uji.wav", mimeType: "audio/wav", buffer: wav() });
  await expect(page.getByTestId("lipsync-status")).toHaveText('Selesai memutar "uji.wav".', { timeout: 20_000 });

  expect(external).toEqual([]);
  expect(consoleErrors.filter((e) => /Content Security Policy|Refused/.test(e))).toEqual([]);
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(0);
});

test("preferensi 2D: tidak ada kanvas WebGL sama sekali", async ({ page }) => {
  await setAvatarPref(page, "2d");
  await page.goto("/settings");
  await expect(page.getByTestId("avatar-renderer")).toHaveText("2d");
  await expect(page.locator("canvas")).toHaveCount(0);
});
