import { expect, test } from "@playwright/test";

import { MENU } from "../apps/web/src/menu";

/** Phase 9: setiap halaman menu di layar HP (375 px) — tanpa geser horizontal, tanpa error JavaScript. */
test.describe("sapu halaman di HP", () => {
  test.skip(() => !test.info().project.name.endsWith("mobile"), "khusus viewport HP");

  for (const item of [...MENU, { path: "/settings/ai-cloud", label: "AI Cloud" }, { path: "/settings/youtube", label: "YouTube" }]) {
    test(`${item.label} (${item.path})`, async ({ page }) => {
      const errors: string[] = [];
      page.on("pageerror", (e) => errors.push(String(e)));
      await page.goto(item.path);
      await expect(page.locator("main h1, section.page h1").first()).toBeVisible({ timeout: 10_000 });
      await page.waitForTimeout(300);
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
      expect(overflow, `geser horizontal di ${item.path}`).toBeLessThanOrEqual(0);
      expect(errors, `error JavaScript di ${item.path}`).toEqual([]);
    });
  }
});
