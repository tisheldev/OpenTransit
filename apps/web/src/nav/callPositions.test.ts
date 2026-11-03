import { afterEach, describe, expect, it } from "vitest";
import type { Result } from "../api/result";
import type { StopDetail, Trip } from "../api/schemas";
import type { Metadata } from "../api/types";
import { endActiveTrip, getActiveTrip, loadActiveTrip, resetActiveTripCache, startActiveTrip } from "./activeTrip";
import { CALLS_BEFORE_EXIT, callTargets, engineCallPositions, fetchCallPositions, missingTrips, runPool } from "./callPositions";
import { buildSteps } from "./steps";
import { recordedJourneys, recordedTrips } from "./testdata";
import recorded from "./testdata/recorded-oct31a-dizengoff-technion.json";
import { prefetchForTrip, type PrefetchApi } from "./usePrefetch";

const stopPositions = (recorded as unknown as { stopPositions: Record<string, { latitude: number; longitude: number }> }).stopPositions;

function stopAnswer(stopId: string): Result<StopDetail> {
  const position = stopPositions[stopId];
  if (!position) return { ok: false, error: { kind: "http", status: 404 }, state: "not_found" };
  return { ok: true, status: 200, value: { data: { stopId, ...position } } as unknown as StopDetail };
}

/** A counting fake API: resolves on the next macrotask so concurrency is observable. */
function fakeApi(options: { failStop?: string } = {}) {
  const calls = { stops: [] as string[], trips: [] as string[], inFlight: 0, maxInFlight: 0 };
  const api: PrefetchApi = {
    getStop: async (stopId) => {
      calls.stops.push(stopId);
      calls.inFlight += 1;
      calls.maxInFlight = Math.max(calls.maxInFlight, calls.inFlight);
      await new Promise((resolve) => setTimeout(resolve, 1));
      calls.inFlight -= 1;
      return stopId === options.failStop ? { ok: false, error: { kind: "network" }, state: "network" } : stopAnswer(stopId);
    },
    getTrip: async (ref) => {
      calls.trips.push(ref);
      await new Promise((resolve) => setTimeout(resolve, 1));
      const trip = recordedTrips[ref];
      return trip
        ? { ok: true, status: 200, value: { data: trip } as unknown as Trip }
        : { ok: false, error: { kind: "http", status: 404 }, state: "not_found" };
    },
  };
  return { api, calls };
}

afterEach(() => {
  endActiveTrip();
  resetActiveTripCache();
});

describe("call targets", () => {
  it.each([0, 1, 2])("journey %i: at most the two calls before each exit, for rides with trip detail", (index) => {
    const journey = recordedJourneys[index]!;
    const steps = buildSteps(journey, recordedTrips);
    const targets = callTargets(steps, recordedTrips);
    const rides = steps.filter((step) => step.kind === "ride");
    expect(Object.keys(targets).map(Number)).toEqual(rides.filter((r) => (r.ride?.stopCount ?? 0) > 0).map((r) => r.index));
    for (const ride of rides) {
      const calls = targets[ride.index] ?? [];
      expect(calls.length).toBeLessThanOrEqual(CALLS_BEFORE_EXIT);
      expect(calls.length).toBe(Math.min(CALLS_BEFORE_EXIT, ride.ride!.stopCount!));
      for (const call of calls) {
        expect(call.ordinal).toBeLessThan(ride.ride!.exitOrdinal!);
        expect(call.ordinal).toBeGreaterThanOrEqual(ride.ride!.boardOrdinal!);
      }
    }
  });

  it("skips rides without trip detail", () => {
    const journey = recordedJourneys[0]!;
    const steps = buildSteps(journey, {});
    expect(callTargets(steps, {})).toEqual({});
    expect(missingTrips(journey, {})).toHaveLength(3);
    expect(missingTrips(journey, recordedTrips)).toEqual([]);
    const first = journey.legs[0]!.transit!.engineTripId;
    expect(missingTrips(journey, {}, [first])).toHaveLength(2);
  });
});

