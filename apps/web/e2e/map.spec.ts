import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import { THEME_COLORS } from "../src/styles/tokens";
import { appPath, blockExternal, expectNoSeriousAxeViolations, useTheme, useTheme as setPageTheme } from "./helpers";

// Mocked: fixtures-mode dev server, offline map style, every non-local request blocked.
// Until the shell renders <MapHost/>, the map is tested on a dev-only harness page
// (src/map/e2e-harness.html) that mounts MapHost with a published scene and a fake sheet
// covering the bottom 35% (the shell's peek height).

const harness = (query: string) => appPath(`src/map/e2e-harness.html?${query}`);

type Clip = { x: number; y: number; width: number; height: number };

/**
 * How many of a region's painted pixels (the map canvas included) are within a step or
 * three of each colour given, and how many there are. The screenshot is decoded in the
 * page, since WebGL's drawing buffer cannot be read back once presented.
 */
async function countColours(page: Page, clip: Clip, colours: string[]): Promise<{ total: number; near: number[] }> {
  const png = (await page.screenshot({ clip, scale: "css" })).toString("base64");
  return page.evaluate(
    async ({ data, hexes }) => {
      const image = new Image();
      image.src = `data:image/png;base64,${data}`;
      await image.decode();
      const canvas = document.createElement("canvas");
      canvas.width = image.width;
      canvas.height = image.height;
      const context = canvas.getContext("2d")!;
      context.drawImage(image, 0, 0);
      const pixels = context.getImageData(0, 0, image.width, image.height).data;
      const targets = hexes.map((hex) => [1, 3, 5].map((at) => parseInt(hex.slice(at, at + 2), 16)));
      const near = targets.map(() => 0);
      for (let at = 0; at < pixels.length; at += 4) {
        targets.forEach((colour, i) => {
          if (colour.every((value, c) => Math.abs(pixels[at + c]! - value) <= 3)) near[i] = (near[i] ?? 0) + 1;
        });
      }
      return { total: pixels.length / 4, near };
    },
    { data: png, hexes: colours },
  );
}

/** The share of a region's pixels that are not the theme's land colour (the drawn scene). */
async function drawnShare(page: Page, clip: Clip, land: string): Promise<number> {
  const { total, near } = await countColours(page, clip, [land]);
  return (total - near[0]!) / total;
}

/** True when a small patch of map with nothing drawn on it is all the given land colour. */
async function isLand(page: Page, x: number, y: number, land: string): Promise<boolean> {
  const { total, near } = await countColours(page, { x, y, width: 2, height: 2 }, [land]);
  return near[0] === total;
}

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
  await expectAttributionVisible(page, ["© OpenStreetMap", "OpenFreeMap", "Israel MoT"]);
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
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await expectNoSeriousAxeViolations(page, "map harness, dark");
});

test("no serious axe violations with the map and a drawn journey, light theme", async ({ page }) => {
  await useTheme(page, "light");
  await trackExternal(page);
  await page.goto(harness("lang=he&scene=journey"));
  await expect(page.locator(".maplibregl-canvas")).toBeVisible();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  await expectNoSeriousAxeViolations(page, "map harness, light");
  await page.goto(harness("lang=en&scene=journey"));
  await expect(page.locator(".maplibregl-canvas")).toBeVisible();
  await expectNoSeriousAxeViolations(page, "map harness, light (en)");
});

test("the map is dark by default, light when chosen, and a switch keeps the camera and the pick centre", async ({ page }) => {
  const external = await trackExternal(page);
  await page.goto(harness("lang=he&scene=pick"));
  await expect(page.locator(".maplibregl-canvas")).toBeVisible();
  const center = page.getByTestId("harness-center");
  await expect(center).toHaveText(/^34\.78\d*,32\.\d+$/);
  const before = await center.textContent();
  // Land beside the pick pin, in the visible map above the sheet.
  const landIs = (theme: "dark" | "light") => () => isLand(page, 40, 300, THEME_COLORS[theme]["map-land"]);
  await expect.poll(landIs("dark")).toBe(true);

  await page.getByTestId("harness-theme").click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  await expect.poll(landIs("light")).toBe(true);
  // Restyled in place: the camera did not move, so the reported centre is unchanged.
  await expect(center).toHaveText(before!);
  await expect(page.getByTestId("map-pick-pin")).toBeVisible();

  await page.getByTestId("harness-theme").click();
  await expect.poll(landIs("dark")).toBe(true);
  await expect(center).toHaveText(before!);
  expect(external).toEqual([]);
});

