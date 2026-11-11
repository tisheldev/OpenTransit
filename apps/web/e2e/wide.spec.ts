import { expect, test } from "@playwright/test";
import { appPath, blockExternal, expectNoSeriousAxeViolations, useTheme } from "./helpers";

// Board 8 (user, 11 November 2026): on a wide screen the panel sits beside the map instead of
// over its bottom. Mocked: fixtures mode; the map is offline (land only).

test.use({ viewport: { width: 1200, height: 760 }, isMobile: false, hasTouch: false });

test.beforeEach(async ({ page }) => {
  await blockExternal(page);
});

for (const [lang, side] of [
  ["he", "right"],
  ["en", "left"],
] as const) {
  test(`${lang}: the panel is a full-height column at the inline start (${side}), the map beside it`, async ({ page }) => {
    if (lang === "en") {
      await page.addInitScript(() =>
        localStorage.setItem(
          "opentransit",
          JSON.stringify({ version: 1, settings: { lang: "en" }, home: null, work: null, favourites: [], recents: [] }),
        ),
      );
    }
    await page.goto(appPath("#/"));
    const sheet = page.locator(".sheet");
    await expect(sheet).toBeVisible();
    const box = (await sheet.boundingBox())!;
    expect(Math.round(box.width)).toBe(400);
    expect(Math.round(box.height)).toBe(760);
    if (side === "right") expect(Math.round(box.x + box.width)).toBe(1200);
    else expect(Math.round(box.x)).toBe(0);
    // The top band (attribution, banners) floats over the map, not over the panel.
    const top = (await page.locator(".overlay-top").boundingBox())!;
    if (side === "right") expect(top.x + top.width).toBeLessThanOrEqual(box.x + 1);
    else expect(top.x).toBeGreaterThanOrEqual(box.width - 1);
  });
}

test("light and dark wide layouts pass axe", async ({ page }) => {
  await page.goto(appPath("#/"));
  await expect(page.locator(".sheet")).toBeVisible();
  await expectNoSeriousAxeViolations(page, "wide dark");
  await useTheme(page, "light");
  await page.goto(appPath("#/"));
  await expect(page.locator(".sheet")).toBeVisible();
  await expectNoSeriousAxeViolations(page, "wide light");
});
