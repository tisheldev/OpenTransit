import { readFileSync } from "node:fs";
import { expect, test, type Page } from "@playwright/test";
import { appPath, blockExternal, expectNoSeriousAxeViolations } from "./helpers";

// The stops layer (stops and lines design, 12 November 2026), mocked: fixtures mode, the
// offline map style, stops by area from the derived answer (src/mocks/areaStops.ts).

const MAP_READY_MS = 20_000;

async function allowLocation(page: Page): Promise<void> {
  await page.context().grantPermissions(["geolocation"]);
  await page.context().setGeolocation({ latitude: 32.0753, longitude: 34.7749, accuracy: 20 });
}

const layer = (page: Page) => page.getByTestId("stops-layer");

test.beforeEach(async ({ page }) => {
  await blockExternal(page);
});

test("Home draws its stops as signs, the nearest one chosen, with a couple of next-line tags", async ({ page }) => {
  await allowLocation(page);
  await page.goto(appPath("#/"));
  await expect(layer(page)).toHaveAttribute("data-level", "signs", { timeout: MAP_READY_MS });
  const chosen = layer(page).locator(".ot-stop--chosen");
  await expect(chosen).toHaveCount(1);
  await expect(chosen).toHaveAttribute("data-stop-id", "mot:stop:13583");
  // Every sign is a button of at least 44 px that opens its stop.
  const sign = layer(page).getByRole("button", { name: /^פתיחת התחנה דיזנגוף סנטר\/דיזנגוף, קו 172 בעוד \d+ דק׳$/ });
  await expect(sign).toBeAttached();
  const box = (await sign.boundingBox())!;
  expect(box.width).toBeGreaterThanOrEqual(44);
  expect(box.height).toBeGreaterThanOrEqual(44);
  // Tags: two at most, the chosen stop's (pale) among them.
  const tags = layer(page).locator(".ot-stop-tag:not(.ot-stop-tag--measure)");
  await expect(tags.first()).toBeVisible();
  expect(await tags.count()).toBeLessThanOrEqual(2);
  await expectNoSeriousAxeViolations(page, "Home with the stops layer (he)");
});

test("tapping a group zooms in and lists its stops; the picked row is the chosen stop; Back closes it", async ({ page }) => {
  await allowLocation(page);
  await page.goto(appPath("#/"));
  await expect(layer(page)).toHaveAttribute("data-level", "signs", { timeout: MAP_READY_MS });
  const group = layer(page).getByRole("button", { name: /^\d+ תחנות צמודות, הקשה פותחת אותן$/ }).first();
  await expect(group).toBeAttached({ timeout: MAP_READY_MS });
  const count = Number((await group.getAttribute("aria-label"))!.match(/^\d+/)![0]);
  // Groups sit close together and may be under the sheet's edge: use the keyboard.
  await group.press("Enter");

  // The sheet lists the group's stops (board 9).
  const heading = page.getByRole("heading", { level: 1 });
  await expect(heading).toHaveText(new RegExp(`· ${count} תחנות$`));
  await expect(page.getByText("לאיזה כיוון נוסעים?")).toBeVisible();
  const rows = page.locator(".stop-group__row");
  await expect(rows).toHaveCount(count);
  // The first row is picked, and its stop is the chosen one on the map.
  await expect(rows.first()).toHaveAttribute("aria-pressed", "true");
  const picked = await layer(page).locator(".ot-stop--chosen").getAttribute("data-stop-id");
  expect(picked).toBeTruthy();
  await expectNoSeriousAxeViolations(page, "Home, a group opened (he)");

  // Picking another row makes it the chosen stop.
  await rows.nth(1).click();
  await expect(rows.nth(1)).toHaveAttribute("aria-pressed", "true");
  await expect(rows.first()).toHaveAttribute("aria-pressed", "false");
  await expect(layer(page).locator(".ot-stop--chosen")).not.toHaveAttribute("data-stop-id", picked!);
  // The map zoomed in: the group's stops are signs now (or a count too close to split).
  await expect(layer(page)).toHaveAttribute("data-level", "signs");

  // Back returns to Home's own sheet.
  await page.getByRole("button", { name: "חזרה" }).click();
  await expect(heading).toHaveText("תכנון נסיעה");
  await expect(rows).toHaveCount(0);
});

test("a picked row tapped again opens its stop", async ({ page }) => {
  await allowLocation(page);
  await page.goto(appPath("#/"));
  await expect(layer(page)).toHaveAttribute("data-level", "signs", { timeout: MAP_READY_MS });
  const group = layer(page).getByRole("button", { name: /תחנות צמודות/ }).first();
  await expect(group).toBeAttached({ timeout: MAP_READY_MS });
  await group.press("Enter");
  const first = page.locator(".stop-group__row").first();
  await expect(first).toHaveAttribute("aria-pressed", "true");
  await first.click();
  await expect(page).toHaveURL(/#\/stop\//);
});

test("far out: stations only, with the hint to zoom in for bus stops", async ({ page }) => {
  await page.goto(appPath("#/"));
  await expect(layer(page)).toHaveAttribute("data-level", "signs", { timeout: MAP_READY_MS });
  await page.locator(".maplibregl-canvas").focus();
  // One zoom level a key press (each an eased step): press until the map is far out.
  await expect(async () => {
    await page.keyboard.press("Minus");
    await page.waitForTimeout(400);
    expect(Number(await layer(page).getAttribute("data-zoom"))).toBeLessThan(12);
  }).toPass({ timeout: MAP_READY_MS });
  await expect(layer(page)).toHaveAttribute("data-level", "stations", { timeout: MAP_READY_MS });
  await expect(page.getByText("התקרבו כדי לראות תחנות אוטובוס")).toBeVisible();
  await expect(layer(page).locator(".ot-stop-sign:not(.ot-stop-sign--station)")).toHaveCount(0);
});

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

test("Navigate draws no stops layer and asks for no stops by area", async ({ page }) => {
  const asked: string[] = [];
  page.on("request", (request) => {
    if (/\/v1\/stops\?.*bbox=/.test(request.url())) asked.push(request.url());
  });
  await page.addInitScript((value) => sessionStorage.setItem("opentransit:activeTrip", value), JSON.stringify(activeTrip()));
  await page.goto(appPath("#/navigate"));
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await expect(page.getByTestId("map-canvas")).toBeAttached({ timeout: MAP_READY_MS });
  await page.waitForTimeout(1500);
  await expect(layer(page)).toHaveCount(0);
  expect(asked).toEqual([]);
});
