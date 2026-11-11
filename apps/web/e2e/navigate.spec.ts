import { readFileSync } from "node:fs";
import { expect, test, type Locator, type Page } from "@playwright/test";
import { appPath, blockExternal, expectNoSeriousAxeViolations, useScenario, useTheme } from "./helpers";

// Navigate — C05 as boards 4–6 (11 November 2026), at 360 × 640, mocked (fixtures mode).
// The active trip is seeded from the recorded oct31a journeys (src/nav/testdata); positions
// come from the simulated source. "Bus didn't come" answers are DERIVED in code
// (src/mocks/navigateMissed.ts) under the fixture scenario "navigate-missed".

interface Recorded {
  journeys: {
    data: {
      journeys: Array<{
        legs: Array<{ transit: { engineTripId: string } | null }>;
      }>;
    };
    meta: unknown;
  };
  trips: Record<string, unknown>;
}
const recorded = JSON.parse(
  readFileSync(new URL("../src/nav/testdata/recorded-oct31a-dizengoff-technion.json", import.meta.url), "utf8"),
) as Recorded;

function activeTrip(index: number, nav: Record<string, unknown> = { stepIndex: 0 }) {
  const journey = recorded.journeys.data.journeys[index]!;
  const refs = journey.legs.flatMap((leg) => (leg.transit ? [leg.transit.engineTripId] : []));
  return {
    version: 1,
    journey,
    meta: recorded.journeys.meta,
    trips: Object.fromEntries(refs.map((ref) => [ref, recorded.trips[ref]])),
    startedAt: "2026-10-31T10:00:00.000Z",
    nav,
    labels: { origin: "Dizengoff Center", destination: "Technion" },
  };
}

/** Seed the trip once per tab (a reload keeps what the app stored since). */
async function seed(page: Page, index: number, lang: "he" | "en" = "he", nav?: Record<string, unknown>): Promise<void> {
  const local = {
    version: 1,
    settings: { lang },
    home: null,
    work: null,
    favourites: [],
    recents: [],
  };
  await page.addInitScript(
    ([trip, state]) => {
      if (sessionStorage.getItem("e2e-seeded")) return;
      sessionStorage.setItem("opentransit:activeTrip", trip);
      localStorage.setItem("opentransit", state);
      sessionStorage.setItem("e2e-seeded", "1");
    },
    [JSON.stringify(activeTrip(index, nav)), JSON.stringify(local)] as const,
  );
}

/** A stored engine state on journey 2's first ride with a get-off cue showing (location off). */
function cueState(cue: "two_stops" | "next_stop") {
  return {
    stepIndex: 1,
    phase: cue === "two_stops" ? "cue_two" : "cue_next",
    cue,
    stopsLeft: cue === "two_stops" ? 2 : 1,
    locationMode: "manual",
    lastFixAt: null,
    locationLost: false,
    nearBoarding: false,
    autoSince: null,
  };
}

const answer = (page: Page) => page.locator(".nav-answer, .nav-missed");
const title = (page: Page) => page.getByRole("heading", { level: 1 });
const primary = (page: Page) => page.locator(".nav-primary");
const sheet = (page: Page) => page.locator(".sheet");
const rows = (page: Page) => page.getByRole("list", { name: "כל השלבים" }).getByRole("button");
const closeButton = (page: Page) => page.getByRole("button", { name: "יציאה מהניווט" });

async function expectFullyVisible(page: Page, locator: Locator): Promise<void> {
  await expect(locator).toBeInViewport({ ratio: 1 });
  const box = (await locator.boundingBox())!;
  const viewport = page.viewportSize()!;
  expect(box.y).toBeGreaterThanOrEqual(0);
  expect(box.y + box.height).toBeLessThanOrEqual(viewport.height);
}

/** The one answer and its actions in view above the sheet's bottom; the floats over the map, clear of the sheet. */
async function expectPanel(page: Page): Promise<void> {
  await expectFullyVisible(page, answer(page));
  await expectFullyVisible(page, primary(page));
  const sheetBox = (await sheet(page).boundingBox())!;
  const close = closeButton(page);
  if ((await close.count()) > 0) {
    await expectFullyVisible(page, close);
    const box = (await close.boundingBox())!;
    expect(box.width).toBeGreaterThanOrEqual(44);
    expect(box.height).toBeGreaterThanOrEqual(44);
    expect(box.y + box.height).toBeLessThan(sheetBox.y);
  }
}

/** Open Navigate and wait for its lazy screen (a cold dev server under parallel workers is slow). */
async function gotoNavigate(page: Page): Promise<void> {
  await page.goto(appPath("#/navigate"));
  await expect(answer(page)).toBeVisible({ timeout: 30_000 });
}

