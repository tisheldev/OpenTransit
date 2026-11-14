import { expect, test } from "@playwright/test";
import { appPath, blockExternal, expectNoSeriousAxeViolations, useTheme } from "./helpers";

// Stops and lines (canvas boards Stop 3, Line 4, Ride 5 and Journey 6; 14 November 2026)
// at 360 × 640, mocked (fixtures mode; the A2/A3 answers are synthetic, src/mocks/lineFixtures.ts).

const STOP = "#/stop/mot%3Astop%3A13583";

test.beforeEach(async ({ page, context }) => {
  await blockExternal(page);
  // The passenger 40 m from Dizengoff Center.
  await context.grantPermissions(["geolocation"]);
  await context.setGeolocation({ latitude: 32.0753, longitude: 34.7749, accuracy: 20 });
});

test("Stop: save, a line opened in place, all its stops; travel from here (axe)", async ({ page }) => {
  await page.goto(appPath(STOP));
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("דיזנגוף סנטר/דיזנגוף");
  await expect(page.getByText(/40 מ׳ · 1 דק׳ הליכה/)).toBeVisible();
  const star = page.getByRole("button", { name: "שמירת התחנה" });
  await star.click();
  await expect(star).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByRole("img", { name: "התחנה דיזנגוף סנטר/דיזנגוף" })).toBeAttached({ timeout: 20_000 });

  const rows = page.getByRole("list", { name: "הקווים בתחנה" }).locator(".b-row");
  await expect(rows).toHaveCount(6);
  await rows.nth(2).click();
  const times = page.getByRole("group", { name: "הזמנים הבאים של קו 8" });
  await expect(times.locator(".sl-chip").first()).toHaveText(/^\d\d:\d\d$/);
  await expectNoSeriousAxeViolations(page, "Stop, a line opened (he)");
  await times.getByRole("button", { name: "כל התחנות" }).click();
  await expect(page).toHaveURL(/#\/line\/5%3A10008$/);
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("קו 8");

  await page.goBack();
  await expect(page).toHaveURL(/#\/stop\//);
  await page.getByRole("button", { name: "לנסוע מכאן" }).click();
  await expect(page).toHaveURL(/#\/search\/to$/);
});

test("Line: opens at the nearest stop, folds, switches direction, train badge (axe, light too)", async ({ page }) => {
  await page.goto(appPath("#/line/5%3A10008"));
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("קו 8");
  await expect(page.getByText("דן · אוטובוס · כל 12 דק׳ בערך")).toBeVisible();
  const list = page.getByRole("list", { name: "התחנות של הקו" });
  await expect(list.getByRole("button").first()).toHaveText("22 תחנות קודמות · ממסוף הטייסים");
  await expect(list.locator(".sl-sr--on")).toContainText("הכי קרובה אליך · 1 דק׳ הליכה");
  await expectNoSeriousAxeViolations(page, "Line (he)");

  await page.getByRole("button", { name: "למסוף הטייסים" }).click();
  await expect(list.getByRole("button").first()).toHaveText("19 תחנות קודמות · ממסוף אוניברסיטת ת''א/הורדה");
  await expect(list.getByRole("button").nth(5)).toContainText("ת. רכבת השלום");
  await expect(list.getByRole("button").nth(5).locator(".sl-rail")).toHaveText("רכבת");
  await expect(list.getByRole("button").nth(6)).toHaveText("17 תחנות נוספות");
  await list.getByRole("button").nth(6).click();
  await expect(list.getByRole("button")).toHaveCount(1 + 1 + 21 + 1);
  await expect(page.getByText("הקישו על תחנה כדי לרדת בה · זמנים לפי לוח הזמנים")).toBeAttached();
});

test("Line, light theme (axe)", async ({ page }) => {
  await useTheme(page, "light");
  await page.goto(appPath("#/line/5%3A10008"));
  await expect(page.getByRole("list", { name: "התחנות של הקו" }).getByRole("button").first()).toHaveText(/תחנות קודמות/);
  await expectNoSeriousAxeViolations(page, "Line, light (he)");
});

test("Ride it: tap a stop, a pinned journey, choose another departure, start (axe)", async ({ page }) => {
  await page.goto(appPath("#/line/5%3A10008"));
  await page.getByRole("button", { name: "למסוף הטייסים" }).click();
  const list = page.getByRole("list", { name: "התחנות של הקו" });
  await expect(list.getByRole("button").nth(5)).toContainText("ת. רכבת השלום");
  const posted = page.waitForRequest((request) => request.method() === "POST" && request.url().includes("/v1/journeys"));
  await list.getByRole("button").nth(5).click();
  await expect(page).toHaveURL(/#\/ride$/);
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("למסוף הטייסים");
  await expect(page.getByText("מתי עולים בדיזנגוף סנטר/דיזנגוף?")).toBeVisible();
  const body = (await posted).postDataJSON() as { pinnedTrip: { boardStopId: string; alightStopId: string } };
  expect(body.pinnedTrip).toMatchObject({ boardStopId: "mot:stop:13583", alightStopId: "mot:stop:12823" });
  await expect(page.getByText("יורדים כאן · 4 תחנות · 6 דק׳ נסיעה")).toBeVisible();
  await expect(page.getByText(/^\d+ דק׳ · כולל 1 דק׳ הליכה לתחנה$/)).toBeVisible();
  await expectNoSeriousAxeViolations(page, "Ride it (he)");

  const chips = page.getByRole("group", { name: "נסיעות" }).getByRole("button");
  await chips.nth(1).click();
  await expect(chips.nth(1)).toHaveAttribute("aria-pressed", "true");
  await page.getByRole("button", { name: "יוצאים לדרך" }).click();
  await expect(page).toHaveURL(/#\/navigate$/);
});

test("Journey: a ride opens in place to its line's departures; a stop's name opens it (axe)", async ({ page }) => {
  await page.goto(appPath("#/"));
  await page.evaluate(() => {
    const dizengoff = { label: "דיזנגוף סנטר", locality: null, kind: "stop", latitude: 32.0753, longitude: 34.7749, stopId: "mot:stop:13583", placeRef: null, refGenerationId: null };
    const technion = { ...dizengoff, label: "טכניון", kind: "pin", latitude: 32.7767, longitude: 35.0231, stopId: null };
    sessionStorage.setItem(
      "opentransit:plan",
      JSON.stringify({ from: { type: "place", place: dizengoff }, to: { type: "place", place: technion }, when: { mode: "depart_at", wall: "2026-10-01T08:00", offset: "auto" } }),
    );
  });
  await page.goto(appPath("#/route"));
  await page.reload();
  const ride = page.locator("button.compare-tl-leg[aria-expanded]").first();
  await expect(ride).toHaveAttribute("aria-expanded", "false");
  await ride.click();
  await expect(ride).toHaveAttribute("aria-expanded", "true");
  await expect(page.getByText("קו 8 מהתחנה הזו · אפשר לבחור נסיעה אחרת")).toBeVisible();
  const times = page.getByRole("group", { name: "הזמנים הבאים של קו 8" }).getByRole("button");
  await expect(times).toHaveCount(3);
  await expect(page.getByRole("button", { name: "כל התחנות של קו 8" })).toBeVisible();
  await expectNoSeriousAxeViolations(page, "Route details, a ride opened (he)");
  const replanned = page.waitForRequest((request) => request.method() === "POST" && request.url().includes("/v1/journeys"));
  await times.nth(2).click();
  await replanned;
  await page.getByRole("button", { name: "דיזנגוף סנטר/דיזנגוף" }).first().click();
  await expect(page).toHaveURL(/#\/stop\/mot%3Astop%3A13561$/);
});
