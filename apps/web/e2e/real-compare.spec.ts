import { fileURLToPath } from "node:url";
import { expect, test } from "@playwright/test";
import type { ViteDevServer } from "vite";
import { appPath, expectNoSeriousAxeViolations } from "./helpers";

// @real Compare (slice S5.6): Dizengoff Center (mot:stop:13583) → Technion
// (32.7767, 35.0231) on a weekday at 08:00 inside coverage, planned through the Compare
// screen against a running API. Skipped unless /readyz is 200 at OPENTRANSIT_API_ORIGIN.
//
// The configured web server runs in fixtures mode (MSW answers /v1 in the browser), so
// this file starts its own dev server without fixtures, proxying /v1 to the API.

const apiOrigin = process.env.OPENTRANSIT_API_ORIGIN ?? "http://localhost:8000";
const port = Number(process.env.OT_E2E_PORT ?? 5174) + 20;
const baseURL = `http://localhost:${port}/`;

let server: ViteDevServer | null = null;
let wall: string | null = null;

/** The first Monday after today (Israel calendar) at 08:00 that lies inside coverage. */
function mondayMorning(coverage: { from: string; until: string }): string | null {
  const day = new Date(`${new Date().toLocaleDateString("en-CA", { timeZone: "Asia/Jerusalem" })}T12:00:00Z`);
  const from = Date.parse(coverage.from);
  const until = Date.parse(coverage.until);
  for (let i = 1; i <= 60; i += 1) {
    const candidate = new Date(day.getTime() + i * 86_400_000);
    if (candidate.getUTCDay() !== 1) continue;
    const at = Date.parse(`${candidate.toISOString().slice(0, 10)}T08:00:00+02:00`);
    if (at > from && at + 6 * 3600_000 < until) return `${candidate.toISOString().slice(0, 10)}T08:00`;
  }
  return null;
}