async function openFullSheet(page: Page): Promise<void> {
  for (let i = 0; i < 3 && (await sheet(page).getAttribute("data-snap")) !== "full"; i += 1) {
    await page.locator(".sheet-handle").click();
  }
  await expect(sheet(page)).toHaveAttribute("data-snap", "full");
}

test.beforeEach(async ({ page }) => {
  await blockExternal(page);
  // The recorded journeys are dated 2 November 2026: navigate as a passenger would, just
  // before journey 2 leaves (08:35). Time still flows from here.
  await page.clock.install({ time: new Date("2026-11-02T08:30:00+02:00") });
});

test("walking (board 4): the panel shrinks to one answer, the map above it; 'עליתי' → on board (board 5); 'ירדתי' goes on; reload restores", async ({
  page,
}) => {
  await seed(page, 2);
  await gotoNavigate(page);
  await expect(title(page)).toHaveText("דיזנגוף סנטר/טשרניחובסקי");
  await expect(answer(page).locator(".nav-kicker")).toHaveText("הולכים אל");
  await expect(answer(page).locator(".nav-check")).toContainText("מספיקים");
  await expect(answer(page).locator(".nav-check")).toContainText("לפי הלוח 08:38");
  // The sheet is sized to the answer: most of the screen is map.
  const sheetBox = (await sheet(page).boundingBox())!;
  expect(sheetBox.y).toBeGreaterThanOrEqual(page.viewportSize()!.height * 0.4);
  await expect(page.locator(".nav-float--end")).toHaveText("מגיעים 10:37");
  await expect(page.locator(".nav-actions").getByRole("button")).toHaveText(["לא הגיע?", "עליתי"]);
  await expectPanel(page);
  await expectNoSeriousAxeViolations(page, "Navigate, walking (he)");

  await page.getByRole("button", { name: "עליתי" }).click();
  await expect(title(page)).toHaveText(/^יורדים בעוד\s*8 תחנות$/);
  await expect(answer(page).locator(".nav-ride-line")).toContainText("249");
  const stops = page.getByRole("list", { name: "התחנות עד הירידה" }).getByRole("listitem");
  await expect(stops.last()).toContainText("ת. רכבת תל אביב - סבידור/דרך נמיר");
  await expect(stops.last()).toContainText("יורדים");
  await expect(answer(page).locator(".nav-after")).toContainText("אחר כך");
  await expect(page.locator("[aria-live='polite']")).toContainText("שלב 2 מתוך 12");
  await expectPanel(page);
  await expectNoSeriousAxeViolations(page, "Navigate, on board (he)");

  await page.getByRole("button", { name: "ירדתי" }).click();
  await expect(answer(page).locator(".nav-kicker")).toHaveText("מעבר באותה תחנה");

  await page.reload();
  await expect(answer(page)).toBeVisible({ timeout: 30_000 });
  await expect(answer(page).locator(".nav-kicker")).toHaveText("מעבר באותה תחנה");
  await expect(rows(page).nth(2)).toHaveAttribute("aria-current", "step");
  await expectPanel(page);
});

test("bus didn't come (board 6): both choices with their arrival times; choosing one switches the trip", async ({ page }) => {
  await useScenario(page, "navigate-missed");
  await seed(page, 2);
  await gotoNavigate(page);
  await page.getByRole("button", { name: "לא הגיע?" }).click();
  await expect(title(page)).toHaveText("ה־249 עוד לא הגיע");
  const walk = page.getByRole("button", { name: /הולכים ל־8/ });
  const wait = page.getByRole("button", { name: /מחכים כאן ל־249/ });
  await expect(walk).toContainText("3 דק׳ הליכה · יוצא 08:45");
  await expect(walk).toContainText("10:40");
  await expect(wait).toContainText("הבא 08:58");
  await expect(wait).toContainText("10:57");
  await expect(walk).toHaveClass(/b-choice--on/);
  await expectFullyVisible(page, page.getByRole("button", { name: "הגיע, עליתי" }));
  await expectNoSeriousAxeViolations(page, "Navigate, bus didn't come (he)");

  await walk.click();
  await expect(answer(page).locator(".nav-kicker")).toHaveText("הולכים אל");
  await expect(title(page)).toHaveText("דיזנגוף סנטר/דיזנגוף");
  await expect(page.locator(".nav-float--end")).toHaveText("מגיעים 10:40");
});

