import { expect, type Page, test } from "@playwright/test";

const HEADERS = { "X-ZOI-Client": "web" };
const isLocal = () => test.info().project.name.startsWith("local");

async function noHorizontalOverflow(page: Page) {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(0);
}

test.afterEach(async ({ page }) => {
  if (isLocal()) await page.request.delete("/api/ai/active-model", { headers: HEADERS });
});

test("AI Lokal di development: jujur memakai Mock, tanpa model", async ({ page }) => {
  test.skip(isLocal(), "khusus development");
  await page.goto("/settings");
  await page.getByTestId("ai-local-link").click();
  await expect(page.getByTestId("ai-status-detail")).toContainText("Mock Provider");
  await expect(page.getByTestId("installed-models")).toHaveCount(0);
  await expect(page.getByTestId("catalog")).toContainText("ollama pull qwen3:0.6b");
  await noHorizontalOverflow(page);
});

test("AI Lokal di local: model dari Ollama, pilih model aktif, model cloud ditolak", async ({ page }) => {
  test.skip(!isLocal(), "khusus local");
  await page.goto("/settings/ai");
  await expect(page.getByTestId("ai-status")).toContainText("0.0.0-tiruan");
  await expect(page.getByTestId("active-model")).toContainText("qwen3:4b");
  const models = page.getByTestId("installed-model");
  await expect(models).toHaveCount(4);
  const cloud = models.filter({ hasText: "uji-awan:cloud" });
  await expect(cloud).toContainText("cloud — tidak diizinkan");
  await expect(cloud.getByRole("button")).toHaveCount(0);

  await models.filter({ hasText: "uji-embed:latest" }).getByRole("button", { name: "Jadikan model aktif" }).click();
  await expect(page.getByTestId("ai-notice")).toContainText("tidak bisa dipakai untuk percakapan");

  await models.filter({ hasText: "uji-kecil:1b" }).getByRole("button", { name: "Jadikan model aktif" }).click();
  await expect(page.getByTestId("ai-notice")).toContainText("Model aktif sekarang uji-kecil:1b");
  await expect(page.getByTestId("active-model")).toContainText("dipilih di halaman ini");

  await page.getByRole("button", { name: /Kembali ke model .env/ }).click();
  await expect(page.getByTestId("active-model")).toContainText("qwen3:4b");
  await page.getByRole("button", { name: "Uji koneksi" }).click();
  await expect(page.getByTestId("ai-notice")).toContainText("menjawab");
  await noHorizontalOverflow(page);
});

test("tombol Berhenti menghentikan jawaban yang sedang ditulis", async ({ page }) => {
  test.skip(!isLocal(), "khusus local (Ollama tiruan yang lambat)");
  await page.goto("/");
  await expect(page.getByTestId("ws-status")).toHaveText("Tersambung", { timeout: 15_000 });
  await page.getByLabel("Pesan untuk ZOI").fill("ceritakan panjang /uji-lambat");
  await page.getByRole("button", { name: "Kirim" }).click();
  await expect(page.getByTestId("msg-assistant").last()).toContainText("kata3");
  await page.getByTestId("stop-button").click();
  const reply = page.getByTestId("msg-assistant").last();
  await expect(reply.getByTestId("stopped-badge")).toBeVisible();
  await expect(reply).not.toContainText("kata199");
  await expect(page.getByRole("button", { name: "Kirim" })).toBeVisible();
});

test("uji model: hasil nyata tersimpan dan jawaban bisa dinilai", async ({ page }) => {
  test.skip(test.info().project.name !== "local-desktop", "cukup sekali");
  test.setTimeout(60_000);
  await page.goto("/settings/ai");
  await page.getByTestId("installed-model").filter({ hasText: "uji-kecil:1b" })
    .getByRole("button", { name: "Uji model" }).click();
  const results = page.getByTestId("evaluations").locator("li.model-item").filter({ hasText: "uji-kecil:1b" }).first();
  await expect(results).toContainText("JSON 5/5", { timeout: 45_000 });
  await results.getByRole("button", { name: "Lihat jawaban" }).click();
  await results.getByRole("button", { name: "Bagus: c01" }).click();
  await expect(results).toContainText("👍 1");
  await noHorizontalOverflow(page);
});
