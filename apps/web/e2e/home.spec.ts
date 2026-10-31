import { readFileSync } from "node:fs";
import { expect, test, type Page } from "@playwright/test";
import { appPath, blockExternal, expectNoSeriousAxeViolations, useScenario } from "./helpers";

// Home — C01 at 360 × 640, mocked (fixtures mode).

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

test.beforeEach(async ({ page }) => {
  await blockExternal(page);
});

test("first launch (Hebrew): From is my location, set-Home/Work chips, no prompts", async ({ page }) => {
  let prompted = false;
  page.on("dialog", () => void (prompted = true));
  await page.goto(appPath("#/"));
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("תכנון נסיעה");
  await expect(page.getByRole("button", { name: "מאיפה? המיקום שלי" })).toBeVisible();
  await expect(page.getByRole("button", { name: "לאן?" })).toBeVisible();
  await expect(page.getByRole("button", { name: /הגדרת בית/ })).toBeVisible();
  await expect(page.getByRole("button", { name: /הגדרת עבודה/ })).toBeVisible();
  await expect(page.getByText("יעדים שתבחרו יופיעו כאן.")).toBeVisible();
  await expect(page.getByText("נתוני בדיקה — לא לוח הזמנים האמיתי")).toBeVisible();
  expect(prompted).toBe(false);
  await expectNoSeriousAxeViolations(page, "Home, first launch (he)");
});

test("with saved places (English): a chip goes straight to Compare", async ({ page }) => {
  await seed(page, "en", true);
  await page.goto(appPath("#/"));
  await expect(page.locator("html")).toHaveAttribute("dir", "ltr");
  await expect(page.getByRole("button", { name: "Technion" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Dizengoff Center/Dizengoff" })).toBeVisible();
  await expectNoSeriousAxeViolations(page, "Home, saved places (en)");
  await page.getByRole("button", { name: "Home", exact: true }).click();
  await expect(page).toHaveURL(/#\/compare$/);
  const draft = await page.evaluate(() => JSON.parse(sessionStorage.getItem("opentransit:plan") ?? "null"));
  expect(draft.to.place.label).toBe("דיזנגוף 50, תל־אביב–יפו");
  expect(page.url()).not.toContain("32.07");
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

test("location refused: From starts empty, Locate is hidden, and a destination asks for the start next", async ({ page }) => {
  await page.goto(appPath("#/"));
  await denyLocation(page);
  await page.reload();
  await expect(page.getByRole("button", { name: "מאיפה?", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: /המיקום שלי/ })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "מרכוז המפה על המיקום שלי" })).toHaveCount(0);
  await expectNoSeriousAxeViolations(page, "Home, location refused (he)");

  await page.getByRole("button", { name: "לאן?" }).click();
  await page.getByRole("searchbox").fill("דיזנגוף");
  await page.getByTestId("search-results").getByRole("button").first().click();
  // No start yet: Search asks for it in the same entry, and says why "My location" is not offered.
  await expect(page).toHaveURL(/#\/search\/from$/);
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("מאיפה?");
  await expect(page.getByText("לא זמין: אין הרשאה למיקום. אפשר לאשר אותה בהגדרות הדפדפן")).toBeVisible();
  await expectNoSeriousAxeViolations(page, "Search From, location refused (he)");
  await page.getByRole("searchbox").fill("דיזנגוף");
  await page.getByTestId("search-results").getByRole("button").nth(1).click();
  await expect(page).toHaveURL(/#\/compare$/);
  await page.getByRole("button", { name: "חזרה" }).click();
  await expect(page).toHaveURL(/#\/$/);

  // Next visit: the plan starts from the start chosen last time.
  await page.evaluate(() => sessionStorage.removeItem("opentransit:plan"));
  await page.reload();
  await expect(page.getByRole("button", { name: /^מאיפה\? דיזנגוף סנטר/ })).toBeVisible();
});

test("an active trip: a resume card first in the sheet, fully visible at half (axe)", async ({ page }) => {
  const recorded = JSON.parse(
    readFileSync(new URL("../src/nav/testdata/recorded-oct31a-dizengoff-technion.json", import.meta.url), "utf8"),
  ) as { journeys: { data: { journeys: unknown[] }; meta: unknown } };
  const trip = {
    version: 1,
    journey: recorded.journeys.data.journeys[0],
    meta: recorded.journeys.meta,
    trips: {},
    startedAt: "2026-10-31T10:00:00.000Z",
    nav: { stepIndex: 0 },
    labels: { origin: "דיזנגוף סנטר", destination: "טכניון" },
  };
  await page.addInitScript((value) => sessionStorage.setItem("opentransit:activeTrip", value), JSON.stringify(trip));
  await page.goto(appPath("#/"));
  const resume = page.getByRole("button", { name: "חזרה לניווט" });
  await expect(resume).toBeVisible();
  await expect(resume).toContainText(/נסיעה פעילה אל טכניון · הגעה \d\d:\d\d/);
  const card = (await resume.boundingBox())!;
  const sheet = (await page.locator(".sheet").boundingBox())!;
  expect(card.y).toBeGreaterThan(sheet.y);
  expect(card.y + card.height).toBeLessThan(sheet.y + sheet.height);
  const fromTo = (await page.getByRole("group", { name: "מוצא ויעד" }).boundingBox())!;
  expect(card.y).toBeLessThan(fromTo.y);
  await expectNoSeriousAxeViolations(page, "Home, active trip (he)");
  await resume.click();
  await expect(page).toHaveURL(/#\/navigate$/);
});

test("no scheduled-times footnote on Home; Settings is the gear in the sheet's top row", async ({ page }) => {
  await page.goto(appPath("#/"));
  await expect(page.getByText("זמנים בזמן אמת והתראות אינם זמינים")).toHaveCount(0);
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
});
