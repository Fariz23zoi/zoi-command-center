import { type APIRequestContext, expect, type Page, test } from "@playwright/test";

// Phase 6B. Proyek "local": Google/YouTube TIRUAN + Ollama TIRUAN. Proyek "development": Mock (berlabel).
const HEADERS = { "X-ZOI-Client": "web", "Content-Type": "application/json" };
const isLocal = () => test.info().project.name.startsWith("local");
const CLIENT = { installed: { client_id: "uji-e2e.apps.googleusercontent.com", client_secret: "rahasia-e2e" } };

async function noHorizontalOverflow(page: Page) {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(0);
}

async function reset(request: APIRequestContext) {
  await request.post("/api/youtube/disconnect", { headers: HEADERS });
  await request.delete("/api/youtube/client", { headers: HEADERS });
  for (const kind of ["ideas", "script"]) {
    const { items } = await (await request.get(`/api/content/items?kind=${kind}`)).json();
    for (const item of items) await request.delete(`/api/content/items/${item.id}`, { headers: HEADERS });
  }
}

/** Menghubungkan akun lewat Google tiruan tanpa UI (alur UI diuji di youtube.spec.ts). */
async function connect(request: APIRequestContext) {
  await request.put("/api/youtube/client", { headers: HEADERS, data: { config: CLIENT } });
  const started = await (await request.post("/api/youtube/connect", { headers: HEADERS })).json();
  await request.get(started.auth_url);
  await expect.poll(async () => (await (await request.get("/api/youtube/status")).json()).connected).toBe(true);
}

test.beforeEach(async ({ page }) => {
  await page.request.put("/api/preferences", { headers: HEADERS,
    data: { ui_language: "id", avatar_mode_preference: "2d", avatar_character: "female" } });
  await reset(page.request);
});

test.afterEach(async ({ page }) => {
  await reset(page.request);
  await page.request.put("/api/preferences", { headers: HEADERS,
    data: { ui_language: "id", avatar_mode_preference: "auto", avatar_character: "female" } });
});

test("belum terhubung: halaman data publik jujur dan tombolnya mati", async ({ page }) => {
  await page.goto("/competitors");
  await expect(page.getByTestId("public-not-connected")).toBeVisible();
  await expect(page.getByTestId("public-policy")).toContainText("30 hari");
  await expect(page.getByTestId("competitors-empty")).toBeVisible();
  await page.goto("/viral");
  await expect(page.getByTestId("trending-fetch")).toBeDisabled();
  await expect(page.getByTestId("viral-empty")).toBeVisible();
  await page.goto("/trends");
  await expect(page.getByTestId("trends-empty")).toBeVisible();
  await page.goto("/performance");
  await expect(page.getByTestId("youtube-not-connected")).toBeVisible();
  await noHorizontalOverflow(page);
});

test("Content Ideas → Script: draf AI berlabel, lalu dihapus", async ({ page }) => {
  await page.goto("/ideas");
  await expect(page.getByTestId("ws-status")).toHaveText("Tersambung", { timeout: 15_000 });
  if (isLocal()) await expect(page.getByTestId("content-mock-banner")).toHaveCount(0);
  else await expect(page.getByTestId("content-mock-banner")).toContainText("MOCK");
  await page.getByLabel("Topik atau arahan").fill("kopi rumahan untuk pemula");
  await page.getByLabel("Jumlah ide").selectOption("2");
  await page.getByRole("button", { name: "Susun ide" }).click();
  const set = page.getByTestId("idea-set").first();
  await expect(set).toContainText("kopi rumahan untuk pemula", { timeout: 20_000 });
  await expect(set.getByTestId("ai-stamp")).toContainText(isLocal() ? "Draf AI lokal (ollama" : "bukan hasil AI");
  if (!isLocal()) await expect(set.getByTestId("idea")).toHaveCount(2);
  await noHorizontalOverflow(page);

  await set.getByRole("link", { name: "Tulis naskah dari ide ini" }).first().click();
  await expect(page.getByTestId("script-page")).toBeVisible();
  await expect(page.getByLabel("Judul video")).not.toHaveValue("");
  await page.getByRole("button", { name: "Tulis naskah" }).click();
  const item = page.getByTestId("script-item").first();
  await expect(item).toBeVisible({ timeout: 20_000 });
  await item.locator("summary").click();
  await expect(item.getByTestId("storyboard").locator("tbody tr").first()).toBeVisible();
  const downloadPromise = page.waitForEvent("download");
  await item.getByRole("button", { name: "Unduh Markdown" }).click();
  expect((await downloadPromise).suggestedFilename()).toMatch(/^naskah-.+\.md$/);
  await noHorizontalOverflow(page);
  await item.getByRole("button", { name: "Hapus draf" }).click();
  await expect(page.getByTestId("scripts-empty")).toBeVisible();
});

