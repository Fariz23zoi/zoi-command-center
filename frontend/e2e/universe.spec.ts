import { expect, test } from "@playwright/test";

const mobile = () => !test.info().project.name.endsWith("desktop");

test("landing → dashboard (dua tab) → Open ZOI AI → kembali", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Explore the Future with ZOI." })).toBeVisible();
  await expect(page.getByTestId("product-ai-lab")).toContainText("Belum tersedia");
  await page.getByRole("link", { name: /Explore Universe/ }).click();
  await expect(page.getByTestId("dashboard-page")).toBeVisible();
  await page.getByRole("tab", { name: "Competitors" }).click();
  await expect(page.getByTestId("competitors-tab")).toBeVisible();
  await page.getByRole("link", { name: "Open ZOI AI" }).first().click();
  await expect(page.getByRole("heading", { name: "Hello, I'm ZOI." })).toBeVisible();
  await expect(page.getByTestId("ws-status")).toHaveText("Tersambung", { timeout: 15_000 });
  if (mobile()) await page.getByRole("button", { name: "Buka menu" }).click();
  await page.getByRole("link", { name: "Back to ZOI Universe" }).click();
  await expect(page.getByTestId("dashboard-page")).toBeVisible();
});

test("workspace AI: kantor 3D di desktop, chat tersimpan di riwayat lalu dihapus", async ({ page }) => {
  test.skip(test.info().project.name !== "development-desktop", "cukup sekali");
  const external: string[] = [];
  page.on("request", (r) => { if (!/^(http:\/\/127\.0\.0\.1|ws:\/\/127\.0\.0\.1|data:|blob:)/.test(r.url())) external.push(r.url()); });
  await page.goto("/ai");
  await expect(page.getByTestId("ws-status")).toHaveText("Tersambung", { timeout: 15_000 });
  await expect(page.getByTestId("ai-stage").locator("canvas, [role=img]").first()).toBeVisible({ timeout: 30_000 });
  await page.getByLabel("Pesan untuk ZOI").fill("halo dari uji riwayat");
  await page.getByRole("button", { name: "Kirim" }).click();
  await expect(page.getByTestId("msg-assistant").last()).not.toContainText("menulis…", { timeout: 20_000 });
  const row = page.getByTestId("ai-history").locator("li").first();
  await expect(row).toContainText("halo dari uji riwayat");
  page.once("dialog", (d) => void d.accept());
  await row.getByRole("button", { name: /Hapus percakapan/ }).click();
  await expect(page.getByTestId("ai-history")).not.toContainText("halo dari uji riwayat");
  await expect(page.getByRole("heading", { name: "Hello, I'm ZOI." })).toBeVisible();
  expect(external).toEqual([]);
});

test("chat: lampirkan file teks lalu kirim", async ({ page }) => {
  test.skip(test.info().project.name !== "development-desktop", "cukup sekali");
  await page.goto("/ai");
  await expect(page.getByTestId("ws-status")).toHaveText("Tersambung", { timeout: 15_000 });
  await page.getByTestId("attach-input").setInputFiles({ name: "catatan.md", mimeType: "text/markdown",
    buffer: Buffer.from("# Rencana video\nTopik: langit biru") });
  await expect(page.getByText("📄 catatan.md")).toBeVisible();
  await page.getByTestId("attach-input").setInputFiles({ name: "foto.png", mimeType: "image/png",
    buffer: Buffer.from([0x89, 0x50, 0x4e, 0x47]) });
  await expect(page.getByRole("alert")).toContainText("belum didukung");
  await page.getByLabel("Pesan untuk ZOI").fill("Ringkas lampiran ini");
  await page.getByRole("button", { name: "Kirim" }).click();
  const user = page.getByTestId("msg-user").last();
  await expect(user).toContainText("Ringkas lampiran ini");
  await user.getByText("📄 catatan.md").click();
  await expect(user.locator("pre")).toContainText("Topik: langit biru");
  await expect(page.getByText("📄 catatan.md", { exact: true }).locator("xpath=ancestor::ul[@aria-label='Lampiran']")).toHaveCount(0);
});
