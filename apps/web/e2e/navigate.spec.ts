import { readFileSync } from "node:fs";
import { expect, test, type Locator, type Page } from "@playwright/test";
import { appPath, blockExternal, expectNoSeriousAxeViolations } from "./helpers";

// Navigate — C05 at 360 × 640, mocked (fixtures mode). The active trip is seeded from the
// recorded oct31a journeys (src/nav/testdata); positions come from the simulated source.

interface Recorded {
  journeys: { data: { journeys: Array<{ legs: Array<{ transit: { engineTripId: string } | null }> }> }; meta: unknown };
  trips: Record<string, unknown>;
}
const recorded = JSON.parse(
  readFileSync(new URL("../src/nav/testdata/recorded-oct31a-dizengoff-technion.json", import.meta.url), "utf8"),
) as Recorded;

function activeTrip(index: number) {
  const journey = recorded.journeys.data.journeys[index]!;
  const refs = journey.legs.flatMap((leg) => (leg.transit ? [leg.transit.engineTripId] : []));
  return {
    version: 1,
    journey,
    meta: recorded.journeys.meta,
    trips: Object.fromEntries(refs.map((ref) => [ref, recorded.trips[ref]])),
    startedAt: "2026-10-31T10:00:00.000Z",
    nav: { stepIndex: 0 },
    labels: { origin: "Dizengoff Center", destination: "Technion" },
  };
}

/** Seed the trip once per tab (a reload keeps what the app stored since). */
async function seed(page: Page, index: number, lang: "he" | "en" = "he"): Promise<void> {
  const local = { version: 1, settings: { lang }, home: null, work: null, favourites: [], recents: [] };
  await page.addInitScript(
    ([trip, state]) => {
      if (sessionStorage.getItem("e2e-seeded")) return;
      sessionStorage.setItem("opentransit:activeTrip", trip);
      localStorage.setItem("opentransit", state);
      sessionStorage.setItem("e2e-seeded", "1");
    },
    [JSON.stringify(activeTrip(index)), JSON.stringify(local)] as const,
  );
}

const card = (page: Page) => page.locator(".step-card");
const nextButton = (page: Page) => page.getByRole("button", { name: "השלב הבא" });
const rows = (page: Page) => page.getByRole("list").getByRole("button");
const sheet = (page: Page) => page.locator(".sheet");

async function expectFullyVisible(page: Page, locator: Locator): Promise<void> {
  await expect(locator).toBeInViewport({ ratio: 1 });
  const box = (await locator.boundingBox())!;
  const viewport = page.viewportSize()!;
  expect(box.y).toBeGreaterThanOrEqual(0);
  expect(box.y + box.height).toBeLessThanOrEqual(viewport.height);
}

/** Card, its "what comes next" and Next step all visible, nothing pinned over the card. */
async function expectCardAndNext(page: Page): Promise<void> {
  await expectFullyVisible(page, card(page));
  await expectFullyVisible(page, nextButton(page));
  const cardBox = (await card(page).boundingBox())!;
  // Nothing of the card is hidden under the pinned action (its padding may overlap).
  const nextBox = (await nextButton(page).boundingBox())!;
  expect(cardBox.y + cardBox.height).toBeLessThanOrEqual(nextBox.y);
}

test.beforeEach(async ({ page }) => {
  await blockExternal(page);
});

