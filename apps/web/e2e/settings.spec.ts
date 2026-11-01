import { expect, test } from "@playwright/test";
import { appPath, blockExternal, expectNoSeriousAxeViolations } from "./helpers";

// Settings — C07 at 360 × 640, mocked (fixtures mode).

test.beforeEach(async ({ page }) => {
  await blockExternal(page);
});

test("Hebrew: data status, unavailable live data, credits and version (axe)", async ({ page }) => {
  await page.goto(appPath("#/settings"));
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("הגדרות");
  await expect(page.getByText(/לוח זמנים מתוכנן מ־/)).toBeVisible();
  await expect(page.getByText("זמנים בזמן אמת: לא זמין")).toBeAttached();
  await expect(page.getByText("התראות שירות: לא זמין")).toBeAttached();
  await expect(page.getByText("לוח הזמנים: משרד התחבורה")).toBeAttached();
  await expect(page.locator("#main").getByText("© תורמי OpenStreetMap")).toBeAttached();
  await expect(page.getByText("אריחי המפה: OpenFreeMap")).toBeAttached();
  await expect(page.getByText(/^גרסה /)).toBeAttached();
  await expectNoSeriousAxeViolations(page, "Settings (he)");
});

test("English: save a favourite through Search, rename it, delete it (axe)", async ({ page }) => {
  await page.goto(appPath("#/settings"));
  await page.getByLabel("English").check();
  await page.getByRole("button", { name: "+ Add a saved place" }).click();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Add a saved place");
  await page.getByRole("searchbox").fill("Dizengoff");
  await page.getByTestId("search-results").getByRole("button").first().click();
  const name = page.getByLabel("Name for this place");
  await expect(name).toHaveValue("Dizengoff Center/Dizengoff");
  await name.fill("Mall");
  await page.getByRole("button", { name: "Save" }).click();
  await expect(page).toHaveURL(/#\/settings$/);
  await expect(page.getByText("Mall")).toBeVisible();
  await expectNoSeriousAxeViolations(page, "Settings with a favourite (en)");

  await page.getByRole("button", { name: "Rename Mall" }).click();
  await page.getByLabel("New name for Mall").fill("Dizengoff mall");
  await page.getByRole("button", { name: "Save name" }).click();
  await expect(page.getByText("Dizengoff mall")).toBeVisible();
  await page.getByRole("button", { name: "Delete Dizengoff mall" }).click();
  await expect(page.getByText("No other saved places yet.")).toBeVisible();
  const stored = await page.evaluate(() => JSON.parse(localStorage.getItem("opentransit") ?? "null"));
  expect(stored.favourites).toEqual([]);
});

test("the clear-all button arms on the first tap and can be cancelled", async ({ page }) => {
  await page.goto(appPath("#/settings"));
  await page.getByRole("button", { name: "מחיקת כל הנתונים במכשיר" }).click();
  await expect(page.getByRole("button", { name: "הקישו שוב כדי למחוק הכול" })).toBeVisible();
  await expectNoSeriousAxeViolations(page, "Settings, clear armed (he)");
  await page.getByRole("button", { name: "ביטול" }).click();
  await expect(page.getByRole("button", { name: "מחיקת כל הנתונים במכשיר" })).toBeVisible();
});