test("kompetitor, Trending, pencarian, rangkuman tema, performa", async ({ page }) => {
  test.skip(!isLocal(), "Data publik diuji terhadap Google tiruan (hanya proyek local).");
  await connect(page.request);

  await page.goto("/competitors");
  await expect(page.getByTestId("ws-status")).toHaveText("Tersambung", { timeout: 15_000 });
  await expect(page.getByTestId("youtube-test-banner")).toContainText("ENDPOINT UJI");
  await page.getByLabel("Handle, ID, atau tautan channel").fill("https://www.youtube.com/@kopilain");
  await page.getByLabel("Catatanmu (opsional)").fill("pesaing kopi");
  await page.getByRole("button", { name: "Tambah channel" }).click();
  const competitor = page.getByTestId("competitor-item");
  await expect(competitor).toContainText("Kopi Lain · @kopilain");
  await expect(competitor).toContainText("12.400");
  await competitor.getByRole("button", { name: /Ambil data terbaru/ }).click();
  await expect(competitor.getByTestId("competitor-videos")).toContainText("Resep kopi susu gula aren");
  await expect(competitor.getByTestId("youtube-source")).toContainText("dihapus otomatis");
  await noHorizontalOverflow(page);

  await page.goto("/viral");
  await page.getByTestId("trending-fetch").click();
  const list = page.getByTestId("viral-list").first();
  await expect(list.locator("tbody tr").first()).toContainText("Cara seduh kopi V60 untuk pemula");
  await expect(list.locator("tbody tr").first()).toContainText("500.000");
  await expect(page.getByLabel("Kategori").locator("option")).toHaveCount(4);
  // Hitungan kuota bertahan antar-proyek (server yang sama) → bandingkan dengan nilai sebelumnya.
  const before = (await (await page.request.get("/api/youtube/public/viral")).json()).quota.search_used as number;
  await page.getByLabel("Kata kunci").fill("kopi");
  await page.getByRole("button", { name: "Cari di YouTube" }).click();
  await expect(page.getByTestId("viral-list")).toHaveCount(2);
  await expect(page.getByTestId("search-quota")).toContainText(`${before + 1} dari batas aman 90`);
  await noHorizontalOverflow(page);

  await page.getByTestId("viral-list").filter({ hasText: "Trending Indonesia" }).getByRole("link", { name: "Rangkum tema judul" }).click();
  await expect(page.getByTestId("themes-disclaimer")).toContainText("bukan statistik");
  await page.getByTestId("themes-start").click();
  const entry = page.getByTestId("themes-entry");
  await expect(entry).toBeVisible({ timeout: 20_000 });
  await expect(entry).toContainText("Interpretasi AI atas judul");
  await expect(entry.getByTestId("ai-stamp")).toContainText("Draf AI lokal (ollama");
  // Ollama tiruan mengembalikan contoh judul yang tidak ada di daftar → dibuang, dan itu disebutkan.
  await expect(entry).toContainText("dibuang karena tidak ada di daftar");
  await noHorizontalOverflow(page);

  await page.goto("/performance");
  await page.getByTestId("youtube-refresh").click();
  const table = page.getByTestId("performance-table");
  await expect(table).toContainText("Video uji pertama", { timeout: 15_000 });
  await expect(table).toContainText("42,5");
  await expect(table).toContainText("ID vidHAPUS0001");
  await expect(page.getByTestId("upload-time-note")).toBeVisible();
  await noHorizontalOverflow(page);

  // Memutuskan akun menghapus data publik dan daftar pantauan.
  await page.request.post("/api/youtube/disconnect", { headers: HEADERS });
  await page.goto("/competitors");
  await expect(page.getByTestId("competitors-empty")).toBeVisible();
});