describe("fetching", () => {
  it("runs at most two requests at once and keeps input order", async () => {
    let inFlight = 0;
    let max = 0;
    const tasks = Array.from({ length: 7 }, (_, i) => async () => {
      inFlight += 1;
      max = Math.max(max, inFlight);
      await new Promise((resolve) => setTimeout(resolve, 1));
      inFlight -= 1;
      return i;
    });
    expect(await runPool(tasks)).toEqual([0, 1, 2, 3, 4, 5, 6]);
    expect(max).toBe(2);
  });

  it("fetches each stop once, concurrency 2; a failing stop disables cues for its ride only", async () => {
    const journey = recordedJourneys[2]!;
    const steps = buildSteps(journey, recordedTrips);
    const targets = callTargets(steps, recordedTrips);
    const allStops = new Set(Object.values(targets).flatMap((calls) => calls.map((c) => c.stopId)));
    const failing = targets[1]![0]!.stopId;
    const { api, calls } = fakeApi({ failStop: failing });
    const entries = await fetchCallPositions(targets, api.getStop);
    expect(calls.stops.length).toBe(allStops.size);
    expect(new Set(calls.stops).size).toBe(calls.stops.length);
    expect(calls.maxInFlight).toBe(2);
    expect(entries["1"]).toEqual({ status: "failed" });
    for (const key of Object.keys(targets).filter((k) => k !== "1")) {
      const entry = entries[key]!;
      expect(entry.status).toBe("ok");
      if (entry.status === "ok") expect(entry.positions.map((p) => p.ordinal)).toEqual(targets[Number(key)]!.map((c) => c.ordinal));
    }
    expect(Object.keys(engineCallPositions(entries))).not.toContain("1");
  });

  it("an aborted fetch stores nothing for the rides it did not finish", async () => {
    const journey = recordedJourneys[0]!;
    const targets = callTargets(buildSteps(journey, recordedTrips), recordedTrips);
    const controller = new AbortController();
    controller.abort();
    const { api, calls } = fakeApi();
    expect(await fetchCallPositions(targets, api.getStop, { signal: controller.signal })).toEqual({});
    expect(calls.stops).toEqual([]);
  });
});

describe("prefetch at Start", () => {
  it("requests a missing trip once, then call positions; nothing repeats, also after a reload", async () => {
    const journey = recordedJourneys[0]!;
    const missingRef = journey.legs[2]!.transit!.engineTripId;
    const trips = { ...recordedTrips };
    delete trips[missingRef];
    const trip = startActiveTrip({ journey, meta: {} as Metadata, trips });
    const first = fakeApi();
    await prefetchForTrip(trip.startedAt, first.api, new AbortController().signal);
    expect(first.calls.trips).toEqual([missingRef]);
    const stored = getActiveTrip()!;
    expect(stored.trips[missingRef]).toBeDefined();
    expect(stored.tripsRequested).toEqual([missingRef]);
    expect(Object.values(stored.callPositions ?? {}).every((entry) => entry.status === "ok")).toBe(true);
    expect(Object.keys(stored.callPositions ?? {})).toEqual(["0", "2", "4"]);
    const fetchedStops = first.calls.stops.length;
    expect(fetchedStops).toBeGreaterThan(0);
    expect(fetchedStops).toBeLessThanOrEqual(3 * CALLS_BEFORE_EXIT);

    const again = fakeApi();
    await prefetchForTrip(trip.startedAt, again.api, new AbortController().signal);
    resetActiveTripCache(); // reload: read back from sessionStorage
    expect(loadActiveTrip()?.callPositions).toEqual(stored.callPositions);
    await prefetchForTrip(trip.startedAt, again.api, new AbortController().signal);
    expect(again.calls).toMatchObject({ stops: [], trips: [] });
  });

  it("a trip that cannot be fetched is not requested again and its ride has no cues", async () => {
    const journey = recordedJourneys[0]!;
    const missingRef = journey.legs[2]!.transit!.engineTripId;
    const trips = { ...recordedTrips };
    delete trips[missingRef];
    const trip = startActiveTrip({ journey, meta: {} as Metadata, trips });
    const { api, calls } = fakeApi();
    api.getTrip = async (ref) => {
      calls.trips.push(ref);
      return { ok: false, error: { kind: "network" }, state: "network" };
    };
    await prefetchForTrip(trip.startedAt, api, new AbortController().signal);
    await prefetchForTrip(trip.startedAt, api, new AbortController().signal);
    expect(calls.trips).toEqual([missingRef]);
    expect(Object.keys(getActiveTrip()!.callPositions ?? {})).toEqual(["0", "4"]);
  });

  it("restore rejects malformed stored call positions", () => {
    const journey = recordedJourneys[0]!;
    startActiveTrip({ journey, meta: {} as Metadata, trips: recordedTrips });
    const raw = JSON.parse(sessionStorage.getItem("opentransit:activeTrip")!);
    raw.callPositions = { "0": { status: "ok", positions: [{ ordinal: "x" }] } };
    sessionStorage.setItem("opentransit:activeTrip", JSON.stringify(raw));
    resetActiveTripCache();
    expect(loadActiveTrip()).toBeNull();
  });
});
