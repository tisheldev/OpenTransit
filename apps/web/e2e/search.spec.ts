import { expect, test } from "@playwright/test";
import { appPath, blockExternal, expectNoSeriousAxeViolations, useScenario, useTheme } from "./helpers";

// Where to / Where from — C02 at 360 × 640, mocked (fixtures mode).

test.beforeEach(async ({ page }) => {
  await blockExternal(page);
});

test("Hebrew: To opens focused, results arrive, and a stop opens Compare without IDs in the URL", async ({ page }) => {
  await page.goto(appPath("#/"));
  await page.getByRole("button", { name: "לאן נוסעים?" }).click();
  await expect(page).toHaveURL(/#\/search\/to$/);
  const field = page.getByRole("searchbox", { name: "חיפוש מקום, תחנה או קו" });
  await expect(field).toBeFocused();
  await expect(page.getByRole("button", { name: "בחירה במפה" })).toBeVisible();
  await expectNoSeriousAxeViolations(page, "Search, before typing (he)");
  await field.fill("דיזנגוף סנטר");
  const results = page.getByTestId("search-results");
  await expect(results.locator(".sx-main").first()).toContainText("דיזנגוף סנטר/דיזנגוף");
  await expect(results.locator(".sx-main").first()).toContainText("תחנה");
  await expect(page.getByText("5 תוצאות")).toBeAttached();
  await expectNoSeriousAxeViolations(page, "Search, results (he)");
  await results.locator(".sx-main").first().click();
  await expect(page).toHaveURL(/#\/compare$/);
  expect(page.url()).not.toMatch(/mot|stop|32\.0/);
  const draft = await page.evaluate(() => JSON.parse(sessionStorage.getItem("opentransit:plan") ?? "null"));
  expect(draft.to.place.stopId).toBe("mot:stop:13583");
});

test("one clear button inside the field; a stop reads 'stop code · street, city'", async ({ page }) => {
  await page.goto(appPath("#/search/to"));
  const field = page.getByRole("searchbox");
  await field.fill("דיזנגוף סנטר");
  const clear = page.getByRole("button", { name: "ניקוי החיפוש" });
  await expect(clear).toHaveCount(1);
  const fieldBox = (await page.locator(".sx-field").boundingBox())!;
  const clearBox = (await clear.boundingBox())!;
  // Inside the field's box, at its inline end (left in Hebrew).
  expect(clearBox.x).toBeGreaterThanOrEqual(fieldBox.x - 1);
  expect(clearBox.x + clearBox.width).toBeLessThan(fieldBox.x + fieldBox.width / 2);
  const first = page.getByTestId("search-results").locator(".sx-main").first();
  await expect(first.locator(".sx-sub")).toHaveText(/^תחנה \d+\s*·\s*\S/);
  await clear.click();
  await expect(field).toHaveValue("");
  await expect(field).toBeFocused();
});

test("typing more keeps the previous results in place while the next answer loads", async ({ page }) => {
  await page.goto(appPath("#/search/to"));
  const field = page.getByRole("searchbox");
  await field.fill("דיזנגוף");
  await expect(page.getByTestId("search-results")).toBeVisible();
  const before = (await page.getByTestId("search-results").boundingBox())!;
  await field.press("End");
  await field.pressSequentially(" ס", { delay: 30 });
  // Either the new answer already arrived or the old one is still shown: never an empty jump.
  await expect(page.getByTestId("search-skeleton")).toHaveCount(0);
  const list = page.locator("[data-testid=search-results], [data-testid=search-results-previous]");
  await expect(list).toHaveCount(1);
  expect(Math.abs((await list.boundingBox())!.y - before.y)).toBeLessThan(2);
});

test("choose on map starts at street level, with Locate available", async ({ page }) => {
  await page.goto(appPath("#/search/from"));
  await page.getByRole("button", { name: "בחירה במפה" }).click();
  await expect(page.locator(".sheet")).toHaveAttribute("data-snap", "peek");
  await expect(page.getByRole("button", { name: "מרכוז המפה על המיקום שלי" })).toBeVisible();
  await expectNoSeriousAxeViolations(page, "Search, choose on map (he)");
  await page.getByRole("button", { name: "חזרה לחיפוש" }).click();
  await expect(page.locator(".sheet")).toHaveAttribute("data-snap", "full");
  await expect(page.getByRole("button", { name: "מרכוז המפה על המיקום שלי" })).toHaveCount(0);
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

test("results end with Choose on map", async ({ page }) => {
  await page.goto(appPath("#/search/to"));
  await page.getByRole("searchbox").fill("דיזנגוף");
  await expect(page.getByTestId("search-results").getByRole("button").first()).toContainText("דיזנגוף");
  const pick = page.getByRole("button", { name: "בחירה במפה" });
  await expect(pick).toHaveCount(1);
  const results = (await page.getByTestId("search-results").boundingBox())!;
  expect((await pick.boundingBox())!.y).toBeGreaterThanOrEqual(results.y + results.height - 1);
});

test("a number lists lines from one digit, exact first; a line opens the line (axe)", async ({ page }) => {
  await page.goto(appPath("#/search/to"));
  // Back sits beside the field, as drawn: one Back on the screen.
  await expect(page.getByRole("button", { name: "חזרה" })).toHaveCount(1);
  await page.getByRole("searchbox").fill("8");
  const rows = page.getByTestId("search-results").getByRole("button");
  await expect(rows.first()).toContainText(/^8\s*מסוף רידינג ↔ מסוף הטייסים\s*דן · תל אביב-יפו/);
  await expect(rows.nth(1)).toContainText(/^8\s*מרכזית המפרץ ↔ בת גלים\s*אגד · חיפה/);
  await expect(rows.nth(4)).toHaveText("עוד 6 קווים");
  await expectNoSeriousAxeViolations(page, "Search, lines (he)");
  await rows.nth(4).click();
  await expect(rows).toHaveCount(10);
  await rows.first().click();
  await expect(page).toHaveURL(/#\/line\/5%3A10008$/);
});

test("a stop row's clock opens its departures; the row itself still sets the journey end", async ({ page }) => {
  await page.goto(appPath("#/search/to"));
  await page.getByRole("searchbox").fill("דיזנגוף סנטר");
  const clock = page.getByRole("button", { name: "לוח היציאות של דיזנגוף סנטר/דיזנגוף" }).first();
  const box = (await clock.boundingBox())!;
  expect(box.width).toBeGreaterThanOrEqual(44);
  expect(box.height).toBeGreaterThanOrEqual(44);
  await clock.click();
  await expect(page).toHaveURL(/#\/stop\/mot%3Astop%3A13583$/);
});

// Light theme (dark is the default, and what the tests above run in).

test("light theme: before typing, results, skeleton, empty, partial and error (axe)", async ({ page }) => {
  await useTheme(page, "light");
  await page.goto(appPath("#/search/from"));
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  await expect(page.getByRole("button", { name: "בחירה במפה" })).toBeVisible();
  await expectNoSeriousAxeViolations(page, "Search, before typing, light (he)");
  await page.getByRole("searchbox").fill("דיזנגוף סנטר");
  await expect(page.getByTestId("search-results").locator(".sx-main").first()).toContainText("דיזנגוף סנטר/דיזנגוף");
  await expectNoSeriousAxeViolations(page, "Search, results, light (he)");
  await page.getByRole("searchbox").fill("zzzz");
  await expect(page.getByText("לא נמצאו תוצאות. נסו לכתוב אחרת.")).toBeVisible();
  await expectNoSeriousAxeViolations(page, "Search, empty, light (he)");

  await useScenario(page, "places-partial");
  await page.reload();
  await page.getByRole("searchbox").fill("דיזנגוף");
  await expect(page.getByRole("note").filter({ hasText: "כתובת: לא זמין כרגע" })).toBeVisible();
  await expectNoSeriousAxeViolations(page, "Search, partial, light (he)");

  await useScenario(page, "places-unavailable");
  await page.reload();
  await page.getByRole("searchbox").fill("דיזנגוף");
  await expect(page.getByRole("alert")).toContainText("החיפוש בסוג הזה אינו זמין כרגע.");
  await expectNoSeriousAxeViolations(page, "Search, error, light (he)");

  await useScenario(page, "places-slow");
  await page.reload();
  await page.getByRole("searchbox").fill("דיזנגוף");
  await expect(page.getByTestId("search-skeleton")).toBeVisible();
  await expectNoSeriousAxeViolations(page, "Search, typing, light (he)");
});

test("an error and a partial answer pass axe (dark)", async ({ page }) => {
  await useScenario(page, "places-partial");
  await page.goto(appPath("#/search/to"));
  await page.getByRole("searchbox").fill("דיזנגוף");
  await expect(page.getByRole("note").filter({ hasText: "כתובת: לא זמין כרגע" })).toBeVisible();
  await expectNoSeriousAxeViolations(page, "Search, partial (he)");
  await useScenario(page, "places-unavailable");
  await page.reload();
  await page.getByRole("searchbox").fill("דיזנגוף");
  await expect(page.getByRole("alert")).toBeVisible();
  await expectNoSeriousAxeViolations(page, "Search, error (he)");
});