test("simulated positions: the sheet drops to half, labelled as simulated, and advance through the first steps", async ({ page }) => {
  await seed(page, 2);
  await gotoNavigate(page);
  await expect(title(page)).toHaveText("דיזנגוף סנטר/טשרניחובסקי");
  await openFullSheet(page);
  await page.getByRole("combobox", { name: "מהירות ההדמיה" }).selectOption("120");
  await page.getByRole("checkbox", { name: "מיקום מדומה (בדיקה)" }).check();
  await expect(sheet(page)).not.toHaveAttribute("data-snap", "full");
  const banner = page.locator(".nav-banner-sim");
  await expect(banner).toContainText(/מיקום מדומה, לא אמיתי · שעון \d\d:\d\d · פי 120/);
  const current = () => rows(page).evaluateAll((list) => list.findIndex((row) => row.getAttribute("aria-current") === "step"));
  await expect.poll(current, { timeout: 15_000, intervals: [100] }).toBeGreaterThanOrEqual(1);
  await expect.poll(current, { timeout: 15_000, intervals: [100] }).toBeGreaterThanOrEqual(2);
  await expectFullyVisible(page, banner);
  await expectFullyVisible(page, answer(page));
  await expect(rows(page).nth(0)).toHaveAccessibleName(/^הושלם: 08:35 /);
});

for (const theme of ["dark", "light"] as const) {
  test(`${theme} theme: walking, on board, bus didn't come and the full checklist pass axe`, async ({ page }) => {
    await useScenario(page, "navigate-missed");
    await seed(page, 2);
    await useTheme(page, theme);
    await gotoNavigate(page);
    await expect(page.locator("html")).toHaveAttribute("data-theme", theme);
    await expect(title(page)).toHaveText("דיזנגוף סנטר/טשרניחובסקי");
    await expectPanel(page);
    await expectNoSeriousAxeViolations(page, `Navigate, walking (${theme})`);

    await page.getByRole("button", { name: "לא הגיע?" }).click();
    await expect(page.getByRole("button", { name: /מחכים כאן ל־249/ })).toContainText("10:57");
    await expectNoSeriousAxeViolations(page, `Navigate, bus didn't come (${theme})`);

    await page.getByRole("button", { name: "הגיע, עליתי" }).click();
    await expect(title(page)).toHaveText(/^יורדים בעוד/);
    await expectPanel(page);
    await expectNoSeriousAxeViolations(page, `Navigate, on board (${theme})`);

    await openFullSheet(page);
    await expect(rows(page)).toHaveCount(12);
    await expect(page.getByRole("button", { name: "יציאה מהניווט" })).toHaveClass(/nav-end-full/);
    await expectNoSeriousAxeViolations(page, `Navigate, checklist, full (${theme})`);
  });

  test(`${theme} theme: get-off cues change the answer's words and pass axe`, async ({ page }) => {
    await seed(page, 2, "he", cueState("next_stop"));
    await useTheme(page, theme);
    await gotoNavigate(page);
    await expect(answer(page)).toHaveAttribute("data-cue", "next_stop");
    await expect(answer(page).locator(".nav-kicker")).toHaveText("רדו בתחנה הבאה");
    await expect(answer(page).locator(".b-answer__figure")).toHaveText("תחנה אחת");
    await expect(page.getByRole("status")).toContainText("השלבים מתקדמים ידנית");
    await expectPanel(page);
    await expectNoSeriousAxeViolations(page, `Navigate, cue next stop (${theme})`);

    await page.evaluate((state) => {
      const trip = JSON.parse(sessionStorage.getItem("opentransit:activeTrip")!);
      sessionStorage.setItem("opentransit:activeTrip", JSON.stringify({ ...trip, nav: state }));
    }, cueState("two_stops"));
    await page.reload();
    await expect(answer(page)).toBeVisible({ timeout: 30_000 });
    await expect(answer(page)).toHaveAttribute("data-cue", "two_stops");
    await expect(answer(page).locator(".nav-kicker")).toHaveText("רדו בעוד 2 תחנות");
    await expect(answer(page).locator(".b-answer__figure")).toHaveText("2 תחנות");
    await expectNoSeriousAxeViolations(page, `Navigate, cue two stops (${theme})`);
  });
}

test("English, time-only transfer; the close button returns Home with no resume row", async ({ page }) => {
  await seed(page, 1, "en");
  await gotoNavigate(page);
  await expect(page.locator("html")).toHaveAttribute("dir", "ltr");
  await openFullSheet(page);
  await page.getByRole("list", { name: "All steps" }).getByRole("button").nth(3).click();
  await expect(answer(page)).toContainText("no street path available");
  await expect(answer(page)).not.toContainText(/platform/i);
  await expectNoSeriousAxeViolations(page, "Navigate, time-only transfer (en)");
  await page.getByRole("button", { name: "Exit navigation" }).click();
  await expect(page).toHaveURL(/#\/$/);
  await expect(page.getByRole("button", { name: /Active trip/ })).toHaveCount(0);
  expect(await page.evaluate(() => sessionStorage.getItem("opentransit:activeTrip"))).toBeNull();
});
