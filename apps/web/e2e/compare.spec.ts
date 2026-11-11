import { expect, test, type Page } from "@playwright/test";
import { appPath, blockExternal, expectNoSeriousAxeViolations, useScenario as setScenario, useTheme as setTheme } from "./helpers";

// Mocked Compare (boards Choose and Step, 11 November 2026): fixtures mode at 360 x 640. The plan draft is written to
// sessionStorage ("opentransit:plan", the PlanDraft shape) before the app starts. Dark is
// the default theme; the light-theme tests at the end repeat the axe checks.

const draft = {
  from: {
    type: "place",
    place: {
      label: "דיזנגוף סנטר",
      locality: "תל אביב-יפו",
      kind: "stop",
      latitude: 32.0753,
      longitude: 34.7749,
      stopId: "mot:stop:13583",
      placeRef: null,
      refGenerationId: null,
    },
  },
  to: {
    type: "place",
    place: {
      label: "טכניון",
      locality: "חיפה",
      kind: "pin",
      latitude: 32.7767,
      longitude: 35.0231,
      stopId: null,
      placeRef: null,
      refGenerationId: null,
    },
  },
  when: { mode: "depart_at", wall: "2026-10-01T08:00", offset: "auto" },
};

async function openCompare(
  page: Page,
  scenario: string | null = null,
  plan: object = draft,
  theme: "dark" | "light" | null = null,
): Promise<void> {
  await blockExternal(page);
  await setScenario(page, scenario);
  await page.addInitScript((value) => sessionStorage.setItem("opentransit:plan", value), JSON.stringify(plan));
  if (theme) await setTheme(page, theme);
  await page.goto(appPath("#/compare"));
  // A cold dev server compiles the Compare chunk on first request (seen with parallel
  // workers): wait for the screen itself before the 5 s assertions start counting.
  await expect(page.locator(".compare")).toBeVisible({ timeout: 20_000 });
}

const optionList = (page: Page) => page.getByRole("list", { name: /אפשרויות נסיעה|Trip options/ });

const detailsButton = (page: Page) => page.getByRole("button", { name: "פרטי המסלול" });
const legButtons = (page: Page) => page.getByRole("region", { name: /פרטי מסלול|Route details/ }).getByRole("button");

test("Choose at the half sheet: the destination, the start, the time tag, every option and פרטי המסלול in view", async ({ page }) => {
  await openCompare(page);
  const options = optionList(page).getByRole("button");
  await expect(options).toHaveCount(3);
  await expect(page.locator(".sheet")).toHaveAttribute("data-snap", "half");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("טכניון");
  await expect(page.getByRole("button", { name: /^מוצא: ?מדיזנגוף סנטר$/ })).toBeInViewport();
  await expect(page.getByRole("button", { name: /^שינוי השעה: יציאה 08:00/ })).toBeInViewport();
  const main = detailsButton(page);
  await expect(main).toBeInViewport();
  const bar = (await page.locator(".compare-start").boundingBox())!;
  // Opaque and full width, flush with the bottom.
  expect(bar.width).toBeGreaterThanOrEqual(359);
  expect(bar.y + bar.height).toBeGreaterThanOrEqual(639);
  for (let i = 0; i < 3; i += 1) {
    const box = (await options.nth(i).boundingBox())!;
    expect(box.y + box.height, `option ${i + 1} above פרטי המסלול`).toBeLessThanOrEqual(bar.y + 1);
  }
  await expect(options.first()).toHaveAccessibleName(/^אפשרות 1, 105 דקות, יציאה 08:07, הגעה 09:52, 2 החלפות, קווים: 8, רכבת, 1/);
  // Hebrew: the departure sits on the right of the arrival.
  const times = options.first().locator(".b-op__time bdi");
  expect((await times.first().boundingBox())!.x).toBeGreaterThan((await times.last().boundingBox())!.x);
  await expectNoSeriousAxeViolations(page, "compare choose (he)");
});

test("choosing by row swaps the chosen option without a request and keeps the half sheet", async ({ page }) => {
  const journeyRequests: string[] = [];
  page.on("request", (request) => {
    if (request.method() === "POST" && new URL(request.url()).pathname === "/v1/journeys") journeyRequests.push(request.url());
  });
  await openCompare(page);
  const options = optionList(page).getByRole("button");
  await expect(options).toHaveCount(3);
  await expect(options.first()).toHaveAttribute("aria-pressed", "true");
  const before = journeyRequests.length;
  await options.nth(1).click();
  await expect(options.nth(1)).toHaveAttribute("aria-pressed", "true");
  await expect(options.first()).toHaveAttribute("aria-pressed", "false");
  expect(journeyRequests.length).toBe(before);
  await expect(page.locator(".sheet")).toHaveAttribute("data-snap", "half");
  await expectNoSeriousAxeViolations(page, "compare choose, second option (he)");
});

