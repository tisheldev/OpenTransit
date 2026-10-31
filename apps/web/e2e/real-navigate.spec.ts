import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import { encodePathRef } from "../src/api/pathRef";
import type { Result } from "../src/api/result";
import type { StopDetail } from "../src/api/schemas";
import type { Journey } from "../src/api/types";
import { callTargets, fetchCallPositions } from "../src/nav/callPositions";
import { buildSteps, type TripDetail } from "../src/nav/steps";
import { appPath, blockExternal } from "./helpers";

// @real: Dizengoff Center → Technion planned on the real API (no fixtures), seeded as the
// active trip with its real trips, then replayed through every step with SIMULATED
// positions (the simulated source; not a recorded trace). Skips unless /readyz is 200.
//
// Dev-server mode runs the page on fixture handlers (MSW), so the page cannot reach the
// real stops itself: the spec fetches the call positions from the real API with the
// app's own planner (src/nav/callPositions.ts) and seeds them. In served mode
// (OT_E2E_BASE_URL) the page fetches them itself at Start.

const apiOrigin = process.env.OPENTRANSIT_API_ORIGIN ?? "http://localhost:8000";
const served = !!process.env.OT_E2E_BASE_URL;
/** A weekday morning inside oct31a coverage (31 Oct – 30 Nov 2026). */
const DEPART_AT = "2026-11-02T08:00:00+02:00";

async function api<T>(request: APIRequestContext, path: string): Promise<{ status: number; body: T }> {
  const response = await request.get(`${apiOrigin}${path}`);
  return { status: response.status(), body: (await response.json()) as T };
}

function realGetStop(request: APIRequestContext) {
  return async (stopId: string): Promise<Result<StopDetail>> => {
    const encoded = encodePathRef(stopId);
    if (!encoded.ok) return { ok: false, error: { kind: "unroutable_ref", ref: stopId, reason: encoded.reason }, state: "unexpected" };
    const { status, body } = await api<StopDetail>(request, `/v1/stops/${encoded.segment}`);
    return status === 200 ? { ok: true, status, value: body } : { ok: false, error: { kind: "http", status }, state: "unexpected" };
  };
}

async function currentStep(page: Page): Promise<number> {
  return page.getByRole("list").getByRole("button").evaluateAll((rows) => rows.findIndex((row) => row.getAttribute("aria-current") === "step"));
}

test.describe("@real navigate", () => {
  test.beforeAll(async ({ request }) => {
    const ready = await request.get(`${apiOrigin}/readyz`, { timeout: 5_000 }).catch(() => null);
    test.skip(ready?.status() !== 200, `API at ${apiOrigin} is not ready; real checks pending`);
  });

  test("Dizengoff Center → Technion replays through every step with simulated positions", async ({ page, request }) => {
    test.setTimeout(180_000);
    const planned = await request.post(`${apiOrigin}/v1/journeys`, {
      data: {
        from: { kind: "stop", stopId: "mot:stop:13583" },
        to: { kind: "coordinate", latitude: 32.7767, longitude: 35.0231 },
        departAt: DEPART_AT,
      },
    });
    expect(planned.status()).toBe(200);
    const response = (await planned.json()) as { data: { journeys: Journey[] }; meta: unknown };
    const journey = response.data.journeys[0]!;
    expect(journey.legs.some((leg) => leg.kind === "transit")).toBe(true);

    const trips: Record<string, TripDetail> = {};
    for (const leg of journey.legs) {
      if (leg.kind !== "transit" || !leg.transit) continue;
      const encoded = encodePathRef(leg.transit.engineTripId);
      expect(encoded.ok).toBe(true);
      if (!encoded.ok) continue;
      const { status, body } = await api<{ data: TripDetail }>(request, `/v1/trips/${encoded.segment}`);
      expect(status, leg.transit.engineTripId).toBe(200);
      trips[leg.transit.engineTripId] = body.data;
    }

    const steps = buildSteps(journey, trips);
    const callPositions = served ? undefined : await fetchCallPositions(callTargets(steps, trips), realGetStop(request));
    const trip = {
      version: 1,
      journey,
      meta: response.meta,
      trips,
      startedAt: new Date().toISOString(),
      nav: { stepIndex: 0 },
      labels: { origin: "דיזנגוף סנטר", destination: "הטכניון" },
      ...(callPositions ? { callPositions } : {}),
    };

    if (!served) await blockExternal(page);
    await page.addInitScript((value) => {
      if (sessionStorage.getItem("e2e-seeded")) return;
      sessionStorage.setItem("opentransit:activeTrip", value);
      sessionStorage.setItem("e2e-seeded", "1");
    }, JSON.stringify(trip));
    await page.goto(appPath("#/navigate"));
    await expect(page.locator(".step-card")).toBeVisible();
    // Record every announcement (step changes and cues) from the live region.
    await page.evaluate(() => {
      const log: string[] = [];
      (window as unknown as { navLog: string[] }).navLog = log;
      const region = document.querySelector("[aria-live]")!;
      new MutationObserver(() => log.push(region.textContent ?? "")).observe(region, { childList: true, subtree: true, characterData: true });
    });
    if (served) {
      await expect
        .poll(async () => page.evaluate(() => Object.keys(JSON.parse(sessionStorage.getItem("opentransit:activeTrip") ?? "{}").callPositions ?? {}).length), { timeout: 20_000 })
        .toBeGreaterThan(0);
    }

    await page.getByRole("combobox", { name: "מהירות ההדמיה" }).selectOption("600");
    await page.getByRole("checkbox", { name: "מיקום מדומה (בדיקה)" }).check();

    const last = steps.length - 1;
    let automatic = 0;
    let manual = 0;
    let step = await currentStep(page);
    while (step < last) {
      const before = step;
      try {
        await expect.poll(() => currentStep(page), { timeout: 15_000, intervals: [100] }).not.toBe(before);
        step = await currentStep(page);
        automatic += step - before;
      } catch {
        await page.getByRole("button", { name: "השלב הבא" }).click();
        manual += 1;
        step = await currentStep(page);
      }
    }
    await expect(page.locator(".step-card")).toContainText("הגעתם אל הטכניון");
    const log = await page.evaluate(() => (window as unknown as { navLog: string[] }).navLog);
    const cues = {
      twoStops: log.filter((text) => text.includes("רדו בעוד 2 תחנות")).length,
      nextStop: log.filter((text) => text.includes("רדו בתחנה הבאה")).length,
    };
    const rides = steps.filter((s) => s.kind === "ride").length;
    const ridesWithPositions = Object.values(callPositions ?? {}).filter((entry) => entry.status === "ok").length;
    const summary = { steps: steps.length, automatic, manual, rides, ridesWithPositions, cues, served };
    test.info().annotations.push({ type: "replay", description: JSON.stringify(summary) });
    console.log(`real-navigate replay: ${JSON.stringify(summary)}`);
    expect(automatic + manual).toBe(last);

    await page.getByRole("button", { name: "סיום", exact: true }).click();
    await expect(page).toHaveURL(/#\/$/);
    expect(await page.evaluate(() => sessionStorage.getItem("opentransit:activeTrip"))).toBeNull();
  });
});
