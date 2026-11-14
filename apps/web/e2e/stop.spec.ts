import { expect, test } from "@playwright/test";
import { appPath, blockExternal, expectNoSeriousAxeViolations, useTheme } from "./helpers";

// A stop — board 7 (11 November 2026) at 360 × 640, mocked (fixtures mode): every line
// through the stop fans out on the map with a tag; tapping a line, in the panel or on the
// map, shows its whole route with its direction and its end.

const STOP = "#/stop/mot%3Astop%3A13583";

test.beforeEach(async ({ page }) => {
  await blockExternal(page);
});

test("every line through the stop: a row each, one tag per direction; a tag lists or chooses its lines (axe)", async ({ page }) => {
  await page.goto(appPath(STOP));
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("דיזנגוף סנטר/דיזנגוף");
  const rows = page.getByRole("list", { name: "הקווים בתחנה" }).getByRole("button");
  await expect(rows).toHaveCount(6);
  await expect(rows.first()).toContainText(/172\s*מסוף רדינג\s*2 דק׳/);
  await expect(rows.first()).toHaveAttribute("aria-pressed", "false");
  await expect(page.getByText("זמנים לפי לוח הזמנים")).toBeAttached();
  // Five lines leave north up the same street: one tag at the map's edge, badges only (four
  // and "+1", the fifth named to a screen reader).
  const north = page.getByRole("button", { name: /^172\s*8\s*5\s*2\s*39$/ });
  await expect(north).toBeAttached({ timeout: 20_000 });
  const west = page.getByRole("button", { name: /115\s*לכיוון מסוף רדינג/ });
  await expect(west).toBeAttached();
  // The tags fade in once the lines have drawn out; check them when fully shown.
  await expect(north).toHaveCSS("opacity", "1");
  await expect(west).toHaveCSS("opacity", "1");
  await expectNoSeriousAxeViolations(page, "Stop, every line (he)");

  // Tapping it lists that direction's lines in the panel; "כל הקווים" lists them all again.
  await north.press("Enter");
  await expect(rows).toHaveCount(5);
  await expect(page.getByText("5 קווים בכיוון הזה")).toBeVisible();
  await page.getByRole("button", { name: "כל הקווים" }).click();
  await expect(rows).toHaveCount(6);

  await rows.nth(3).click();
  await expect(rows.nth(3)).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByRole("img", { name: "קו 5 נוסע אל רכבת מרכז" })).toBeAttached();
  await expect(page.getByRole("img", { name: "כיוון הנסיעה של קו 5" })).toBeAttached();
  await expectNoSeriousAxeViolations(page, "Stop, a line chosen (he)");
  await rows.nth(3).click();
  await expect(rows.nth(3)).toHaveAttribute("aria-pressed", "false");
  await expect(page.getByRole("img", { name: "קו 5 נוסע אל רכבת מרכז" })).toHaveCount(0);
});

test("light theme: a line chosen from its row (axe); Back returns Home", async ({ page }) => {
  await useTheme(page, "light");
  await page.goto(appPath("#/"));
  await page.getByRole("list", { name: "הקווים הקרובים אליך" }).getByRole("button").first().click();
  await expect(page).toHaveURL(/#\/stop\/mot%3Astop%3A13583$/);
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  const chosen = page.getByRole("button", { pressed: true });
  await expect(chosen).toContainText("172");
  await expect(page.getByRole("img", { name: "קו 172 נוסע אל מסוף רדינג" })).toBeAttached({ timeout: 20_000 });
  await expectNoSeriousAxeViolations(page, "Stop, a line chosen, light (he)");
  await page.getByRole("button", { name: "חזרה" }).click();
  await expect(page).toHaveURL(/#\/$/);
});

test("a stop that is not in the timetable says so", async ({ page }) => {
  await page.goto(appPath("#/stop/mot%3Astop%3Anowhere"));
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("תחנה");
  await expect(page.getByRole("alert")).toContainText("לא נמצא עוד בלוח הזמנים.");
  await expectNoSeriousAxeViolations(page, "Stop, not found (he)");
});
