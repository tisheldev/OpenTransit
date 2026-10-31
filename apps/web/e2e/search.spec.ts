import { expect, test } from "@playwright/test";
import { appPath, blockExternal, expectNoSeriousAxeViolations, useScenario } from "./helpers";

// Where to / Where from — C02 at 360 × 640, mocked (fixtures mode).

test.beforeEach(async ({ page }) => {
  await blockExternal(page);
});

test("Hebrew: To opens focused, results arrive, and a stop opens Compare without IDs in the URL", async ({ page }) => {
  await page.goto(appPath("#/"));
  await page.getByRole("button", { name: "לאן?" }).click();
  await expect(page).toHaveURL(/#\/search\/to$/);
  const field = page.getByRole("searchbox", { name: "חיפוש כתובת, תחנה או מקום" });
  await expect(field).toBeFocused();
  await expect(page.getByRole("button", { name: "בחירה במפה" })).toBeVisible();
  await expectNoSeriousAxeViolations(page, "Search, before typing (he)");
  await field.fill("דיזנגוף סנטר");
  const results = page.getByTestId("search-results");
  await expect(results.getByRole("button").first()).toContainText("דיזנגוף סנטר/דיזנגוף");
  await expect(results.getByRole("button").first()).toContainText("תחנה");
  await expect(page.getByText("5 תוצאות")).toBeAttached();
  await expectNoSeriousAxeViolations(page, "Search, results (he)");
  await results.getByRole("button").first().click();
  await expect(page).toHaveURL(/#\/compare$/);
  expect(page.url()).not.toMatch(/mot|stop|32\.0/);
  const draft = await page.evaluate(() => JSON.parse(sessionStorage.getItem("opentransit:plan") ?? "null"));
  expect(draft.to.place.stopId).toBe("mot:stop:13583");
});

test("typing shows skeleton rows (axe)", async ({ page }) => {
  await useScenario(page, "places-slow");
  await page.goto(appPath("#/search/to"));
  await page.getByRole("searchbox").fill("דיזנגוף");
  await expect(page.getByTestId("search-skeleton")).toBeVisible();
  await expectNoSeriousAxeViolations(page, "Search, typing (he)");
});

test("zero matches is a calm empty result (axe)", async ({ page }) => {
  await page.goto(appPath("#/search/to"));
  await page.getByRole("searchbox").fill("zzzz");
  await expect(page.getByText("לא נמצאו תוצאות. נסו לכתוב אחרת.")).toBeVisible();
  await expect(page.getByRole("alert")).toHaveCount(0);
  await expectNoSeriousAxeViolations(page, "Search, empty (he)");
});

test("English: From offers My location, results mirror left to right", async ({ page }) => {
  await page.goto(appPath("#/settings"));
  await page.getByLabel("English").check();
  await page.goto(appPath("#/search/from"));
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Where from?");
  await expect(page.getByRole("button", { name: "My location", exact: true })).toBeVisible();
  await page.getByRole("searchbox").fill("Dizengoff");
  const first = page.getByTestId("search-results").getByRole("button").first();
  await expect(first).toContainText("Dizengoff Center/Dizengoff");
  await expectNoSeriousAxeViolations(page, "Search, results (en)");
  await page.getByRole("searchbox").fill("zzzz");
  await expect(page.getByText(/No results/)).toBeVisible();
  await expectNoSeriousAxeViolations(page, "Search, empty (en)");
});

test("a partial answer names the unavailable type inline", async ({ page }) => {
  await useScenario(page, "places-partial");
  await page.goto(appPath("#/search/to"));
  await page.getByRole("searchbox").fill("דיזנגוף");
  await expect(page.getByRole("note").filter({ hasText: "כתובת: לא זמין כרגע" })).toBeVisible();
});

test("all categories unavailable is an error with retry", async ({ page }) => {
  await useScenario(page, "places-unavailable");
  await page.goto(appPath("#/search/to"));
  await page.getByRole("searchbox").fill("דיזנגוף");
  await expect(page.getByRole("alert")).toContainText("החיפוש בסוג הזה אינו זמין כרגע.");
  await expect(page.getByRole("button", { name: "נסו שוב" })).toBeVisible();
});

test("save mode: setting Home from Search fills the Home chip", async ({ page }) => {
  await page.goto(appPath("#/"));
  await page.getByRole("button", { name: /הגדרת בית/ }).click();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("הגדרת בית");
  await page.getByRole("searchbox").fill("דיזנגוף");
  await page.getByTestId("search-results").getByRole("button").first().click();
  await expect(page).toHaveURL(/#\/$/);
  await expect(page.getByRole("button", { name: "בית", exact: true })).toBeVisible();
});
