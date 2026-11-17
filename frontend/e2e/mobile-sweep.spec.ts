import { expect, test } from "@playwright/test";

import { MENU } from "../apps/web/src/menu";

/** Phase 9: setiap halaman menu di layar HP (375 px) — tanpa geser horizontal, tanpa error JavaScript. */
test.describe("sapu halaman di HP", () => {
  test.skip(() => !test.info().project.name.endsWith("mobile"), "khusus viewport HP");

  for (const item of [...MENU, { path: "/settings/ai-cloud", label: "AI Cloud" }, { path: "/settings/youtube", label: "YouTube" }, { path: "/settings/voice", label: "Suara" }, { path: "/ai/voice", label: "Suara (AI)" }, { path: "/ai/models", label: "AI Models" }, { path: "/", label: "Landing" }, { path: "/products", label: "Products" }, { path: "/about", label: "About" }]) {
    test(`${item.label} (${item.path})`, async ({ page }) => {
      const errors: string[] = [];
      page.on("pageerror", (e) => errors.push(String(e)));
      await page.goto(item.path);
      await expect(page.locator("main h1, section.page h1").first()).toBeVisible({ timeout: 10_000 });
      await page.waitForTimeout(300);
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
      expect(overflow, `geser horizontal di ${item.path}`).toBeLessThanOrEqual(0);
      // Elemen yang keluar layar walau induknya memotong (overflow hidden) juga dihitung.
      const wide = await page.evaluate(() => [...document.querySelectorAll("main *")].filter((e) => {
        const b = e.getBoundingClientRect();
        return b.width > 0 && b.right > document.documentElement.clientWidth + 1 && !e.closest(".table-wrap, pre, .md-code");
      }).slice(0, 3).map((e) => `${e.tagName}.${(e as HTMLElement).className}`));
      expect(wide, `elemen keluar layar di ${item.path}`).toEqual([]);
      expect(errors, `error JavaScript di ${item.path}`).toEqual([]);
    });
  }
});
