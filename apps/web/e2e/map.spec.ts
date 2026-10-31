import { expect, test, type Page } from "@playwright/test";
import { appPath, blockExternal, expectNoSeriousAxeViolations } from "./helpers";

// Mocked: fixtures-mode dev server, offline map style, every non-local request blocked.
// Until the shell renders <MapHost/>, the map is tested on a dev-only harness page
// (src/map/e2e-harness.html) that mounts MapHost with a published scene and a fake sheet
// covering the bottom 35% (the shell's peek height).

const harness = (query: string) => appPath(`src/map/e2e-harness.html?${query}`);

async function trackExternal(page: Page): Promise<string[]> {
  const external: string[] = [];
  page.on("request", (request) => {
    if (!/^https?:\/\/(localhost|127\.0\.0\.1)[:/]/.test(request.url()) && !request.url().startsWith("data:") && !request.url().startsWith("blob:"))
      external.push(request.url());
  });
  await blockExternal(page);
  return external;
}

async function expectAttributionVisible(page: Page, texts: string[]): Promise<void> {
  const attribution = page.getByTestId("map-attribution");
  await expect(attribution).toBeVisible();
  for (const text of texts) await expect(attribution).toContainText(text);
  const box = (await attribution.boundingBox())!;
  const viewport = page.viewportSize()!;
  expect(box.y).toBeGreaterThanOrEqual(0);
  expect(box.x).toBeGreaterThanOrEqual(0);
  expect(box.x + box.width).toBeLessThanOrEqual(viewport.width);
  // Not covered by the sheet at peek height, nor by anything else.
  const sheetTop = (await page.getByTestId("harness-sheet").boundingBox())!.y;
  expect(box.y + box.height).toBeLessThan(sheetTop);
  const onTop = await attribution.evaluate((element) => {
    const rect = element.getBoundingClientRect();
    const hit = document.elementFromPoint(rect.x + rect.width / 2, rect.y + rect.height / 2);
    return !!hit && element.contains(hit);
  });
  expect(onTop).toBe(true);
}

test("the map chunk is fetched only after first paint, and nothing leaves the origin", async ({ page }) => {
  const external = await trackExternal(page);
  await page.goto(harness("lang=he&scene=journey"));
  await expect(page.getByTestId("map-host")).toBeVisible();
  await expect(page.locator(".maplibregl-canvas")).toBeVisible();
  const timing = await page.evaluate(() => {
    const paint = performance.getEntriesByType("paint").find((entry) => entry.name === "first-paint");
    const maplibre = performance
      .getEntriesByType("resource")
      .filter((entry) => /maplibre-gl(\.js|-worker)/.test(entry.name))
      .map((entry) => entry.startTime);
    return { firstPaint: paint?.startTime ?? null, maplibre };
  });
  expect(timing.firstPaint).not.toBeNull();
  expect(timing.maplibre.length).toBeGreaterThan(0);
  for (const start of timing.maplibre) expect(start).toBeGreaterThanOrEqual(timing.firstPaint!);
  expect(external).toEqual([]);
});

test("attribution is visible above the sheet at 360 × 640 in Hebrew", async ({ page }) => {
  await trackExternal(page);
  await page.goto(harness("lang=he&scene=journey"));
  await expect(page.locator(".maplibregl-canvas")).toBeVisible();
  await expectAttributionVisible(page, ["OpenStreetMap", "OpenFreeMap", "משרד התחבורה"]);
});

test("attribution is visible above the sheet at 360 × 640 in English", async ({ page }) => {
  await trackExternal(page);
  await page.goto(harness("lang=en&scene=journey"));
  await expect(page.locator("html")).toHaveAttribute("dir", "ltr");
  await expectAttributionVisible(page, ["© OpenStreetMap", "OpenFreeMap", "Ministry of Transport"]);
});

test("the map is never mirrored: its container is ltr while the page is rtl", async ({ page }) => {
  await trackExternal(page);
  await page.goto(harness("lang=he&scene=empty"));
  await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
  await expect(page.getByTestId("map-host")).toHaveAttribute("dir", "ltr");
  await expect(page.locator(".maplibregl-map")).toBeVisible();
  const direction = await page.locator(".maplibregl-map").evaluate((element) => getComputedStyle(element).direction);
  expect(direction).toBe("ltr");
  await expect(page.getByTestId("map-attribution")).toHaveAttribute("dir", "rtl");
});