test("a theme switch keeps the drawn journey", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" }); // the camera fits at once
  await trackExternal(page);
  await page.goto(harness("lang=he&scene=journey&active=none"));
  await expect(page.locator(".maplibregl-canvas")).toBeVisible();
  // The journey crosses the visible map between the attribution and the fake sheet.
  const band = { x: 0, y: 40, width: 360, height: 360 };
  const poll = { timeout: 15_000 };
  await expect.poll(() => drawnShare(page, band, THEME_COLORS.dark["map-land"]), poll).toBeGreaterThan(0.002);
  const darkShare = await drawnShare(page, band, THEME_COLORS.dark["map-land"]);
  expect(darkShare).toBeLessThan(0.2); // mostly land, with the journey drawn on it
  await page.getByTestId("harness-theme").click();
  // Light land everywhere the journey is not, no dark land left, and about as much drawn
  // as before. The light theme draws walking dots and pins in near-black ink, whose
  // anti-aliased edges pass through dark land's colour: a few such pixels are not land.
  await expect
    .poll(async () => {
      const { total, near } = await countColours(page, band, [THEME_COLORS.light["map-land"], THEME_COLORS.dark["map-land"]]);
      return near[1]! / total < 0.002 && (total - near[0]!) / total > darkShare / 2 && (total - near[0]!) / total < 0.2;
    }, poll)
    .toBe(true);
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
    await expect(attribution).toContainText("Israel MoT");
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
    // English too, in both themes: one line beside Back.
    await page.goto(appPath("#/settings"));
    await page.getByLabel("English").check();
    for (const theme of ["Dark", "Light"]) {
      await page.getByRole("radio", { name: theme }).check();
      const attribution = page.getByTestId("map-attribution");
      await expect(attribution).toContainText("Israel MoT");
      const box = (await attribution.boundingBox())!;
      expect(box.height, `English, ${theme}: one line`).toBeLessThan(20);
      const b = (await page.getByRole("button", { name: "Back" }).boundingBox())!;
      expect(box.x >= b.x + b.width, `English, ${theme}: beside Back`).toBe(true);
    }
  });

  test("a wider font never wraps the attribution: map credits stay whole, the timetable credit ends in an ellipsis", async ({ page }) => {
    await blockExternal(page);
    for (const theme of ["dark", "light"] as const) {
      await setPageTheme(page, theme);
      await page.goto(appPath("#/search/to"));
      // Stand-in for a wide system font (DejaVu Sans on the Linux CI runner wraps it otherwise).
      await page.addStyleTag({ content: ".map-attribution { letter-spacing: 1.5px; }" });
      const attribution = page.getByTestId("map-attribution");
      await expect(attribution).toBeVisible();
      const box = (await attribution.boundingBox())!;
      expect(box.height, `${theme}: one line`).toBeLessThan(20);
      const b = (await page.getByRole("button", { name: "חזרה" }).boundingBox())!;
      expect(box.x + box.width <= b.x || box.x >= b.x + b.width, `${theme}: beside Back`).toBe(true);
      const credits = await attribution.locator(".map-credit").evaluateAll((elements) =>
        elements.map((element) => ({
          fit: element.classList.contains("map-credit-fit"),
          clipped: element.scrollWidth > element.clientWidth + 1,
          text: element.textContent,
          title: element.getAttribute("title"),
        })),
      );
      expect(credits.filter((c) => !c.fit).map((c) => [c.text, c.clipped])).toEqual([
        ["© OpenStreetMap", false],
        ["OpenFreeMap", false],
      ]);
      const mot = credits.find((c) => c.fit)!;
      expect(mot.clipped, `${theme}: the timetable credit gives way`).toBe(true);
      expect([mot.text, mot.title]).toEqual(["משרד התחבורה", "משרד התחבורה"]);
    }
  });

  test("the attribution reads in both themes (axe colour contrast) over the app shell", async ({ page }) => {
    await blockExternal(page);
    for (const theme of ["dark", "light"] as const) {
      await page.goto(appPath("#/settings"));
      await page.getByRole("radio", { name: theme === "dark" ? "כהה" : "בהירה" }).check();
      await expect(page.locator("html")).toHaveAttribute("data-theme", theme);
      const results = await new AxeBuilder({ page }).include('[data-testid="map-attribution"]').withRules(["color-contrast"]).analyze();
      expect(results.violations.map((v) => v.id), theme).toEqual([]);
      expect(results.passes.map((v) => v.id), theme).toContain("color-contrast");
    }
  });

  test("the map container is ltr while the app is rtl", async ({ page }) => {
    await blockExternal(page);
    await page.goto(appPath("#/"));
    await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
    await expect(page.getByTestId("map-host")).toHaveAttribute("dir", "ltr");
  });
});