test("half sheet: map above, card with what comes next and Next step at 360 × 640; Next advances; a row jumps; reload restores (he)", async ({ page }) => {
  await seed(page, 2);
  await page.goto(appPath("#/navigate"));
  await expect(card(page)).toContainText("הליכה אל דיזנגוף סנטר/טשרניחובסקי");
  // N1: Navigate opens at half; the map (top ~45%) stays visible above the sheet.
  await expect(sheet(page)).toHaveAttribute("data-snap", "half");
  const sheetBox = (await sheet(page).boundingBox())!;
  expect(sheetBox.y).toBeGreaterThan(page.viewportSize()!.height * 0.4);
  // Walk card: the bus to catch and its countdown are in the card (the next step).
  await expect(card(page).locator(".step-vehicle")).toContainText("אוטובוס 249");
  await expectCardAndNext(page);
  // N5: End trip is in the card header, away from the single bottom action; small to the
  // eye, but its hit area is 44 px tall (::after).
  const end = card(page).getByRole("button", { name: "סיום הנסיעה" });
  await expectFullyVisible(page, end);
  await expect(page.locator(".navigate-actions").getByRole("button")).toHaveCount(1);
  const endBox = (await end.boundingBox())!;
  const hitTop = await page.evaluate(
    ([x, y]) => document.elementFromPoint(x!, y!)?.closest(".step-end") !== null,
    [endBox.x + endBox.width / 2, endBox.y + endBox.height / 2 - 21],
  );
  const hitBottom = await page.evaluate(
    ([x, y]) => document.elementFromPoint(x!, y!)?.closest(".step-end") !== null,
    [endBox.x + endBox.width / 2, endBox.y + endBox.height / 2 + 21],
  );
  expect([hitTop, hitBottom]).toEqual([true, true]);
  const nextBox = (await nextButton(page).boundingBox())!;
  expect(nextBox.y - (endBox.y + endBox.height)).toBeGreaterThan(150);
  await expectNoSeriousAxeViolations(page, "Navigate, walk to stop (he)");

  await nextButton(page).click();
  await expect(rows(page).nth(1)).toHaveAttribute("aria-current", "step");
  await expect(card(page)).toContainText("אוטובוס 249");
  // N4: the exit leads; stops are counted to the exit (no positions measured yet).
  await expect(card(page).locator(".step-lead")).toHaveText("ירידה ב־ת. רכבת תל אביב - סבידור/דרך נמיר");
  await expect(card(page)).toContainText("8 תחנות עד הירידה");
  await expect(card(page).locator(".step-then")).toContainText("אחר כך: מעבר לאוטובוס 825");
  await expectCardAndNext(page);
  await expect(page.locator("[aria-live]")).toContainText("שלב 2 מתוך 12");

  // N2: the checklist (drag up) shows each step's scheduled time.
  await page.locator(".sheet-handle").click();
  await expect(sheet(page)).toHaveAttribute("data-snap", "full");
  await expect(rows(page).nth(3).locator(".checklist-time")).toHaveText("08:51");
  await rows(page).nth(4).click();
  await expect(rows(page).nth(4)).toHaveAttribute("aria-current", "step");
  await expect(card(page)).toContainText("מעבר באותה תחנה");
  await expect(card(page)).toContainText("צומת אולגה · תחנה 41694 · 3 דק׳ למעבר");
  await expectNoSeriousAxeViolations(page, "Navigate, same-stop transfer, full sheet (he)");

  await page.reload();
  await expect(rows(page).nth(4)).toHaveAttribute("aria-current", "step");
  await expect(card(page)).toContainText("מעבר באותה תחנה");
  await expect(sheet(page)).toHaveAttribute("data-snap", "half");
  await expectCardAndNext(page);
});

test("simulated positions: the sheet drops to half, labelled as simulated, and advance through the first steps", async ({ page }) => {
  await seed(page, 2);
  await page.goto(appPath("#/navigate"));
  await page.locator(".sheet-handle").click();
  await expect(sheet(page)).toHaveAttribute("data-snap", "full");
  await page.getByRole("combobox", { name: "מהירות ההדמיה" }).selectOption("120");
  await page.getByRole("checkbox", { name: "מיקום מדומה (בדיקה)" }).check();
  // N6: half, so the moving dot is on the map; the compact banner stays in view.
  await expect(sheet(page)).toHaveAttribute("data-snap", "half");
  const banner = page.locator(".nav-banner-sim");
  await expect(banner).toContainText(/מיקום מדומה, לא אמיתי · שעון \d\d:\d\d · פי 120/);
  const current = () => rows(page).evaluateAll((list) => list.findIndex((row) => row.getAttribute("aria-current") === "step"));
  await expect.poll(current, { timeout: 15_000, intervals: [100] }).toBe(1);
  // A same-stop change lasts a second at ×120: wait for "at least the third step".
  await expect.poll(current, { timeout: 15_000, intervals: [100] }).toBeGreaterThanOrEqual(2);
  await expectFullyVisible(page, banner);
  await expectFullyVisible(page, card(page));
  await expect(rows(page).nth(0)).toHaveAccessibleName(/^הושלם: 08:35 /);
});

test("English, time-only transfer, no platform guessed; End trip returns Home with no resume row", async ({ page }) => {
  await seed(page, 1, "en");
  await page.goto(appPath("#/navigate"));
  await expect(page.locator("html")).toHaveAttribute("dir", "ltr");
  await page.locator(".sheet-handle").click();
  await page.getByRole("list").getByRole("button").nth(3).click();
  await expect(card(page)).toContainText("no street path available");
  await expect(card(page)).toContainText("4 min to change");
  await expect(card(page)).not.toContainText(/platform/i);
  await expectNoSeriousAxeViolations(page, "Navigate, time-only transfer (en)");
  await page.getByRole("button", { name: "End trip" }).click();
  await expect(page).toHaveURL(/#\/$/);
  await expect(page.getByRole("button", { name: /Active trip/ })).toHaveCount(0);
  expect(await page.evaluate(() => sessionStorage.getItem("opentransit:activeTrip"))).toBeNull();
});
