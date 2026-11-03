import { expect, test } from "@playwright/test";
import { encodePathRef } from "../src/api/pathRef";
import { appPath } from "./helpers";

// @real: against a running local API. Skipped unless the API's /readyz returns 200
// (design: Work slices). Two modes (playwright.config.ts):
// - dev server (default): API calls go through the dev server's /v1 proxy; the page
//   itself runs on MSW fixtures, so page-level checks are skipped there.
// - served build (OT_E2E_BASE_URL, e.g. http://127.0.0.1:8590/app/): the API serves the
//   built client at /app/, same origin, under its CSP.

const apiOrigin = process.env.OPENTRANSIT_API_ORIGIN ?? "http://localhost:8000";
const served = !!process.env.OT_E2E_BASE_URL;

test.describe("@real", () => {
  test.beforeAll(async ({ request }) => {
    const ready = await request.get(`${apiOrigin}/readyz`, { timeout: 5_000 }).catch(() => null);
    test.skip(ready?.status() !== 200, `API at ${apiOrigin} is not ready; real checks pending`);
  });

  test("/v1/status on the real API", async ({ request }) => {
    const response = await request.get("/v1/status");
    expect(response.status()).toBe(200);
    const body = await response.json();
    expect(body.data.ready).toBe(true);
    expect(body.meta.mode).toBe("real");
    expect(body.data.realtime).toBe("not_enabled");
  });

  test("a real engine trip ID opens through the encoded trips path", async ({ request }) => {
    const departAt = new Date(Date.now() + 26 * 3600_000).toISOString().replace(/\.\d{3}Z$/, "Z");
    const journey = await request.post("/v1/journeys", {
      data: {
        from: { kind: "stop", stopId: "mot:stop:13583" },
        to: { kind: "coordinate", latitude: 32.7767, longitude: 35.0231 },
        departAt,
      },
    });
    expect(journey.status()).toBe(200);
    const legs = (await journey.json()).data.journeys.flatMap((item: { legs: unknown[] }) => item.legs);
    const ids = [
      ...new Set(
        legs.flatMap((leg: { transit: { engineTripId: string } | null }) => (leg.transit ? [leg.transit.engineTripId] : [])),
      ),
    ] as string[];
    expect(ids.length).toBeGreaterThan(0);
    for (const id of ids) {
      expect(id).toContain(":");
      const encoded = encodePathRef(id);
      expect(encoded.ok, id).toBe(true);
      if (!encoded.ok) continue;
      const trip = await request.get(`/v1/trips/${encoded.segment}`);
      expect(trip.status(), id).toBe(200);
      expect((await trip.json()).data.tripRef).toBe(id);
    }
  });

  test("the served build loads under the API's CSP and reads the real status", async ({ page }) => {
    test.skip(!served, "page checks need the build served by the API (OT_E2E_BASE_URL)");
    await page.addInitScript(() => {
      const seen: string[] = [];
      (window as unknown as { cspViolations: string[] }).cspViolations = seen;
      document.addEventListener("securitypolicyviolation", (event) => {
        seen.push(`${event.violatedDirective} ${event.blockedURI}`);
      });
    });
    const status = page.waitForResponse((response) => new URL(response.url()).pathname === "/v1/status");
    const documentResponse = await page.goto(appPath("#/"));
    expect(documentResponse?.status()).toBe(200);
    const headers = documentResponse!.headers();
    expect(headers["content-security-policy"]).toContain("script-src 'self'");
    expect(headers["cache-control"]).toBe("no-store");
    expect(headers["x-content-type-options"]).toBe("nosniff");
    expect((await status).status()).toBe(200);
    await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    // A production build has no fixture mode: the "test data" banner must not appear.
    await expect(page.getByText("נתוני בדיקה")).toHaveCount(0);
    expect(await page.evaluate(() => (window as unknown as { cspViolations: string[] }).cspViolations)).toEqual([]);
  });
});
