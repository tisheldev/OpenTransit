import { expect, test, type Page } from "@playwright/test";
import { appPath, blockExternal, expectNoSeriousAxeViolations, useScenario as setScenario } from "./helpers";

// Mocked Compare (slice S5): fixtures mode at 360 x 640. The plan draft is written to
// sessionStorage ("opentransit:plan", the PlanDraft shape) before the app starts.

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

async function openCompare(page: Page, scenario: string | null = null, plan: object = draft): Promise<void> {
  await blockExternal(page);
  await setScenario(page, scenario);
  await page.addInitScript((value) => sessionStorage.setItem("opentransit:plan", value), JSON.stringify(plan));
  await page.goto(appPath("#/compare"));
}

const optionList = (page: Page) => page.getByRole("list", { name: /אפשרויות נסיעה|Trip options/ });

test("half sheet: header, time chip and every option fit above the pinned Start", async ({ page }) => {
  await openCompare(page);
  const options = optionList(page).getByRole("button");
  await expect(options).toHaveCount(3);
  await expect(page.locator(".sheet")).toHaveAttribute("data-snap", "half");
  const start = page.getByRole("button", { name: "התחלת ניווט" });
  await expect(start).toBeInViewport();
  const bar = (await page.locator(".compare-start").boundingBox())!;
  // Opaque and full width: nothing shows beside or below it.
  expect(bar.width).toBeGreaterThanOrEqual(359);
  expect(bar.y + bar.height).toBeGreaterThanOrEqual(639);
  await expect(page.getByRole("group", { name: "מוצא ויעד" })).toBeInViewport();
  await expect(page.getByRole("button", { name: /^שינוי השעה: יציאה 08:00/ })).toBeInViewport();
  for (let i = 0; i < 3; i += 1) {
    const box = (await options.nth(i).boundingBox())!;
    expect(box.y).toBeGreaterThan(640 * 0.45 - 1);
    expect(box.y + box.height, `option ${i + 1} above Start`).toBeLessThanOrEqual(bar.y + 1);
  }
  await expectNoSeriousAxeViolations(page, "compare half sheet (he)");
});

test("options: tap the second, details swap without a request, Start opens navigation", async ({ page }) => {
  const journeyRequests: string[] = [];
  page.on("request", (request) => {
    if (request.method() === "POST" && new URL(request.url()).pathname === "/v1/journeys") journeyRequests.push(request.url());
  });
  await openCompare(page);
  const options = optionList(page).getByRole("button");
  await expect(options).toHaveCount(3);
  await expect(options.first()).toHaveAttribute("aria-pressed", "true");
  await expect(options.first()).toHaveAccessibleName("אפשרות 1, מומלץ, 105 דקות, יציאה 08:07, הגעה 09:52, 2 החלפות");
  const details = page.getByRole("region", { name: /פרטי מסלול/ });
  await expect(details.getByText("רכבת ישראל", { exact: true })).toBeVisible();
  await expect(details).not.toContainText("רכבת לחוף הכרמל");
  await expect(details.getByRole("link")).toHaveCount(0);
  const before = journeyRequests.length;

  await options.nth(1).click();
  await expect(options.nth(1)).toHaveAttribute("aria-pressed", "true");
  await expect(details.getByText(/^הליכה כ־2 דק׳$/)).toBeVisible();
  expect(journeyRequests.length).toBe(before);

  // Tapping an option raises the sheet; at 360 x 640 the options and the start of the
  // selected route are both on screen.
  await expect(page.locator(".sheet")).toHaveAttribute("data-snap", "full");
  await expect(options.nth(2)).toBeInViewport();
  await expect(details.locator(".it").first()).toBeInViewport();

  // Hebrew: the earliest time sits on the right of the bar.
  const segments = options.first().locator(".bar-seg");
  const firstBox = await segments.first().boundingBox();
  const lastBox = await segments.last().boundingBox();
  expect(firstBox!.x).toBeGreaterThan(lastBox!.x);

  // The whole itinerary scrolls clear of the pinned Start bar.
  await page.locator("main").evaluate((el) => el.scrollTo(0, el.scrollHeight));
  const last = (await details.locator(".it").last().boundingBox())!;
  const bar = (await page.locator(".compare-start").boundingBox())!;
  expect(last.y + last.height).toBeLessThanOrEqual(bar.y + 1);

  await expectNoSeriousAxeViolations(page, "compare options (he)");

  await page.getByRole("button", { name: "התחלת ניווט" }).click();
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

test("English: left to right, earliest on the left, no serious axe violations", async ({ page }) => {
  await blockExternal(page);
  await page.goto(appPath("#/settings"));
  await page.getByLabel("English").check();
  await page.evaluate((value) => sessionStorage.setItem("opentransit:plan", value), JSON.stringify(draft));
  await page.goto(appPath("#/compare"));
  await page.reload();
  const options = optionList(page).getByRole("button");
  await expect(options).toHaveCount(3);
  await expect(options.first()).toHaveAccessibleName("Option 1, Recommended, 105 minutes, departs 08:07, arrives 09:52, 2 transfers");
  await expect(page.getByRole("region", { name: /Route details/ }).getByText("רכבת ישראל", { exact: true })).toBeVisible();
  const segments = options.first().locator(".bar-seg");
  expect((await segments.first().boundingBox())!.x).toBeLessThan((await segments.last().boundingBox())!.x);
  await expectNoSeriousAxeViolations(page, "compare options (en)");
});
