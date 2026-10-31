import { expect, test } from "@playwright/test";

// Mocked: the dev server runs in fixtures mode, MSW answers /v1 in the browser.

test("home opens in Hebrew, right to left, with the mocked data status", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
  await expect(page.locator("html")).toHaveAttribute("lang", "he");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("בית");
  await expect(page.getByText("נתוני בדיקה — לא לוח הזמנים האמיתי")).toBeVisible();
  await expect(page.getByText("לוח הזמנים זמין")).toBeVisible();
  await expect(page.getByText("זמנים בזמן אמת והתראות אינם זמינים")).toBeVisible();
});

test("the language switch flips direction and survives a reload", async ({ page }) => {
  await page.goto("/#/settings");
  await page.getByLabel("English").check();
  await expect(page.locator("html")).toHaveAttribute("dir", "ltr");
  await expect(page.locator("html")).toHaveAttribute("lang", "en");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Settings");
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("dir", "ltr");
  await page.getByLabel("עברית").check();
  await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
});

test("mirrors the layout: the brand sits at the inline start in each direction", async ({ page }) => {
  await page.goto("/");
  const width = page.viewportSize()!.width;
  const rtl = await page.locator(".brand").boundingBox();
  expect(rtl!.x + rtl!.width).toBeGreaterThan(width / 2);
  await page.goto("/#/settings");
  await page.getByLabel("English").check();
  await page.goto("/#/");
  const ltr = await page.locator(".brand").boundingBox();
  expect(ltr!.x).toBeLessThan(width / 2);
});

test("hash routes reach every placeholder screen and unknown routes say not found", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("link", { name: "תחנות בסביבה" }).click();
  await expect(page).toHaveURL(/#\/nearby$/);
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("תחנות בסביבה");
  await expect(page.locator("#main")).toBeFocused();
  await page.goto("/#/no-such-screen");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("הדף לא נמצא");
});

test("clear all local data resets language and saved state", async ({ page }) => {
  await page.goto("/#/settings");
  await page.getByLabel("English").check();
  page.once("dialog", (dialog) => void dialog.accept());
  await page.getByRole("button", { name: "Clear all local data" }).click();
  await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
  await expect(page.getByRole("status")).toHaveText("הנתונים המקומיים נמחקו.");
  const stored = await page.evaluate(() => JSON.parse(localStorage.getItem("opentransit") ?? "null"));
  expect(stored?.settings?.lang ?? "he").toBe("he");
});

test("touch targets on the placeholder screens are at least 44 px", async ({ page }) => {
  await page.goto("/");
  for (const link of await page.locator(".link-list a").all()) {
    const box = await link.boundingBox();
    expect(box!.height).toBeGreaterThanOrEqual(44);
  }
});