test.describe("@real compare", () => {
  test.describe.configure({ mode: "serial" });

  test.beforeAll(async ({ request }) => {
    const ready = await request.get(`${apiOrigin}/readyz`, { timeout: 5_000 }).catch(() => null);
    test.skip(ready?.status() !== 200, `API at ${apiOrigin} is not ready; real compare pending`);
    const status = await (await request.get(`${apiOrigin}/v1/status`)).json();
    wall = mondayMorning(status.meta.coverage);
    test.skip(wall === null, "no Monday inside the API's coverage");
    process.env.OPENTRANSIT_API_ORIGIN = apiOrigin;
    const { createServer } = await import("vite");
    server = await createServer({
      configFile: fileURLToPath(new URL("../vite.config.ts", import.meta.url)),
      mode: "development",
      server: { port, strictPort: true },
      logLevel: "warn",
    });
    await server.listen();
  });

  test.afterAll(async () => {
    await server?.close();
  });

  test("Dizengoff Center → Technion: options with times on the half sheet, itinerary, a train from boarding to exit, Start", async ({ page }, testInfo) => {
    const draft = {
      from: {
        type: "place",
        place: {
          label: "דיזנגוף סנטר",
          locality: "תל אביב-יפו",
          kind: "stop",
          latitude: 32.0753,
          longitude: 34.7749,
          stopId: "mot:stop:13583",
          placeRef: null,
          refGenerationId: null,
        },
      },
      to: {
        type: "place",
        place: {
          label: "טכניון",
          locality: "חיפה",
          kind: "pin",
          latitude: 32.7767,
          longitude: 35.0231,
          stopId: null,
          placeRef: null,
          refGenerationId: null,
        },
      },
      when: { mode: "depart_at", wall, offset: "auto" },
    };
    await page.addInitScript((value) => sessionStorage.setItem("opentransit:plan", value), JSON.stringify(draft));
    const answer = page.waitForResponse((r) => r.request().method() === "POST" && r.url().endsWith("/v1/journeys"));
    await page.goto(new URL(appPath("#/compare"), baseURL).href);
    const response = await answer;
    expect(response.status()).toBe(200);
    const body = await response.json();
    expect(body.meta.mode).toBe("real");

    const options = page.getByRole("list", { name: "אפשרויות נסיעה" }).getByRole("button");
    await expect(options).toHaveCount(body.data.journeys.length);
    expect(body.data.journeys.length).toBeGreaterThan(0);
    const details = page.getByRole("region", { name: /פרטי מסלול/ });
    await expect(details.locator(".it").first()).toBeVisible();
    await expect(details.getByRole("link")).toHaveCount(0);

    // Half sheet: every option, with its departure and arrival, above the pinned Start.
    await expect(page.locator(".sheet")).toHaveAttribute("data-snap", "half");
    const bar = (await page.locator(".compare-start").boundingBox())!;
    const clock = (iso: string) =>
      new Intl.DateTimeFormat("he-IL", { timeZone: "Asia/Jerusalem", hour: "2-digit", minute: "2-digit", hourCycle: "h23" }).format(
        new Date(iso),
      );
    for (let i = 0; i < body.data.journeys.length; i += 1) {
      const box = (await options.nth(i).boundingBox())!;
      expect(box.y + box.height, `option ${i + 1} above Start`).toBeLessThanOrEqual(bar.y + 1);
      const { scheduledDeparture, scheduledArrival } = body.data.journeys[i].timing;
      await expect(options.nth(i)).toHaveAccessibleName(new RegExp(`יציאה ${clock(scheduledDeparture)}, הגעה ${clock(scheduledArrival)}`));
    }
    await expect(details).not.toContainText(/\bSTART\b|\bEND\b/);

    // SP04 client work: request sent → chart painted (marks from src/plan/queries.ts).
    const clientMs = await page.evaluate(() => performance.getEntriesByName("ot:journeys:client")[0]?.duration ?? null);
    testInfo.annotations.push({ type: "SP04 client ms", description: String(clientMs) });

    // Every option: a rail leg reads as Israel Railways from its boarding stop to its exit
    // (never "a train to <exit>"); a walk without a distance reads as time only.
    let sawTrain = false;
    let sawTimeOnly = false;
    const summary: string[] = [];
    for (let i = 0; i < body.data.journeys.length; i += 1) {
      await options.nth(i).click();
      await expect(options.nth(i)).toHaveAttribute("aria-pressed", "true");
      const journey = body.data.journeys[i];
      const rails = journey.legs.filter((leg: { mode: string }) => /rail/i.test(leg.mode)) as {
        to: { name: string };
        transit: { operatorName: string };
      }[];
      for (const leg of rails) {
        await expect(details.locator(".it-ride-name", { hasText: leg.transit.operatorName }).first()).toBeVisible();
        await expect(details.locator(".it-name", { hasText: leg.to.name }).first()).toBeVisible();
        await expect(details).not.toContainText(`רכבת ל${leg.to.name}`);
        sawTrain = true;
      }
      const timeOnly = journey.legs.filter((leg: { kind: string; distanceMeters: number | null }) => leg.kind === "walk" && leg.distanceMeters === null);
      if (timeOnly.length > 0) {
        await expect(details.getByText(/^הליכה כ־/).first()).toBeVisible();
        sawTimeOnly = true;
      }
      summary.push(
        `${journey.timing.scheduledDeparture.slice(11, 16)}–${journey.timing.scheduledArrival.slice(11, 16)} ` +
          `${journey.transfers} transfers: ` +
          journey.legs
            .filter((leg: { kind: string }) => leg.kind === "transit")
            .map((leg: { mode: string; transit: { routeShortName: string }; to: { name: string } }) =>
              /rail/i.test(leg.mode) ? `train→${leg.to.name}` : leg.transit.routeShortName,
            )
            .join(" > "),
      );
    }
    testInfo.annotations.push({ type: "journeys", description: summary.join(" | ") });
    testInfo.annotations.push({ type: "coverage", description: `${wall}; train ${sawTrain}; time-only walk ${sawTimeOnly}` });
    console.log(`[real-compare] ${wall} SP04 client ${clientMs} ms; ${summary.join(" | ")}`);

    await options.first().click();
    await expectNoSeriousAxeViolations(page, "real compare");
    await page.getByRole("button", { name: "התחלת ניווט" }).click();
    await expect(page).toHaveURL(/#\/navigate$/);
  });
});
