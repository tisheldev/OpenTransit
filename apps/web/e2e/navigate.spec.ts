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

async function expectFullyVisible(page: Page, locator: Locator): Promise<void> {
  await expect(locator).toBeInViewport({ ratio: 1 });
  const box = (await locator.boundingBox())!;
  const viewport = page.viewportSize()!;
  expect(box.y).toBeGreaterThanOrEqual(0);
  expect(box.y + box.height).toBeLessThanOrEqual(viewport.height);
}

test.beforeEach(async ({ page }) => {
  await blockExternal(page);
});

test("step card and Next step fit 360 × 640; Next advances; a row jumps; reload restores (he)", async ({ page }) => {
  await seed(page, 2);
  await page.goto(appPath("#/navigate"));
  await expect(card(page)).toContainText("הליכה אל דיזנגוף סנטר/טשרניחובסקי");
  await expectFullyVisible(page, card(page));
  await expectFullyVisible(page, nextButton(page));
  await expectFullyVisible(page, page.getByRole("button", { name: "סיום הנסיעה" }));
  // Nothing pinned covers the card: it ends above the pinned actions.
  const cardBox = (await card(page).boundingBox())!;
  const actionsBox = (await page.locator(".navigate-actions").boundingBox())!;
  expect(cardBox.y + cardBox.height).toBeLessThanOrEqual(actionsBox.y);
  await expectNoSeriousAxeViolations(page, "Navigate, walk to stop (he)");

  await nextButton(page).click();
  await expect(rows(page).nth(1)).toHaveAttribute("aria-current", "step");
  await expect(card(page)).toContainText("אוטובוס 249");
  await expect(page.locator("[aria-live]")).toContainText("שלב 2 מתוך 12");

  await rows(page).nth(4).click();
  await expect(rows(page).nth(4)).toHaveAttribute("aria-current", "step");
  await expect(card(page)).toContainText("מעבר: הליכה אל צומת אולגה");
  await expectNoSeriousAxeViolations(page, "Navigate, transfer (he)");

  await page.reload();
  await expect(rows(page).nth(4)).toHaveAttribute("aria-current", "step");
  await expect(card(page)).toContainText("מעבר: הליכה אל צומת אולגה");
});

test("simulated positions advance through the first steps, labelled as simulated", async ({ page }) => {
  await seed(page, 2);
  await page.goto(appPath("#/navigate"));
  await page.getByRole("combobox", { name: "מהירות ההדמיה" }).selectOption("600");
  await page.getByRole("checkbox", { name: "מיקום מדומה (בדיקה)" }).check();
  await expect(page.getByText(/מיקום מדומה — לא המיקום האמיתי שלכם/)).toBeVisible();
  await expect(rows(page).nth(1)).toHaveAttribute("aria-current", "step", { timeout: 15_000 });
  await expect(rows(page).nth(2)).toHaveAttribute("aria-current", "step", { timeout: 15_000 });
  await expect(rows(page).nth(0)).toHaveAccessibleName(/^הושלם: /);
});

test("English, time-only transfer; End trip returns Home with no resume row", async ({ page }) => {
  await seed(page, 1, "en");
  await page.goto(appPath("#/navigate"));
  await expect(page.locator("html")).toHaveAttribute("dir", "ltr");
  await page.getByRole("list").getByRole("button").nth(3).click();
  await expect(card(page)).toContainText("no street path available");
  await expect(card(page)).toContainText("Platform unknown");
  await expectNoSeriousAxeViolations(page, "Navigate, time-only transfer (en)");
  await page.getByRole("button", { name: "End trip" }).click();
  await expect(page).toHaveURL(/#\/$/);
  await expect(page.getByRole("button", { name: /Active trip/ })).toHaveCount(0);
  expect(await page.evaluate(() => sessionStorage.getItem("opentransit:activeTrip"))).toBeNull();
});
