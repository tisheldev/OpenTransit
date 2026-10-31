import { expect, test } from "@playwright/test";

// @real: against a running local API, through the dev server's /v1 proxy. Skipped
// unless the API's /readyz returns 200 (design: Work slices).

const apiOrigin = process.env.OPENTRANSIT_API_ORIGIN ?? "http://localhost:8000";

test.describe("@real", () => {
  test.beforeAll(async ({ request }) => {
    const ready = await request.get(`${apiOrigin}/readyz`, { timeout: 5_000 }).catch(() => null);
    test.skip(ready?.status() !== 200, `API at ${apiOrigin} is not ready; real checks pending`);
  });

  test("dev proxy reaches /v1/status on the real API", async ({ request }) => {
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
    const id = legs.find((leg: { transit: unknown }) => leg.transit)?.transit.engineTripId as string;
    expect(id).not.toContain("/");
    const trip = await request.get(`/v1/trips/${encodeURIComponent(id)}`);
    expect(trip.status()).toBe(200);
    expect((await trip.json()).data.tripRef).toBe(id);
  });
});
