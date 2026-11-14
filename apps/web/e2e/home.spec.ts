import { readFileSync } from "node:fs";
import { expect, test, type Page } from "@playwright/test";
import { appPath, blockExternal, expectNoSeriousAxeViolations, useScenario, useTheme } from "./helpers";

// Home — board 1 (11 November 2026) at 360 × 640, mocked (fixtures mode): the search
// field, Home and Work, the stops near the passenger as pins carrying their next departure,
// and the selected stop's departures.

const saved = (id: string, label: string, latitude: number, longitude: number) => ({
  id,
  label,
  latitude,
  longitude,
  stopId: null,
  placeRefHint: null,
  savedAt: "2026-10-31T10:00:00+02:00",
});

async function seed(page: Page, lang: "he" | "en", withPlaces: boolean): Promise<void> {
  const state = {
    version: 1,
    settings: { lang },
    home: withPlaces ? saved("home", "דיזנגוף 50, תל־אביב–יפו", 32.075215, 34.775697) : null,
    work: null,
    favourites: withPlaces ? [saved("fav-1", "Technion", 32.7767, 35.0231)] : [],
    recents: withPlaces ? [saved("32.07557,34.77512", "Dizengoff Center/Dizengoff", 32.075566, 34.77512)] : [],
  };
  await page.addInitScript((value) => {
    if (!sessionStorage.getItem("seeded")) {
      localStorage.setItem("opentransit", value);
      sessionStorage.setItem("seeded", "1");
    }
  }, JSON.stringify(state));
}

/** A position the passenger already allowed (Dizengoff Center, a corpus point). */
async function allowLocation(page: Page): Promise<void> {
  await page.context().grantPermissions(["geolocation"]);
  await page.context().setGeolocation({ latitude: 32.0753, longitude: 34.7749, accuracy: 20 });
}

function activeTrip() {
  const recorded = JSON.parse(
    readFileSync(new URL("../src/nav/testdata/recorded-oct31a-dizengoff-technion.json", import.meta.url), "utf8"),
  ) as { journeys: { data: { journeys: unknown[] }; meta: unknown } };
  return {
    version: 1,
    journey: recorded.journeys.data.journeys[0],
    meta: recorded.journeys.meta,
    trips: {},
    startedAt: "2026-10-31T10:00:00.000Z",
    nav: { stepIndex: 0 },
    labels: { origin: "דיזנגוף סנטר", destination: "טכניון" },
  };
}

const nearest = "דיזנגוף סנטר/דיזנגוף";
/** Pins and tags are drawn once the map has loaded, which can take a while under parallel runs. */
const MAP_READY_MS = 20_000;
/** "Near you" (board 1, 14 November 2026): each line's next departure across the nearby stops. */
const nearHeading = (page: Page) => page.getByRole("heading", { level: 2, name: "קרוב אליך" });
const nearRows = (page: Page) => page.getByRole("list", { name: "הקווים הקרובים אליך" }).getByRole("button");

test.beforeEach(async ({ page }) => {
  await blockExternal(page);
});

test("first launch (Hebrew): the search field, Home and Work to set, the lines near you, no prompts", async ({ page }) => {
  let prompted = false;
  page.on("dialog", () => void (prompted = true));
  await page.goto(appPath("#/"));
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("תכנון נסיעה");
  await expect(page.getByRole("button", { name: "לאן נוסעים?" })).toBeVisible();
  await expect(page.getByRole("button", { name: "הגדרת בית" })).toBeVisible();
  await expect(page.getByRole("button", { name: "הגדרת עבודה" })).toBeVisible();
  await expect(page.getByText("מקום, תחנה או קו")).toBeVisible();
  await expect(nearHeading(page)).toBeVisible();
  await expect(page.getByText("עד 5 דק׳ הליכה")).toBeVisible();
  const rows = nearRows(page);
  await expect(rows).toHaveCount(6);
  await expect(rows.first()).toContainText(/172\s*מסוף רדינג\s*דיזנגוף סנטר\/דיזנגוף · 1 דק׳ הליכה\s*2 דק׳/);
  await expect(page.getByText("זמנים לפי לוח הזמנים")).toBeAttached();
  await expect(page.getByText("נתוני בדיקה — לא לוח הזמנים האמיתי")).toBeVisible();
  // The stops are pins on the map, the selected one carrying its next departure.
  await expect(page.getByRole("button", { name: `פתיחת התחנה ${nearest}, קו 172 בעוד 2 דק׳` })).toBeAttached({ timeout: MAP_READY_MS });
  await expect(page.getByRole("button", { name: "172 2 דק׳", exact: true })).toBeVisible({ timeout: MAP_READY_MS });
  expect(prompted).toBe(false);
  await expectNoSeriousAxeViolations(page, "Home, first launch (he)");
});

