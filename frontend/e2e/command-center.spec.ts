import { expect, type Page, test } from "@playwright/test";

const isLocal = () => test.info().project.name.startsWith("local");

async function expectNoHorizontalOverflow(page: Page) {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(0);
}

async function send(page: Page, text: string) {
  await page.getByLabel("Pesan untuk ZOI").fill(text);
  await page.getByRole("button", { name: "Kirim" }).click();
}

test("command center terbuka, tersambung, tanpa geser horizontal", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByTestId("ws-status")).toHaveText("Tersambung", { timeout: 15_000 });
  await expect(page.getByRole("img", { name: /Avatar ZOI/ })).toBeVisible();
  if (isLocal()) {
    await expect(page.getByTestId("dev-banner")).toHaveCount(0);
  } else {
    await expect(page.getByTestId("dev-banner")).toContainText("MOCK");
  }
  await expectNoHorizontalOverflow(page);
});

test("chat: development memakai mock berlabel, local tidak pernah mock", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByTestId("ws-status")).toHaveText("Tersambung", { timeout: 15_000 });
  await send(page, "halo ZOI");
  const reply = page.getByTestId("msg-assistant").last();
  if (isLocal()) {
    // Ollama TIRUAN: jalur sukses + proses berpikir terpisah, tanpa lencana MOCK.
    await expect(reply).toContainText("Jawaban dari model lokal.", { timeout: 10_000 });
    await expect(reply.getByTestId("msg-thinking")).toContainText("Menimbang jawaban.");
    await expect(page.getByTestId("mock-badge")).toHaveCount(0);
    // Jalur gagal yang cepat (error tiba sebelum respons POST) tetap tampil.
    await send(page, "/uji-error");
    await expect(page.getByTestId("msg-assistant").last().getByRole("alert")).toContainText("Ollama menolak permintaan");
  } else {
    await expect(reply.getByTestId("mock-badge")).toBeVisible({ timeout: 10_000 });
    await expect(reply).toContainText("[MOCK] Halo!", { timeout: 10_000 });
  }
  await expectNoHorizontalOverflow(page);
});

test("task manager: pemeriksaan sistem berjalan sampai selesai", async ({ page }) => {
  await page.goto("/tasks");
  await expect(page.getByTestId("ws-status")).toHaveText("Tersambung", { timeout: 15_000 });
  await page.getByRole("button", { name: "Jalankan pemeriksaan sistem" }).click();
  await expect(page.getByTestId("task-status").first()).toHaveText("Selesai", { timeout: 20_000 });
  await expectNoHorizontalOverflow(page);
});

test("CLIPPER yang ditunda dijelaskan jujur, tanpa angka", async ({ page }) => {
  await page.goto("/clipper");
  const box = page.getByTestId("not-yet-available");
  await expect(box).toContainText("Ditunda");
  await expect(box).toContainText("yt-dlp");
  expect((await box.textContent())!.replace(/Phase \d+/g, "")).not.toMatch(/\d/);
});

test("content production: impor paket lalu tampil dengan tautan Blueprint", async ({ page }) => {
  await page.goto("/production");
  await expect(page.getByTestId("production-readiness")).toBeVisible();
  const paket = { format: "zoi.paket/v1", judul: "Paket uji E2E", topik: "Uji", durasi: "30 detik",
    bahasa: "Indonesia", rasio: "9:16", mock: true, beats: [{ k: "Hook", n: "Halo dari uji.", v: "" }] };
  await page.getByTestId("production-import").setInputFiles({ name: "paket-zoi-uji.json",
    mimeType: "application/json", buffer: Buffer.from(JSON.stringify(paket)) });
  const item = page.getByTestId("production-item").filter({ hasText: "Paket uji E2E" }).first();
  await expect(item).toBeVisible({ timeout: 15_000 });
  await expect(item.getByTestId("production-blueprint")).toHaveAttribute("href", /\/blueprint-studio\/\?paket=/);
  await expectNoHorizontalOverflow(page);
});

test("navigasi mobile lewat drawer", async ({ page }) => {
  test.skip(!test.info().project.name.endsWith("mobile"), "khusus viewport HP");
  await page.goto("/");
  await page.getByRole("button", { name: "Buka menu" }).click();
  await page.getByRole("link", { name: "Settings" }).click();
  await expect(page.getByRole("heading", { name: "Settings" })).toBeVisible({ timeout: 15_000 });
  await expectNoHorizontalOverflow(page);
});

test("automation: pengingat dijalankan manual lalu muncul sebagai notifikasi", async ({ page }) => {
  await page.goto("/automation");
  await expect(page.getByTestId("ws-status")).toHaveText("Tersambung", { timeout: 15_000 });
  const text = `Pengingat E2E ${test.info().project.name} ${Date.now()}`;
  await page.getByTestId("automation-kind").selectOption("pengingat_produksi");
  await page.getByTestId("automation-text").fill(text);
  await page.getByTestId("automation-create").click();
  const item = page.getByTestId("automation-item").filter({ hasText: text });
  await expect(item).toBeVisible({ timeout: 15_000 });
  await item.getByTestId("automation-run").click();
  await expect(page.getByTestId("notifications")).toContainText("Pengingat:", { timeout: 15_000 });
  await expect(item.getByTestId("automation-last")).toContainText("Selesai", { timeout: 15_000 });
  await expectNoHorizontalOverflow(page);
});
