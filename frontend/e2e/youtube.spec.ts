import { expect, type Page, test } from "@playwright/test";

// Phase 6A. Proyek "local" memakai Google/YouTube TIRUAN (ZOI_YOUTUBE_TEST_URL) — tidak ada panggilan ke Google.
const HEADERS = { "X-ZOI-Client": "web", "Content-Type": "application/json" };
const isLocal = () => test.info().project.name.startsWith("local");
const CLIENT = JSON.stringify({ installed: { client_id: "uji-e2e.apps.googleusercontent.com", client_secret: "rahasia-e2e" } });

async function noHorizontalOverflow(page: Page) {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(0);
}

async function reset(page: Page) {
  await page.request.post("/api/youtube/disconnect", { headers: HEADERS });
  await page.request.delete("/api/youtube/client", { headers: HEADERS });
}

test.beforeEach(async ({ page }) => {
  await page.request.put("/api/preferences", { headers: HEADERS,
    data: { ui_language: "id", avatar_mode_preference: "2d", avatar_character: "female" } });
  await reset(page);
});

test.afterEach(async ({ page }) => {
  await reset(page);
  await page.request.put("/api/preferences", { headers: HEADERS,
    data: { ui_language: "id", avatar_mode_preference: "auto", avatar_character: "female" } });
});

test("belum terhubung: Analytics & Monetization tanpa angka channel", async ({ page }) => {
  await page.goto("/analytics");
  const box = page.getByTestId("youtube-not-connected");
  await expect(box).toContainText("belum terhubung");
  expect((await box.textContent())!).not.toMatch(/\d/);
  await page.goto("/monetization");
  await expect(page.getByTestId("youtube-not-connected")).toBeVisible();
  await expect(page.getByTestId("ypp-tier").first()).toContainText("500 subscriber");
  await expect(page.getByTestId("ypp-channel-numbers")).toHaveCount(0);
  await noHorizontalOverflow(page);
});

test("Settings › YouTube: penjelasan jujur; file client bertipe Web ditolak", async ({ page }) => {
  await page.goto("/settings");
  await page.getByTestId("youtube-link").click();
  await expect(page.getByTestId("youtube-settings")).toContainText("tidak pernah melihat atau meminta password");
  await expect(page.getByTestId("youtube-connect")).toBeDisabled();
  if (isLocal()) await expect(page.getByTestId("youtube-test-banner")).toContainText("ENDPOINT UJI");
  else await expect(page.getByTestId("youtube-test-banner")).toHaveCount(0);
  await page.getByTestId("youtube-client-file").setInputFiles({ name: "web.json", mimeType: "application/json",
    buffer: Buffer.from(JSON.stringify({ web: { client_id: "a", client_secret: "b" } })) });
  await expect(page.getByTestId("youtube-notice")).toContainText("Desktop app");
  await expect(page.getByTestId("youtube-connect")).toBeDisabled();
  await noHorizontalOverflow(page);
});

test("hubungkan lewat halaman izin, ambil data, lalu putuskan & hapus", async ({ page, context }) => {
  test.skip(!isLocal(), "Alur OAuth diuji terhadap Google tiruan (hanya proyek local).");
  await page.goto("/settings/youtube");
  await expect(page.getByTestId("ws-status")).toHaveText("Tersambung", { timeout: 15_000 });
  await page.getByTestId("youtube-client-file").setInputFiles({ name: "client.json", mimeType: "application/json",
    buffer: Buffer.from(CLIENT) });
  await expect(page.getByTestId("youtube-client")).toContainText("apps.googleusercontent.com");
  expect(await page.content()).not.toContain("rahasia-e2e");

  const popupPromise = context.waitForEvent("page");
  await page.getByTestId("youtube-connect").click();
  const popup = await popupPromise;
  await expect(popup.getByText("Tab ini boleh ditutup")).toBeVisible({ timeout: 15_000 });
  expect(new URL(popup.url()).hostname).toBe("127.0.0.1");
  await popup.close();

  await expect(page.getByTestId("youtube-account")).toContainText("Channel Uji ZOI", { timeout: 15_000 });
  await expect(page.getByTestId("youtube-storage")).toBeVisible();

  await page.goto("/analytics");
  await expect(page.getByTestId("youtube-test-banner")).toContainText("ENDPOINT UJI");
  await page.getByTestId("youtube-refresh").click();
  await expect(page.getByTestId("channel-stats")).toContainText("1.530", { timeout: 15_000 });
  await expect(page.getByTestId("channel-stats")).toContainText("45.210");
  await expect(page.getByTestId("report-28")).toContainText("3.080");
  await expect(page.getByTestId("video-table")).toContainText("Video uji pertama");
  await expect(page.getByTestId("history-table").locator("tbody tr")).toHaveCount(1);
  await expect(page.getByTestId("youtube-source").first()).toContainText("SERVER UJI");
  expect(await page.locator("progress, meter").count()).toBe(0);
  await noHorizontalOverflow(page);

  await page.goto("/monetization");
  await expect(page.getByTestId("ypp-channel-numbers")).toContainText("1.530");
  await expect(page.getByTestId("ypp-channel-numbers")).toContainText("120.450 menit");
  await expect(page.getByTestId("ypp-disclaimer")).toContainText("YouTube Studio");
  await noHorizontalOverflow(page);

  await page.goto("/settings/youtube");
  await page.getByTestId("youtube-disconnect").click();
  await page.getByRole("button", { name: "Ya, putuskan dan hapus" }).click();
  await expect(page.getByTestId("youtube-notice")).toContainText("Token dicabut di Google");
  await expect(page.getByTestId("youtube-connect")).toBeEnabled();
  const data = await (await page.request.get("/api/youtube/data")).json();
  expect(data.connected).toBe(false);
  expect(data.channel).toBeNull();
  expect(data.history).toEqual([]);
});

test("menolak izin di halaman Google dilaporkan apa adanya", async ({ page }) => {
  test.skip(!isLocal(), "Hanya proyek local (Google tiruan).");
  await page.request.put("/api/youtube/client", { headers: HEADERS, data: { config: JSON.parse(CLIENT) } });
  const started = await (await page.request.post("/api/youtube/connect", { headers: HEADERS })).json();
  const redirect = new URL(started.auth_url).searchParams.get("redirect_uri")!;
  const state = new URL(started.auth_url).searchParams.get("state")!;
  await page.request.get(`${redirect}/?error=access_denied&state=${state}`);
  await page.goto("/settings/youtube");
  await expect(page.getByTestId("youtube-last-error")).toContainText("menolak izin");
});
