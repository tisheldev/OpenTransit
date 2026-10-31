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
