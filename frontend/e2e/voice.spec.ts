import { expect, type Page, test } from "@playwright/test";

const HEADERS = { "X-ZOI-Client": "web", "Content-Type": "application/json" };
const DEFAULT_VOICE = { language: "id", speak_replies: false, auto_send: false, tts_engine: "auto", browser_voice: null,
  speech_rate: 1, piper_license_accepted: false };
const isLocal = () => test.info().project.name.startsWith("local");

async function setVoice(page: Page, patch: Record<string, unknown>) {
  const res = await page.request.put("/api/voice/preferences", { headers: HEADERS, data: { ...DEFAULT_VOICE, ...patch } });
  expect(res.ok()).toBeTruthy();
}

async function setAvatar(page: Page, mode: "auto" | "2d" | "3d") {
  await page.request.put("/api/preferences", { headers: HEADERS,
    data: { ui_language: "id", avatar_mode_preference: mode, avatar_character: "female" } });
}

function watchExternal(page: Page): string[] {
  const external: string[] = [];
  page.on("request", (req) => {
    const url = new URL(req.url());
    if (["http:", "https:", "ws:", "wss:"].includes(url.protocol) && url.hostname !== "127.0.0.1") external.push(req.url());
  });
  return external;
}

test.afterEach(async ({ page }) => {
  await setVoice(page, {});
  await setAvatar(page, "auto");
});

test("development: bicara → transkrip MOCK masuk kotak pesan, tidak langsung dikirim", async ({ page }) => {
  test.skip(isLocal(), "khusus development");
  const external = watchExternal(page);
  await setAvatar(page, "2d");
  await page.goto("/ai");
  const mic = page.getByTestId("mic-button");
  await expect(mic).toBeEnabled();
  await mic.click();
  await expect(page.getByTestId("agent-reason")).toContainText("Mendengarkan");
  await page.waitForTimeout(600);
  await page.getByTestId("mic-finish").click();
  await expect(page.getByLabel("Pesan untuk ZOI")).toHaveValue(/\[MOCK\] transkrip suara tiruan/);
  await expect(page.getByTestId("msg-user")).toHaveCount(0);
  expect(external).toEqual([]);
});

test("development: jawaban dibacakan, Berhenti menghentikan suara", async ({ page }) => {
  test.skip(isLocal(), "khusus development");
  await setAvatar(page, "2d");
  await setVoice(page, { speak_replies: true });
  await page.goto("/ai");
  await expect(page.getByTestId("ws-status")).toHaveText("Tersambung", { timeout: 15_000 });
  await page.getByLabel("Pesan untuk ZOI").fill("halo ZOI");
  await page.getByRole("button", { name: "Kirim" }).click();
  await expect(page.getByTestId("agent-reason")).toHaveText("Membacakan jawaban", { timeout: 15_000 });
  await page.getByTestId("stop-button").click();
  await expect(page.getByTestId("agent-reason")).not.toHaveText("Membacakan jawaban");
  await expect(page.getByRole("button", { name: "Kirim" })).toBeVisible();
});

test("local: tanpa model Whisper tombol mikrofon mati dengan alasan", async ({ page }) => {
  test.skip(!isLocal(), "khusus local");
  await page.goto("/ai");
  const mic = page.getByTestId("mic-button");
  await expect(mic).toBeDisabled();
  await expect(mic).toHaveAttribute("title", /ZOI_WHISPER_MODEL_DIR/);
});

test("local: suara Piper butuh persetujuan lisensi, lalu avatar 3D lip-sync", async ({ page }) => {
  test.skip(test.info().project.name !== "local-desktop", "cukup sekali (3D berat di SwiftShader)");
  test.setTimeout(90_000);
  const external = watchExternal(page);
  await setAvatar(page, "3d");
  await page.goto("/settings/voice");
  await expect(page.getByTestId("piper-license")).toContainText("malayalam");
  await expect(page.getByTestId("reply-engine")).toContainText("Suara lokal");
  const blocked = await page.request.post("/api/voice/speak", { headers: HEADERS, data: { text: "Halo" } });
  expect(blocked.status()).toBe(400);

  await page.getByLabel(/pemakaian pribadi/).check();
  await page.getByRole("button", { name: "Simpan preferensi" }).click();
  await expect(page.getByTestId("reply-engine")).toContainText("Piper");
  await expect(page.locator(".zoi-avatar3d")).toHaveAttribute("data-ready", "true", { timeout: 45_000 });
  await page.getByRole("button", { name: "Coba suara" }).click();
  await expect(page.getByTestId("agent-reason")).toHaveText("Membacakan jawaban", { timeout: 15_000 });
  await expect(page.getByTestId("agent-reason")).not.toHaveText("Membacakan jawaban", { timeout: 30_000 });
  expect(external).toEqual([]);
});
