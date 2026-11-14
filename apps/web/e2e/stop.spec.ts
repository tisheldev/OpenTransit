import { expect, test } from "@playwright/test";
import { appPath, blockExternal, expectNoSeriousAxeViolations, useTheme } from "./helpers";

// A stop — board 7 (11 November 2026) at 360 × 640, mocked (fixtures mode): every line
// through the stop fans out on the map with a tag; tapping a line, in the panel or on the
// map, shows its whole route with its direction and its end.

const STOP = "#/stop/mot%3Astop%3A13583";

test.beforeEach(async ({ page }) => {
  await blockExternal(page);
});

test("every line through the stop: a row and a faded tag each; a tag chooses its line (axe)", async ({ page }) => {
  await page.goto(appPath(STOP));
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("דיזנגוף סנטר/דיזנגוף");
  const rows = page.getByRole("list", { name: "הקווים בתחנה" }).getByRole("button");
  await expect(rows).toHaveCount(6);
  await expect(rows.first()).toContainText(/172\s*מסוף רדינג\s*2 דק׳/);
  await expect(rows.first()).toHaveAttribute("aria-pressed", "false");
  await expect(page.getByText("זמנים לפי לוח הזמנים")).toBeAttached();
  const tag = page.getByRole("button", { name: "5 רכבת מרכז", exact: true });
  await expect(tag).toBeAttached({ timeout: 20_000 });
  await expectNoSeriousAxeViolations(page, "Stop, every line (he)");

  await tag.press("Enter");
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