test("pick mode shows a centre pin and reports the centre on load and after a pan", async ({ page }) => {
  await trackExternal(page);
  await page.goto(harness("lang=he&scene=pick"));
  await expect(page.getByTestId("map-pick-pin")).toBeVisible();
  const center = page.getByTestId("harness-center");
  // The centre of the visible map (above the sheet): Tel Aviv's longitude, a little north of
  // the camera centre (32.0853).
  await expect(center).toHaveText(/^34\.78\d*,32\.\d+$/);
  const before = await center.textContent();
  const lat = Number(before!.split(",")[1]);
  expect(lat).toBeGreaterThan(32.0853);
  expect(lat).toBeLessThan(32.2);
  await page.mouse.move(180, 200);
  await page.mouse.down();
  await page.mouse.move(80, 150, { steps: 8 });
  await page.mouse.up();
  await expect(center).not.toHaveText(before!);
});

test("no serious axe violations with the map and a drawn journey", async ({ page }) => {
  await trackExternal(page);
  await page.goto(harness("lang=he&scene=journey"));
  await expect(page.locator(".maplibregl-canvas")).toBeVisible();
  await expectNoSeriousAxeViolations(page, "map harness");
});

// The shell renders <MapHost/> behind the sheet on every screen.
test.describe("in the app shell", () => {
  test("home loads the map chunk after first paint", async ({ page }) => {
    await blockExternal(page);
    await page.goto(appPath("#/"));
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    await expect(page.locator(".maplibregl-canvas")).toBeVisible();
    const late = await page.evaluate(() => {
      const paint = performance.getEntriesByType("paint").find((entry) => entry.name === "first-paint")!.startTime;
      return performance
        .getEntriesByType("resource")
        .filter((entry) => /maplibre-gl|MapView/.test(entry.name))
        .every((entry) => entry.startTime >= paint);
    });
    expect(late).toBe(true);
  });

  test("attribution stays visible above the sheet in Hebrew and English", async ({ page }) => {
    await blockExternal(page);
    await page.goto(appPath("#/"));
    const attribution = page.getByTestId("map-attribution");
    await expect(attribution).toBeVisible();
    await expect(attribution).toContainText("משרד התחבורה");
    const covered = await attribution.evaluate((element) => {
      const rect = element.getBoundingClientRect();
      const hit = document.elementFromPoint(rect.x + rect.width / 2, rect.y + rect.height / 2);
      return !hit || !element.contains(hit);
    });
    expect(covered).toBe(false);
    await page.goto(appPath("#/settings"));
    await page.getByLabel("English").check();
    await expect(attribution).toContainText("Ministry of Transport");
  });

  test("attribution is one compact line beside Back, never under the full sheet", async ({ page }) => {
    await blockExternal(page);
    for (const hash of ["#/search/to", "#/settings", "#/"]) {
      await page.goto(appPath(hash));
      const attribution = page.getByTestId("map-attribution");
      await expect(attribution).toBeVisible();
      await expect(attribution).toContainText("© OpenStreetMap");
      await expect(attribution).toContainText("OpenFreeMap");
      await expect(attribution).toContainText("משרד התחבורה");
      const box = (await attribution.boundingBox())!;
      expect(box.height, `${hash}: one line`).toBeLessThan(20);
      const sheet = (await page.locator(".sheet").boundingBox())!;
      expect(box.y + box.height, `${hash}: above the sheet`).toBeLessThanOrEqual(sheet.y);
      const back = page.getByRole("button", { name: "חזרה" });
      if (await back.count()) {
        const b = (await back.boundingBox())!;
        expect(box.x + box.width <= b.x || box.x >= b.x + b.width, `${hash}: beside Back`).toBe(true);
      }
      const onTop = await attribution.evaluate((element) => {
        const rect = element.getBoundingClientRect();
        const hit = document.elementFromPoint(rect.x + rect.width / 2, rect.y + rect.height / 2);
        return !!hit && (element.contains(hit) || hit.contains(element));
      });
      expect(onTop, `${hash}: not covered`).toBe(true);
    }
  });

  test("the map container is ltr while the app is rtl", async ({ page }) => {
    await blockExternal(page);
    await page.goto(appPath("#/"));
    await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
    await expect(page.getByTestId("map-host")).toHaveAttribute("dir", "ltr");
  });
});