test("route details: a tapped leg is shown on the map, כל המסלול zooms out, Back returns to Choose", async ({ page }) => {
  await openCompare(page);
  await optionList(page).getByRole("button").nth(1).click();
  await detailsButton(page).click();
  await expect(page).toHaveURL(/#\/route$/);
  await expect(page.getByRole("heading", { level: 1 })).toContainText("08:27");
  const legs = legButtons(page);
  await expect(legs.first()).toHaveAttribute("aria-pressed", "true");
  await expect(legs.first()).toContainText("מוצג במפה");
  const whole = page.getByRole("button", { name: "כל המסלול" });
  await expect(whole).toBeVisible();
  // It floats over the map, above the sheet.
  const sheetTop = (await page.locator(".sheet").boundingBox())!.y;
  const wholeBox = (await whole.boundingBox())!;
  expect(wholeBox.y + wholeBox.height).toBeLessThanOrEqual(sheetTop);
  await expectNoSeriousAxeViolations(page, "compare route details (he)");

  await legs.nth(2).click();
  await expect(legs.nth(2)).toHaveAttribute("aria-pressed", "true");
  await expect(legs.first()).toHaveAttribute("aria-pressed", "false");
  await whole.click();
  await expect(whole).toBeHidden();
  await expect(legs.nth(2)).toHaveAttribute("aria-pressed", "false");

  await page.getByRole("button", { name: "חזרה" }).click();
  await expect(page).toHaveURL(/#\/compare$/);
  await expect(optionList(page).getByRole("button").nth(1)).toHaveAttribute("aria-pressed", "true");
});

test("route details: the star saves the destination, יוצאים לדרך opens navigation", async ({ page }) => {
  await openCompare(page);
  await expect(optionList(page).getByRole("button")).toHaveCount(3);
  await detailsButton(page).click();
  const star = page.getByRole("button", { name: "שמירת היעד" });
  await expect(star).toHaveAttribute("aria-pressed", "false");
  await star.click();
  await expect(star).toHaveAttribute("aria-pressed", "true");
  const start = page.getByRole("button", { name: "יוצאים לדרך" });
  await expect(start).toBeInViewport();
  // The whole timeline scrolls clear of the pinned bar.
  await page.locator("main").evaluate((el) => el.scrollTo(0, el.scrollHeight));
  const last = (await page.locator(".compare-timeline > *").last().boundingBox())!;
  const bar = (await page.locator(".compare-start").boundingBox())!;
  expect(last.y + last.height).toBeLessThanOrEqual(bar.y + 1);
  await start.click();
  await expect(page).toHaveURL(/#\/navigate$/);
});

test("the time chip opens an inline picker; a quick +30 re-plans", async ({ page }) => {
  const bodies: Record<string, unknown>[] = [];
  page.on("request", (request) => {
    if (request.method() === "POST" && new URL(request.url()).pathname === "/v1/journeys") bodies.push(request.postDataJSON());
  });
  await openCompare(page);
  await expect(optionList(page).getByRole("button")).toHaveCount(3);
  await page.getByRole("button", { name: /^שינוי השעה: יציאה 08:00/ }).click();
  const panel = page.getByRole("form", { name: "מתי יוצאים?" });
  await expect(panel).toBeVisible();
  await expect(panel.getByLabel("שעה", { exact: true })).toHaveValue("08:00");
  await expectNoSeriousAxeViolations(page, "compare time picker");
  await panel.getByRole("button", { name: "30 דקות מאוחר יותר" }).click();
  await panel.getByRole("button", { name: "הצגת אפשרויות" }).click();
  await expect(panel).toBeHidden();
  await expect(page.getByRole("button", { name: /^שינוי השעה: יציאה 08:30/ })).toBeVisible();
  await expect.poll(() => bodies.at(-1)?.departAt).toBe("2026-10-01T08:30:00+03:00");
});

test("no route is a calm result with Earlier, Later and change time", async ({ page }) => {
  await openCompare(page, "compare-no-route");
  await expect(page.getByText("לא נמצא מסלול")).toBeVisible();
  await expect(page.getByRole("alert")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "מוקדם יותר" })).toBeEnabled();
  await expect(page.getByRole("button", { name: "מאוחר יותר" })).toBeEnabled();
  await page.getByRole("button", { name: "שינוי השעה", exact: true }).click();
  await expect(page.getByLabel("שעה", { exact: true })).toBeVisible();
  await expectNoSeriousAxeViolations(page, "compare no route");
});

test("no start yet: a calm question with a way to choose one", async ({ page }) => {
  await openCompare(page, null, { ...draft, from: null, when: { mode: "now" } });
  await expect(page.getByText("מאיפה יוצאים?")).toBeVisible();
  await expect(page.getByRole("alert")).toHaveCount(0);
  await expect(page.getByRole("link", { name: "בחירת נקודת מוצא" })).toHaveAttribute("href", "#/search/from");
  await expectNoSeriousAxeViolations(page, "compare no start");
});

test("outside the service window shows the coverage dates", async ({ page }) => {
  await openCompare(page, "compare-outside-window");
  await expect(page.getByRole("alert")).toContainText(/מחוץ ללוח הזמנים. אפשר לבחור בין/);
  await expect(page.getByRole("button", { name: "שינוי השעה", exact: true })).toBeVisible();
});

test("unavailable offers a retry that replaces the error with options", async ({ page }) => {
  await openCompare(page, "compare-unavailable-once");
  await expect(page.getByRole("alert")).toContainText("השירות אינו זמין זמנית");
  await expectNoSeriousAxeViolations(page, "compare unavailable");
  await page.getByRole("button", { name: "נסו שוב" }).click();
  await expect(optionList(page).getByRole("button")).toHaveCount(3);
  await expect(page.getByRole("alert")).toHaveCount(0);
});

test("English: left to right, no serious axe violations", async ({ page }) => {
  await blockExternal(page);
  await page.goto(appPath("#/settings"));
  await page.getByLabel("English").check();
  await page.evaluate((value) => sessionStorage.setItem("opentransit:plan", value), JSON.stringify(draft));
  await page.goto(appPath("#/compare"));
  await page.reload();
  const options = optionList(page).getByRole("button");
  await expect(options).toHaveCount(3);
  await expect(options.first()).toHaveAccessibleName(/^Option 1, 105 minutes, departs 08:07, arrives 09:52, 2 transfers, lines: 8, Train, 1/);
  const times = options.first().locator(".b-op__time bdi");
  expect((await times.first().boundingBox())!.x).toBeLessThan((await times.last().boundingBox())!.x);
  await expectNoSeriousAxeViolations(page, "compare choose (en)");
  await page.getByRole("button", { name: "Route details" }).click();
  await expect(page.getByRole("region", { name: /Route details/ }).getByText("רכבת ישראל", { exact: true })).toBeVisible();
  await expectNoSeriousAxeViolations(page, "compare route details (en)");
});

test("light theme: Choose, route details and the time picker pass axe, and the options still fit", async ({ page }) => {
  await openCompare(page, null, draft, "light");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  const options = optionList(page).getByRole("button");
  await expect(options).toHaveCount(3);
  const bar = (await page.locator(".compare-start").boundingBox())!;
  for (let i = 0; i < 3; i += 1) {
    const box = (await options.nth(i).boundingBox())!;
    expect(box.y + box.height, `option ${i + 1} above פרטי המסלול`).toBeLessThanOrEqual(bar.y + 1);
  }
  await expectNoSeriousAxeViolations(page, "compare choose (he, light)");
  const chip = page.getByRole("button", { name: /^שינוי השעה: יציאה 08:00/ });
  await chip.click();
  await expect(page.getByRole("form", { name: "מתי יוצאים?" })).toBeVisible();
  await expectNoSeriousAxeViolations(page, "compare time picker (light)");
  await chip.click();
  await detailsButton(page).click();
  await expect(legButtons(page).first()).toBeVisible();
  await expectNoSeriousAxeViolations(page, "compare route details (he, light)");
});

for (const [label, scenario, plan, shown] of [
  ["no route", "compare-no-route", draft, "לא נמצא מסלול"],
  ["unavailable", "compare-unavailable", draft, "השירות אינו זמין זמנית."],
  ["rate limited", "compare-rate-limited", draft, "יותר מדי בקשות."],
  ["no start", null, { ...draft, from: null, when: { mode: "now" } }, "מאיפה יוצאים?"],
] as const) {
  test(`light theme: ${label} passes axe`, async ({ page }) => {
    await openCompare(page, scenario, plan, "light");
    await expect(page.getByText(shown, { exact: true })).toBeVisible();
    await expectNoSeriousAxeViolations(page, `compare ${label} (light)`);
  });
}
