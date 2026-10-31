import { expect, test, type Page } from "@playwright/test";
import { appPath, blockExternal, expectNoSeriousAxeViolations } from "./helpers";

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

test("the sheet covers its snap heights, never the top band, and the handle changes them", async ({ page }) => {
  await page.goto(appPath("#/"));
  const sheet = page.locator(".sheet");
  const height = async () => (await sheet.boundingBox())!.height;
  expect(Math.round(await height())).toBe(Math.round(640 * 0.55));
  const handle = page.getByRole("button", { name: /גודל הגיליון/ });
  await handle.click();
  await expect(sheet).toHaveAttribute("data-snap", "full");
  // Full stops below the top band (test-data banner and attribution): nothing there is covered.
  const top = (await page.locator(".overlay-top").boundingBox())!;
  await expect.poll(height).toBeCloseTo(Math.min(640 * 0.92, 640 - top.height), -1);
  expect((await sheet.boundingBox())!.y).toBeGreaterThanOrEqual(top.y + top.height - 1);
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

test("mirrors the layout: Back at the inline start, Locate and the attribution at the inline end", async ({ page }) => {
  const width = 360;
  await page.goto(appPath("#/settings"));
  const backRtl = (await page.getByRole("button", { name: "חזרה" }).boundingBox())!;
  const creditsRtl = (await page.getByTestId("map-attribution").boundingBox())!;
  expect(backRtl.x + backRtl.width).toBeGreaterThan(width / 2);
  expect(creditsRtl.x).toBeLessThan(width / 2);
  expect(creditsRtl.x + creditsRtl.width).toBeLessThanOrEqual(backRtl.x);
  await page.getByLabel("English").check();
  const backLtr = (await page.getByRole("button", { name: "Back" }).boundingBox())!;
  const creditsLtr = (await page.getByTestId("map-attribution").boundingBox())!;
  expect(backLtr.x).toBeLessThan(width / 2);
  expect(creditsLtr.x).toBeGreaterThanOrEqual(backLtr.x + backLtr.width);
  await page.goto(appPath("#/"));
  const locateLtr = (await page.locator(".sheet-locate").boundingBox())!;
  expect(locateLtr.x + locateLtr.width).toBeGreaterThan(width / 2);
  await page.goto(appPath("#/settings"));
  await page.getByLabel("עברית").check();
  await page.goto(appPath("#/"));
  const locateRtl = (await page.locator(".sheet-locate").boundingBox())!;
  expect(locateRtl.x).toBeLessThan(width / 2);
});

test("Locate shows only where a position helps, never over a full sheet or the top band", async ({ page }) => {
  await page.goto(appPath("#/"));
  const locate = page.getByRole("button", { name: "מרכוז המפה על המיקום שלי" });
  await expect(locate).toBeVisible();
  const box = (await locate.boundingBox())!;
  const top = (await page.locator(".overlay-top").boundingBox())!;
  expect(box.y).toBeGreaterThan(top.y + top.height);
  await page.getByRole("button", { name: /גודל הגיליון/ }).click();
  await expect(page.locator(".sheet")).toHaveAttribute("data-snap", "full");
  await expect(locate).toHaveCount(0);
  for (const hash of ["#/settings", "#/search/to", "#/compare"]) {
    await page.goto(appPath(hash));
    await expect(page.getByRole("heading", { level: 1 })).toBeAttached();
    await expect(page.getByRole("button", { name: "מרכוז המפה על המיקום שלי" })).toHaveCount(0);
  }
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

/** Home → Search(to) → a stop → Compare (mocked journeys). */
async function planToCompare(page: Page): Promise<void> {
  await page.goto(appPath("#/"));
  await page.getByRole("button", { name: "לאן?" }).click();
  await page.getByRole("searchbox").fill("דיזנגוף");
  await page.getByTestId("search-results").getByRole("button").first().click();
  await expect(page).toHaveURL(/#\/compare$/);
}

test("on Compare (a screen that sets a snap) a tap and a drag on the handle stick", async ({ page }) => {
  await planToCompare(page);
  const sheet = page.locator(".sheet");
  const handle = page.getByRole("button", { name: /גודל הגיליון/ });
  await expect(sheet).toHaveAttribute("data-snap", /half|full/);
  const start = await sheet.getAttribute("data-snap");
  await handle.click();
  const afterTap = start === "full" ? "peek" : "full";
  await expect(sheet).toHaveAttribute("data-snap", afterTap);
  await page.waitForTimeout(600);
  await expect(sheet).toHaveAttribute("data-snap", afterTap);

  // Drag the handle to just above the middle of the screen: half, and it stays there.
  const box = (await handle.boundingBox())!;
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.down();
  await page.mouse.move(box.x + box.width / 2, 640 - 640 * 0.55 + 20, { steps: 10 });
  await page.mouse.up();
  await expect(sheet).toHaveAttribute("data-snap", "half");
  await page.waitForTimeout(600);
  await expect(sheet).toHaveAttribute("data-snap", "half");
  await expect.poll(async () => (await sheet.boundingBox())!.height).toBeCloseTo(640 * 0.55, -1);
  await expectNoSeriousAxeViolations(page, "Compare at half (he)");
});

test("each screen opens at its top: Back from Search shows Compare unscrolled", async ({ page }) => {
  await planToCompare(page);
  const content = page.locator(".sheet-content");
  // At peek the options and details overflow the sheet.
  await page.getByRole("button", { name: /גודל הגיליון/ }).focus();
  await page.keyboard.press("ArrowDown");
  await page.keyboard.press("ArrowDown");
  await expect(page.locator(".sheet")).toHaveAttribute("data-snap", "peek");
  await expect.poll(() => content.evaluate((element) => element.scrollHeight > element.clientHeight)).toBe(true);
  await content.evaluate((element) => (element.scrollTop = element.scrollHeight));
  expect(await content.evaluate((element) => element.scrollTop)).toBeGreaterThan(0);
  await page.getByRole("button", { name: /^מאיפה\?/ }).click();
  await expect(page).toHaveURL(/#\/search\/from$/);
  expect(await content.evaluate((element) => element.scrollTop)).toBe(0);
  await page.getByRole("button", { name: "חזרה" }).click();
  await expect(page).toHaveURL(/#\/compare$/);
  await expect.poll(() => content.evaluate((element) => element.scrollTop)).toBe(0);
});

test("history: Home → Search → Compare → Search → Compare, then Back is Home in one tap", async ({ page }) => {
  await planToCompare(page);
  await page.getByRole("button", { name: /^מאיפה\?/ }).click();
  await expect(page).toHaveURL(/#\/search\/from$/);
  await page.getByRole("searchbox").fill("דיזנגוף");
  await page.getByTestId("search-results").getByRole("button").nth(1).click();
  await expect(page).toHaveURL(/#\/compare$/);
  await page.getByRole("button", { name: "חזרה" }).click();
  await expect(page).toHaveURL(/#\/$/);
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("תכנון נסיעה");
  // One Compare entry ahead, then the Search it opened (not a second Compare).
  await page.goForward();
  await expect(page).toHaveURL(/#\/compare$/);
  await page.goForward();
  await expect(page).toHaveURL(/#\/search\/from$/);
});
