import { expect, test } from "@playwright/test";

// AI cloud tidak diaktifkan di kedua proyek E2E (.env bawaan). Alur chat lewat cloud diuji di backend (pytest)
// terhadap server tiruan; di sini: halaman Settings › AI Cloud dan penyimpanan API key.
const HEADERS = { "X-ZOI-Client": "web", "Content-Type": "application/json" };
const KEY = "nvapi-" + "e".repeat(30);

// Avatar 2D: WebGL perangkat lunak di mesin uji bisa membekukan halaman saat memuat avatar 3D.
// Preferensi dikembalikan persis seperti sebelum tes agar spec lain tidak terpengaruh.
let before: Record<string, unknown> | null = null;

test.beforeEach(async ({ page }) => {
  before = await (await page.request.get("/api/preferences")).json();
  await page.request.put("/api/preferences", { headers: HEADERS,
    data: { ui_language: "id", avatar_mode_preference: "2d", avatar_character: "female" } });
});

test.afterEach(async ({ page }) => {
  await page.request.delete("/api/ai/cloud/keys/nvidia", { headers: HEADERS });
  if (before) {
    await page.request.put("/api/preferences", { headers: HEADERS, data: {
      ui_language: before.ui_language, avatar_mode_preference: before.avatar_mode_preference,
      avatar_character: before.avatar_character } });
  }
});

test("AI Cloud: bawaan tidak aktif; API key disimpan tanpa pernah ditampilkan", async ({ page }) => {
  await page.goto("/settings");
  await page.getByTestId("ai-cloud-link").click();
  await expect(page.getByTestId("cloud-state")).toContainText("TIDAK aktif", { timeout: 15_000 });
  await expect(page.getByTestId("cloud-howto")).toContainText("ZOI_AI_PROVIDER=nvidia");
  await expect(page.getByTestId("cloud-test-banner")).toHaveCount(0);
  const card = page.getByTestId("cloud-nvidia");
  await expect(card.getByTestId("cloud-nvidia-key")).toHaveText("belum dimasukkan");

  await card.getByLabel(/API key/).fill("salah-format-tetapi-cukup-panjang");
  await card.getByRole("button", { name: "Simpan API key" }).click();
  await expect(page.getByTestId("cloud-notice")).toContainText("nvapi-");

  await card.getByLabel(/API key/).fill(KEY);
  await card.getByRole("button", { name: "Simpan API key" }).click();
  await expect(card.getByTestId("cloud-nvidia-key")).toHaveText("tersimpan (tidak ditampilkan)");
  expect(await page.content()).not.toContain(KEY);
  expect(JSON.stringify(await (await page.request.get("/api/ai/cloud/status")).json())).not.toContain(KEY);
  await expect(card.getByTestId("cloud-nvidia-test")).toHaveCount(0); // tidak dipakai di .env → tidak bisa diuji

  await card.getByRole("button", { name: "Hapus API key" }).click();
  await expect(card.getByTestId("cloud-nvidia-key")).toHaveText("belum dimasukkan");
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(0);
});

test("host AI cloud tetap diblokir bila tidak dipilih di .env", async ({ page }) => {
  const status = await (await page.request.get("/api/ai/cloud/status")).json();
  expect(status.enabled).toBe(false);
  const config = await (await page.request.get("/api/config")).json();
  expect(config.is_cloud).toBe(false);
});