test("the search field opens Where to; an unset card opens Search to save the place", async ({ page }) => {
  await page.goto(appPath("#/"));
  await page.getByRole("button", { name: "לאן נוסעים?" }).click();
  await expect(page).toHaveURL(/#\/search\/to$/);
  await page.getByRole("button", { name: "חזרה" }).click();
  await page.getByRole("button", { name: "הגדרת עבודה" }).click();
  await expect(page).toHaveURL(/#\/search\/work$/);
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("הגדרת עבודה");
});

test("with saved places (English): a card goes straight to Compare", async ({ page }) => {
  await seed(page, "en", true);
  await page.goto(appPath("#/"));
  await expect(page.locator("html")).toHaveAttribute("dir", "ltr");
  await expect(page.getByRole("button", { name: "Home", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Set Work" })).toBeVisible();
  await expect(page.getByRole("heading", { level: 2, name: "Near you" })).toBeVisible();
  await expectNoSeriousAxeViolations(page, "Home, saved places (en)");
  await page.getByRole("button", { name: "Home", exact: true }).click();
  await expect(page).toHaveURL(/#\/compare$/);
  const draft = await page.evaluate(() => JSON.parse(sessionStorage.getItem("opentransit:plan") ?? "null"));
  expect(draft.to.place.label).toBe("דיזנגוף 50, תל־אביב–יפו");
  expect(page.url()).not.toContain("32.07");
});

test("location allowed: each line's walk to its stop; one tap on a pin opens its stop (axe)", async ({ page }) => {
  await allowLocation(page);
  await page.goto(appPath("#/"));
  await expect(nearRows(page).first()).toContainText(new RegExp(`${nearest} · \\d+ דק׳ הליכה`));
  await expectNoSeriousAxeViolations(page, "Home, location allowed (he)");

  // Pins sit close together and under tags: use the keyboard, as a screen reader would.
  await page.getByRole("button", { name: /^פתיחת התחנה דיזנגוף סנטר\/טשרניחובסקי, קו 66 בעוד \d+ דק׳$/ }).press("Enter");
  await expect(page).toHaveURL(/#\/stop\/mot%3Astop%3A13560$/);
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("דיזנגוף סנטר/טשרניחובסקי");
});

test("a line row opens its stop with that line's route shown", async ({ page }) => {
  await page.goto(appPath("#/"));
  const row = nearRows(page).first();
  await expect(row).toContainText(/^172/);
  await row.click();
  await expect(page).toHaveURL(/#\/stop\/mot%3Astop%3A13583$/);
  await expect(page.getByRole("button", { pressed: true })).toContainText("מסוף רדינג");
});

test("saved stops and lines sit after Home and Work with their next departure; a line card opens the line", async ({ page }) => {
  await page.addInitScript((value) => {
    if (!sessionStorage.getItem("seeded")) {
      localStorage.setItem("opentransit", value);
      sessionStorage.setItem("seeded", "1");
    }
  }, JSON.stringify({
    version: 2,
    settings: { lang: "he" },
    home: null,
    work: null,
    favourites: [],
    recents: [],
    savedStops: [{ stopId: "mot:stop:13583", name: "דיזנגוף סנטר", code: "25609", latitude: 32.075566, longitude: 34.77512, mode: "bus", savedAt: "2026-11-14T10:00:00Z" }],
    savedLines: [{ lineKey: "5:10008", shortName: "8", operatorId: "5", operatorName: "דן", mode: "bus", destinationName: "מסוף הטייסים", originName: "מסוף רידינג", routeIdHint: null, area: "תל אביב-יפו", stopId: "mot:stop:13561", stopName: "דיזנגוף סנטר", savedAt: "2026-11-14T10:00:00Z" }],
  }));
  await page.goto(appPath("#/"));
  const saved = page.getByRole("region", { name: "מקומות שמורים" }).getByRole("button");
  await expect(saved).toHaveCount(4);
  await expect(saved.nth(2)).toContainText(/^דיזנגוף סנטר\s*172\s*2\s*115\s*5 דק׳$/);
  await expect(saved.nth(3)).toContainText(/^8\s*מסוף הטייסים\s*5 דק׳ · מדיזנגוף סנטר$/);
  await expectNoSeriousAxeViolations(page, "Home, saved stops and lines (he)");
  await saved.nth(3).click();
  await expect(page).toHaveURL(/#\/line\/5%3A10008$/);
});

/** The browser refuses location for this origin (a real "Block", not a fake API). */
async function denyLocation(page: Page): Promise<void> {
  const session = await page.context().newCDPSession(page);
  const { targetInfo } = (await session.send("Target.getTargetInfo")) as { targetInfo: { browserContextId: string } };
  const browser = await page.context().browser()!.newBrowserCDPSession();
  await browser.send("Browser.setPermission", {
    permission: { name: "geolocation" },
    setting: "denied",
    origin: new URL(page.url()).origin,
    browserContextId: targetInfo.browserContextId,
  });
}

test("location refused: Locate is hidden, and a destination asks for the start next", async ({ page }) => {
  await page.goto(appPath("#/"));
  await denyLocation(page);
  await page.reload();
  await expect(nearHeading(page)).toBeVisible();
  await expect(page.getByRole("button", { name: "מרכוז המפה על המיקום שלי" })).toHaveCount(0);
  await expectNoSeriousAxeViolations(page, "Home, location refused (he)");

  await page.getByRole("button", { name: "לאן נוסעים?" }).click();
  await page.getByRole("searchbox").fill("דיזנגוף");
  await page.getByTestId("search-results").getByRole("button").first().click();
  // No start yet: Search asks for it in the same entry, and says why "My location" is not offered.
  await expect(page).toHaveURL(/#\/search\/from$/);
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("מאיפה?");
  await expect(page.getByText("לא זמין: אין הרשאה למיקום. אפשר לאשר אותה בהגדרות הדפדפן")).toBeVisible();
  await expectNoSeriousAxeViolations(page, "Search From, location refused (he)");
  await page.getByRole("searchbox").fill("דיזנגוף");
  await page.getByTestId("search-results").locator(".sx-main, .sx-row").nth(1).click();
  await expect(page).toHaveURL(/#\/compare$/);
  await page.getByRole("button", { name: "חזרה" }).click();
  await expect(page).toHaveURL(/#\/$/);

  // Next visit: the plan starts from the start chosen last time.
  await page.evaluate(() => sessionStorage.removeItem("opentransit:plan"));
  await page.reload();
  await expect(nearHeading(page)).toBeVisible();
  const draft = await page.evaluate(() => JSON.parse(sessionStorage.getItem("opentransit:plan") ?? "null"));
  expect(draft.from.place.label).toMatch(/^דיזנגוף סנטר/);
});

test("an active trip: a resume card first in the sheet, fully visible at half (axe)", async ({ page }) => {
  await page.addInitScript((value) => sessionStorage.setItem("opentransit:activeTrip", value), JSON.stringify(activeTrip()));
  await page.goto(appPath("#/"));
  const resume = page.getByRole("button", { name: "חזרה לניווט" });
  await expect(resume).toBeVisible();
  await expect(resume).toContainText(/נסיעה פעילה אל טכניון · הגעה \d\d:\d\d/);
  const card = (await resume.boundingBox())!;
  const sheet = (await page.locator(".sheet").boundingBox())!;
  expect(card.y).toBeGreaterThan(sheet.y);
  expect(card.y + card.height).toBeLessThan(sheet.y + sheet.height);
  const field = (await page.getByRole("button", { name: "לאן נוסעים?" }).boundingBox())!;
  expect(card.y).toBeLessThan(field.y);
  await expectNoSeriousAxeViolations(page, "Home, active trip (he)");
  await resume.click();
  await expect(page).toHaveURL(/#\/navigate$/);
});

test("Settings is the gear in the sheet's top row", async ({ page }) => {
  await page.goto(appPath("#/"));
  const gear = page.getByRole("link", { name: "הגדרות" });
  const box = (await gear.boundingBox())!;
  const sheet = (await page.locator(".sheet").boundingBox())!;
  expect(box.y - sheet.y).toBeLessThan(10);
  expect(box.height).toBeGreaterThanOrEqual(44);
});

test("an expired timetable shows one banner", async ({ page }) => {
  await useScenario(page, "status-expired");
  await page.goto(appPath("#/"));
  await expect(page.getByText("לוח הזמנים פג תוקף ואינו זמין לתכנון")).toBeVisible();
  await expectNoSeriousAxeViolations(page, "Home, expired banner (he)");
});

test("offline: Home still renders and says there is no connection", async ({ page }) => {
  await useScenario(page, "status-offline");
  await page.goto(appPath("#/"));
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("תכנון נסיעה");
  await expect(page.getByText(/^אין חיבור\./)).toBeVisible();
  await expectNoSeriousAxeViolations(page, "Home, offline (he)");
});

// Light theme (dark is the default, and what the tests above run in).

test("light theme: saved places, location allowed and an active trip (axe)", async ({ page }) => {
  await seed(page, "he", true);
  await useTheme(page, "light");
  await allowLocation(page);
  await page.addInitScript((value) => sessionStorage.setItem("opentransit:activeTrip", value), JSON.stringify(activeTrip()));
  await page.goto(appPath("#/"));
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  await expect(page.getByRole("button", { name: "חזרה לניווט" })).toBeVisible();
  await expect(page.getByRole("button", { name: "בית", exact: true })).toBeVisible();
  await expect(nearRows(page).first()).toContainText(/דק׳ הליכה/);
  await expect(page.getByRole("button", { name: "172 2 דק׳", exact: true })).toBeVisible({ timeout: MAP_READY_MS });
  await expectNoSeriousAxeViolations(page, "Home, saved places, location and active trip, light (he)");
});

test("light theme: first launch, an expired timetable, offline (axe)", async ({ page }) => {
  await useTheme(page, "light");
  await page.goto(appPath("#/"));
  await expect(page.getByRole("button", { name: "הגדרת בית" })).toBeVisible();
  await expect(nearHeading(page)).toBeVisible();
  await expect(page.getByText("נתוני בדיקה — לא לוח הזמנים האמיתי")).toBeVisible();
  await expectNoSeriousAxeViolations(page, "Home, first launch, light (he)");

  await useScenario(page, "status-expired");
  await page.reload();
  await expect(page.getByText("לוח הזמנים פג תוקף ואינו זמין לתכנון")).toBeVisible();
  await expectNoSeriousAxeViolations(page, "Home, expired banner, light (he)");

  await useScenario(page, "status-offline");
  await page.reload();
  await expect(page.getByText(/^אין חיבור\./)).toBeVisible();
  await expectNoSeriousAxeViolations(page, "Home, offline, light (he)");
});
