import { expect, type Page, test } from "@playwright/test";

const HEADERS = { "X-ZOI-Client": "web", "Content-Type": "application/json" };
const isLocal = () => test.info().project.name.startsWith("local");

async function noHorizontalOverflow(page: Page) {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(0);
}

async function plan(page: Page, text: string) {
  await page.goto("/");
  await expect(page.getByTestId("ws-status")).toHaveText("Tersambung", { timeout: 15_000 });
  await page.getByLabel("Pesan untuk ZOI").fill(text);
  await page.getByTestId("plan-button").click();
  return page.getByTestId("agent-card").last();
}

test.beforeEach(async ({ page }) => {
  await page.request.put("/api/preferences", { headers: HEADERS,
    data: { ui_language: "id", avatar_mode_preference: "2d", avatar_character: "female" } });
});

test.afterEach(async ({ page }) => {
  await page.request.delete("/api/memories?confirm=HAPUS%20SEMUA", { headers: HEADERS });
  await page.request.put("/api/preferences", { headers: HEADERS,
    data: { ui_language: "id", avatar_mode_preference: "auto", avatar_character: "female" } });
});

test("Memory: tambah, cari, ubah, hapus", async ({ page }) => {
  await page.goto("/memory");
  await page.getByLabel("Isi").fill("Channel fokus ke resep kopi nusantara");
  await page.getByRole("button", { name: "Simpan memori" }).click();
  const item = page.getByTestId("memory-item").filter({ hasText: "kopi nusantara" });
  await expect(item).toContainText("dari kamu");
  await page.getByLabel("Cari memori").fill("resep");
  await expect(page.getByTestId("memory-item")).toHaveCount(1);
  await page.getByLabel("Cari memori").fill("tidakada");
  await expect(page.getByText("Tidak ada memori yang cocok.")).toBeVisible();
  await page.getByLabel("Cari memori").fill("");
  await item.getByRole("button", { name: "Ubah" }).click();
  await page.getByLabel("Ubah isi").fill("Channel fokus ke teh tradisional");
  await page.getByRole("button", { name: "Simpan perubahan" }).click();
  await expect(page.getByTestId("memory-item").first()).toContainText("teh tradisional");
  await page.getByRole("button", { name: /^Hapus memori:/ }).click();
  await expect(page.getByText("Belum ada memori.")).toBeVisible();
  await noHorizontalOverflow(page);
});

test("development: rencana MOCK → jalankan → izin → memori tersimpan", async ({ page }) => {
  test.skip(isLocal(), "khusus development");
  const card = await plan(page, "tolong catat sesuatu di memori");
  await expect(card).toHaveAttribute("data-status", "planned", { timeout: 15_000 });
  await expect(card.getByTestId("agent-step")).toHaveCount(2);
  await expect(card).toContainText("ubah data — perlu izin");
  await noHorizontalOverflow(page);

  await card.getByRole("button", { name: "Jalankan rencana" }).click();
  await expect(card.getByTestId("agent-approval")).toContainText("simpan_memori", { timeout: 15_000 });
  await expect(page.getByTestId("agent-reason")).toContainText("Menunggu izin");
  await card.getByRole("button", { name: "Setujui" }).click();
  await expect(card).toHaveAttribute("data-status", "completed", { timeout: 15_000 });
  await expect(page.getByTestId("msg-assistant").last()).toContainText("[MOCK] Ringkasan tiruan");

  await page.goto("/memory");
  await expect(page.getByTestId("memory-item").first()).toContainText("disimpan agen");
  await expect(page.getByTestId("approval-log")).toContainText("disetujui");
});

test("development: /agen dengan tool terlarang ditolak jujur, tidak bisa dijalankan", async ({ page }) => {
  test.skip(isLocal(), "khusus development");
  await page.goto("/");
  await expect(page.getByTestId("ws-status")).toHaveText("Tersambung", { timeout: 15_000 });
  await page.getByLabel("Pesan untuk ZOI").fill("/agen unggah video /uji-rencana-rusak");
  await page.getByRole("button", { name: "Kirim" }).click();
  const card = page.getByTestId("agent-card").last();
  await expect(card).toHaveAttribute("data-status", "invalid", { timeout: 15_000 });
  await expect(card.getByRole("alert")).toContainText("unggah_video");
  await expect(card.getByRole("button", { name: "Jalankan rencana" })).toHaveCount(0);
});

test("local: rencana dari Ollama tiruan, izin ditolak menghentikan langkah", async ({ page }) => {
  test.skip(test.info().project.name !== "local-desktop", "cukup sekali");
  const card = await plan(page, "cek jam lalu catat");
  await expect(card).toHaveAttribute("data-status", "planned", { timeout: 15_000 });
  await expect(card.getByTestId("mock-badge")).toHaveCount(0);
  await card.getByRole("button", { name: "Jalankan rencana" }).click();
  await expect(card.getByTestId("agent-approval")).toBeVisible({ timeout: 15_000 });
  await card.getByRole("button", { name: "Tolak" }).click();
  await expect(card).toHaveAttribute("data-status", "stopped", { timeout: 15_000 });
  await expect(card).toContainText("Izin ditolak");
  const memories = await (await page.request.get("/api/memories")).json();
  expect(memories.total).toBe(0);
});
