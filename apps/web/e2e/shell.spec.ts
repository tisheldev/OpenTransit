import { expect, test } from "@playwright/test";
import { appPath, blockExternal } from "./helpers";

// Mocked: the dev server runs in fixtures mode, MSW answers /v1 in the browser.

test.beforeEach(async ({ page }) => {
  await blockExternal(page);
});

test("opens in Hebrew, right to left, with the map behind the sheet and the test-data banner", async ({ page }) => {
  await page.goto(appPath("#/"));
  await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
  await expect(page.locator("html")).toHaveAttribute("lang", "he");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("תכנון נסיעה");
  await expect(page.getByText("נתוני בדיקה — לא לוח הזמנים האמיתי")).toBeVisible();
  await expect(page.locator(".map-layer")).toBeAttached();
  await expect(page.locator(".sheet")).toHaveAttribute("data-snap", "half");
  await expect(page.getByRole("button", { name: "חזרה" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "מרכוז המפה על המיקום שלי" })).toBeVisible();
});

test("the sheet covers its snap heights and the handle changes them", async ({ page }) => {
  await page.goto(appPath("#/"));
  const sheet = page.locator(".sheet");
  const height = async () => (await sheet.boundingBox())!.height;
  expect(Math.round(await height())).toBe(Math.round(640 * 0.55));
  const handle = page.getByRole("button", { name: /גודל הגיליון/ });
  await handle.click();
  await expect(sheet).toHaveAttribute("data-snap", "full");
  await expect.poll(height).toBeCloseTo(640 * 0.92, -1);
  await handle.press("ArrowDown");
  await handle.press("ArrowDown");
  await expect(sheet).toHaveAttribute("data-snap", "peek");
  await expect.poll(height).toBeCloseTo(640 * 0.35, -1);
});

test("the language switch flips direction and survives a reload", async ({ page }) => {
  await page.goto(appPath("#/settings"));
  await page.getByLabel("English").check();
  await expect(page.locator("html")).toHaveAttribute("dir", "ltr");
  await expect(page.locator("html")).toHaveAttribute("lang", "en");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Settings");
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("dir", "ltr");
  await page.getByLabel("עברית").check();
  await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
});

test("mirrors the layout: Back sits at the inline start and Locate at the inline end", async ({ page }) => {
  const width = 360;
  await page.goto(appPath("#/settings"));
  const backRtl = (await page.getByRole("button", { name: "חזרה" }).boundingBox())!;
  const locateRtl = (await page.locator(".sheet-locate").boundingBox())!;
  expect(backRtl.x + backRtl.width).toBeGreaterThan(width / 2);
  expect(locateRtl.x).toBeLessThan(width / 2);
  await page.getByLabel("English").check();
  const backLtr = (await page.getByRole("button", { name: "Back" }).boundingBox())!;
  const locateLtr = (await page.locator(".sheet-locate").boundingBox())!;
  expect(backLtr.x).toBeLessThan(width / 2);
  expect(locateLtr.x + locateLtr.width).toBeGreaterThan(width / 2);
});

test("navigation moves focus to the new screen and unknown routes say not found", async ({ page }) => {
  await page.goto(appPath("#/"));
  await page.getByRole("link", { name: "הגדרות" }).click();
  await expect(page).toHaveURL(/#\/settings$/);
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("הגדרות");
  await expect(page.getByRole("heading", { level: 1 })).toBeFocused();
  await page.getByRole("button", { name: "חזרה" }).click();
  await expect(page).toHaveURL(/#\/$/);
  await expect(page.getByRole("heading", { level: 1 })).toBeFocused();
  await page.goto(appPath("#/no-such-screen"));
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("הדף לא נמצא");
});

test("clear all local data resets language and saved state after a second tap", async ({ page }) => {
  let dialogs = 0;
  page.on("dialog", (dialog) => {
    dialogs += 1;
    void dialog.dismiss();
  });
  await page.goto(appPath("#/settings"));
  await page.getByLabel("English").check();
  await page.getByRole("button", { name: "Clear all local data" }).click();
  await expect(page.locator("html")).toHaveAttribute("dir", "ltr");
  await page.getByRole("button", { name: "Tap again to delete everything" }).click();
  await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
  await expect(page.getByText("הנתונים המקומיים נמחקו.")).toBeVisible();
  const stored = await page.evaluate(() => localStorage.getItem("opentransit"));
  expect(stored).toBeNull();
  expect(dialogs).toBe(0);
});

test("touch targets on the core screens are at least 44 px", async ({ page }) => {
  for (const hash of ["#/", "#/search/from", "#/settings"]) {
    await page.goto(appPath(hash));
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    const controls = page.locator(".sheet button:visible, .sheet a:visible, .overlay-top button:visible, .sheet input:visible");
    const count = await controls.count();
    expect(count).toBeGreaterThan(2);
    for (let index = 0; index < count; index += 1) {
      const box = await controls.nth(index).boundingBox();
      if (!box) continue;
      if ((await controls.nth(index).getAttribute("type")) === "radio") continue;
      expect(box.height, `${hash} control ${index}`).toBeGreaterThanOrEqual(44);
    }
  }
});
