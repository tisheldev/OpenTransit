import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { server } from "../mocks/node";
import { respond } from "../mocks/handlers";
import {
  getRoute,
  getRoutePatterns,
  getStatus,
  getStop,
  getStopDepartures,
  getTrip,
  listRoutes,
  listStops,
  planJourney,
  searchPlaces,
} from "./endpoints";
import { fixture } from "./fixtures";
import type { JourneyRequest } from "./types";

const journeyRequest: JourneyRequest = {
  from: { kind: "stop", stopId: "mot:stop:13583" },
  to: { kind: "coordinate", latitude: 32.7767, longitude: 35.0231 },
  departAt: "2026-10-01T08:00:00+03:00",
};

/** Capture the URL the client actually sent for the next matching request. */
function captureUrl(method: "get" | "post", pattern: string): { url?: URL } {
  const seen: { url?: URL } = {};
  server.events.on("request:start", ({ request }) => {
    const url = new URL(request.url);
    if (request.method.toLowerCase() === method && url.pathname.startsWith(pattern)) seen.url = url;
  });
  return seen;
}

describe("endpoints over MSW", () => {
  it("reads status", async () => {
    const result = await getStatus();
    expect(result.ok && result.value.data.ready).toBe(true);
  });

  it("searches places with repeated type parameters and near", async () => {
    const seen = captureUrl("get", "/v1/places");
    const result = await searchPlaces({
      q: "Dizengoff",
      lang: "en",
      types: ["stop", "poi"],
      near: { latitude: 32.0757, longitude: 34.7748 },
      limit: 5,
    });
    expect(result.ok).toBe(true);
    expect(seen.url?.searchParams.getAll("type")).toEqual(["stop", "poi"]);
    expect(seen.url?.searchParams.get("near")).toBe("32.0757,34.7748");
    expect(seen.url?.searchParams.has("cursor")).toBe(false);
  });

  it("returns an empty search as a success", async () => {
    const result = await searchPlaces({ q: "zzzznotarealstop", lang: "en", types: ["stop"] });
    expect(result.ok && result.value.data).toEqual([]);
  });

  it("plans a journey and then opens each leg's trip by engineTripId", async () => {
    const seen = captureUrl("get", "/v1/trips/");
    const result = await planJourney(journeyRequest);
    expect(result.ok).toBe(true);
    if (!result.ok) return;
    const legs = result.value.data.journeys.flatMap((journey) => journey.legs);
    const tripId = legs.find((leg) => leg.transit)?.transit?.engineTripId;
    expect(tripId).toBeDefined();
    // The mocked API holds only some recorded trips; an unknown one is a 404 state.
    const trip = await getTrip(tripId!);
    expect(seen.url?.pathname).toBe(`/v1/trips/${encodeURIComponent(tripId!)}`);
    expect(trip.ok || trip.state === "not_found").toBe(true);
  });

  it("opens a recorded overnight trip by its ref", async () => {
    const result = await getTrip("20260930_23:50_mot60day_584668860_300926");
    expect(result.ok && result.value.data.calls.length).toBe(40);
  });

  it("refuses a trip ref the API could not route, without a request", async () => {
    let requested = false;
    server.events.on("request:start", () => {
      requested = true;
    });
    const result = await getTrip("a/b");
    expect(result).toMatchObject({ ok: false, state: "unexpected", error: { kind: "unroutable_ref" } });
    expect(requested).toBe(false);
  });

  it("reads a stop, its departures and the next page by cursor", async () => {
    expect((await getStop("mot:stop:13583")).ok).toBe(true);
    const first = await getStopDepartures("mot:stop:13583", { from: "2026-10-01T00:10:00+03:00", limit: 2 });
    expect(first.ok).toBe(true);
    if (!first.ok) return;
    const cursor = first.value.page.nextCursor;
    expect(cursor).toBeTruthy();
    const second = await getStopDepartures("mot:stop:13583", { from: "2026-10-01T00:10:00+03:00", limit: 2, cursor });
    expect(second.ok && second.value.data[0]?.tripRef).not.toBe(first.value.data[0]?.tripRef);
  });

  it("lists stops near a point and in a box", async () => {
    const seen = captureUrl("get", "/v1/stops");
    expect((await listStops({ near: { latitude: 32.08, longitude: 34.78 }, radiusMeters: 300 }, { limit: 1 })).ok).toBe(true);
    expect(seen.url?.searchParams.get("radius")).toBe("300");
    expect((await listStops({ bbox: { west: 34.77, south: 32.07, east: 34.79, north: 32.09 } })).ok).toBe(true);
    expect(seen.url?.searchParams.get("bbox")).toBe("34.77,32.07,34.79,32.09");
  });

  it("reads routes, a route and its patterns", async () => {
    expect((await listRoutes({ operatorId: "op_1" })).ok).toBe(true);
    expect((await getRoute("mot:route:bus_7")).ok).toBe(true);
    expect((await getRoutePatterns("mot:route:bus_7")).ok).toBe(true);
  });
});

describe("failures", () => {
  it("maps a problem to its UI state", async () => {
    server.use(http.post("*/v1/journeys", () => respond(fixture("recorded-problem-outside-window"))));
    const result = await planJourney(journeyRequest);
    expect(result).toMatchObject({ ok: false, state: "outside_window", error: { kind: "problem", status: 422 } });
  });

  it("keeps Retry-After from a 429", async () => {
    server.use(http.get("*/v1/status", () => respond(fixture("synthetic-problem-rate-limited"), { "Retry-After": "7" })));
    const result = await getStatus();
    expect(result).toMatchObject({ ok: false, state: "rate_limited", error: { retryAfterSeconds: 7 } });
  });

  it("reports a 503 without a problem body as temporarily unavailable", async () => {
    server.use(http.get("*/v1/status", () => new HttpResponse("<html>bad gateway</html>", { status: 503 })));
    expect(await getStatus()).toMatchObject({ ok: false, state: "temporarily_unavailable", error: { kind: "http" } });
  });

  it("reports a network failure", async () => {
    server.use(http.get("*/v1/status", () => HttpResponse.error()));
    expect(await getStatus()).toMatchObject({ ok: false, state: "network", error: { kind: "network" } });
  });

  it("reports an aborted request without calling it a server failure", async () => {
    const controller = new AbortController();
    controller.abort();
    expect(await getStatus(controller.signal)).toMatchObject({ ok: false, error: { kind: "aborted" } });
  });

  it("rejects a 200 whose body breaks the schema", async () => {
    server.use(http.get("*/v1/status", () => HttpResponse.json({ data: { ready: "yes" } })));
    const result = await getStatus();
    expect(result).toMatchObject({ ok: false, state: "unexpected", error: { kind: "invalid_response" } });
  });
});
