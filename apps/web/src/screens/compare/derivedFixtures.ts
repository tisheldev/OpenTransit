import { fixture, type Fixture } from "../../api/fixtures";
import type { Trip } from "../../api/schemas";
import type { Journey, JourneyResponse, Leg } from "../../api/types";

// DERIVED fixtures for Compare states no recorded or synthetic fixture covers. They are
// built in code from committed recorded fixtures (deterministic edits listed per entry)
// so src/api/fixtures keeps only recorded/synthetic files: its provenance test accepts
// those two kinds alone. The coordinator may move them to derived-journey-*.json files
// once that test accepts "derived". Fixture mode is always labelled test data.

type Body = JourneyResponse;

const recorded = (name: string) => structuredClone(fixture(name)) as Fixture & { body: Body };
const shiftIso = (iso: string, seconds: number) => new Date(Date.parse(iso) + seconds * 1000).toISOString().replace(".000Z", "Z");

function shiftLeg(leg: Leg, seconds: number, suffix: string): Leg {
  return {
    ...leg,
    timing: {
      ...leg.timing,
      scheduledDeparture: shiftIso(leg.timing.scheduledDeparture, seconds),
      scheduledArrival: shiftIso(leg.timing.scheduledArrival, seconds),
    },
    transit: leg.transit ? { ...leg.transit, engineTripId: `${leg.transit.engineTripId}${suffix}` } : null,
  };
}

function journeyFrom(id: string, legs: Leg[]): Journey {
  const walks = legs.filter((leg) => leg.kind === "walk");
  const rides = legs.filter((leg) => leg.kind === "transit");
  const departure = legs[0]!.timing.scheduledDeparture;
  const arrival = legs[legs.length - 1]!.timing.scheduledArrival;
  const distances = walks.map((leg) => leg.distanceMeters);
  return {
    id,
    timing: { ...legs[0]!.timing, scheduledDeparture: departure, scheduledArrival: arrival },
    durationSeconds: (Date.parse(arrival) - Date.parse(departure)) / 1000,
    walkingSeconds: walks.reduce((sum, leg) => sum + leg.durationSeconds, 0),
    walkingDistanceMeters: distances.some((d) => d === null) ? null : distances.reduce<number>((s, d) => s + (d ?? 0), 0),
    transfers: Math.max(0, rides.length - 1),
    legs,
  };
}

function response(journeys: Journey[], outcome: "routes_found" | "no_route" = "routes_found"): Fixture {
  const base = recorded("recorded-journey-routes");
  const warnings = journeys.some((j) => j.legs.some((leg) => leg.geometryUnavailableReason === "street_path_unavailable"))
    ? ["TRANSFER_STREET_PATH_UNAVAILABLE"]
    : [];
  return {
    ...base,
    request: { ...base.request, body: { ...(base.request.body as object), results: 3 } },
    body: { data: { outcome, journeys }, meta: { ...base.body.meta, warnings } },
  };
}

/**
 * Option 1: the recorded journey (bus 8 → rail → bus 1), unchanged.
 * Option 2: option 1 shifted +20 min (trip IDs suffixed "~d2"); the walk between rail and
 *   bus is time-only (distance/geometry null, street_path_unavailable, as on the real
 *   oct31a answer) and the last walk is 60 s shorter (distance 270 m), so it is strictly
 *   fastest and walks least.
 * Option 3: the recorded place-ref journey (4 transfers, walk from START), unchanged.
 */
function threeJourneys(): Journey[] {
  const one = recorded("recorded-journey-routes").body.data.journeys[0]!;
  const three = recorded("recorded-journey-poi").body.data.journeys[0]!;
  const legs = one.legs.map((leg) => shiftLeg(leg, 20 * 60, "~d2"));
  const interior = legs[3]!;
  legs[3] = { ...interior, distanceMeters: null, geometry: null, geometryUnavailableReason: "street_path_unavailable" };
  const lastWalk = legs[legs.length - 1]!;
  legs[legs.length - 1] = {
    ...lastWalk,
    durationSeconds: lastWalk.durationSeconds - 60,
    distanceMeters: 270,
    timing: { ...lastWalk.timing, scheduledArrival: shiftIso(lastWalk.timing.scheduledArrival, -60) },
  };
  return [one, journeyFrom(`${one.id}~d2`, legs), three];
}

/** Option 1 alone is a walk: START → END, 18 min, 1.4 km, a straight two-point line. */
function walkOnlyJourney(): Journey {
  const one = recorded("recorded-journey-routes").body.data.journeys[0]!;
  const departure = one.timing.scheduledDeparture;
  const walk: Leg = {
    kind: "walk",
    mode: "walk",
    from: { name: "START", latitude: 32.0753, longitude: 34.7749, stopId: null, stopCode: null },
    to: { name: "END", latitude: 32.0861, longitude: 34.7818, stopId: null, stopCode: null },
    timing: { ...one.timing, scheduledDeparture: departure, scheduledArrival: shiftIso(departure, 18 * 60) },
    durationSeconds: 18 * 60,
    distanceMeters: 1400,
    geometry: { type: "LineString", coordinates: [[34.7749, 32.0753], [34.7818, 32.0861]] },
    geometryUnavailableReason: null,
    transit: null,
  };
  return journeyFrom("journey-derived-walk-only", [walk]);
}

export const derivedJourneyFixtures = {
  /** Three options (see threeJourneys). */
  "derived-journey-three": () => response(threeJourneys()),
  /** The first two of the three. */
  "derived-journey-two": () => response(threeJourneys().slice(0, 2)),
  /** The recorded answer's meta with outcome no_route and no journeys. */
  "derived-journey-no-route": () => response([], "no_route"),
  /** A walk-only option followed by the recorded transit option. */
  "derived-journey-walk-only": () =>
    response([walkOnlyJourney(), recorded("recorded-journey-routes").body.data.journeys[0]!]),
} as const;

/** 504 ENGINE_TIMEOUT: the recorded 503 problem with its status, code, type and title changed. */
export function derivedEngineTimeout(): Fixture {
  const base = structuredClone(fixture("recorded-problem-not-ready"));
  return {
    ...base,
    status: 504,
    body: {
      ...(base.body as object),
      type: "urn:opentransit:problem:engine-timeout",
      title: "Engine timeout",
      status: 504,
      code: "ENGINE_TIMEOUT",
      detail: "The routing engine did not answer in time.",
    },
  };
}

/** Every transit leg of the derived answers, by engineTripId (for derived trip details). */
function legsByTrip(): Map<string, { leg: Leg; meta: Body["meta"] }> {
  const map = new Map<string, { leg: Leg; meta: Body["meta"] }>();
  for (const build of Object.values(derivedJourneyFixtures)) {
    const body = build().body as Body;
    for (const journey of body.data.journeys)
      for (const leg of journey.legs) if (leg.transit) map.set(leg.transit.engineTripId, { leg, meta: body.meta });
  }
  return map;
}

let cachedLegs: ReturnType<typeof legsByTrip> | null = null;

/**
 * A derived trip detail for a derived journey's ride: boarding call at the leg's stop and
 * time, one invented intermediate call per 2.5 min of riding ("derived:stop:N"), exit call
 * at the leg's end. Only the stop count it yields is used; it is test data, not a timetable.
 */
export function derivedTrip(tripRef: string): Fixture | null {
  cachedLegs ??= legsByTrip();
  const found = cachedLegs.get(tripRef);
  if (!found?.leg.transit) return null;
  const { leg, meta } = found;
  const transit = leg.transit!;
  const departure = Date.parse(leg.timing.scheduledDeparture);
  const ride = leg.durationSeconds * 1000;
  const between = Math.max(0, Math.round(leg.durationSeconds / 150) - 1);
  const iso = (at: number) => new Date(at).toISOString().replace(".000Z", "Z");
  const call = (ordinal: number, stopId: string, at: number, first: boolean, last: boolean) => ({
    callSequence: ordinal + 1,
    ordinal,
    stopId,
    scheduledArrival: first ? null : iso(at),
    scheduledDeparture: last ? null : iso(at),
    pickupType: last ? 1 : 0,
    dropOffType: first ? 1 : 0,
  });
  const calls = [call(0, leg.from.stopId ?? "derived:stop:from", departure, true, false)];
  for (let i = 1; i <= between; i += 1) {
    calls.push(call(i, `derived:stop:${i}`, departure + Math.round((ride * i) / (between + 1) / 60_000) * 60_000, false, false));
  }
  calls.push(call(between + 1, leg.to.stopId ?? "derived:stop:to", departure + ride, false, true));
  const body: Trip = {
    data: {
      tripRef,
      sourceTripId: transit.sourceTripId,
      serviceDate: transit.serviceDate,
      startTime: transit.startTime,
      routeId: transit.routeId,
      routeShortName: transit.routeShortName,
      headsign: transit.headsign,
      shape: leg.geometry ? { type: "LineString", coordinates: leg.geometry.coordinates } : null,
      calls,
      timingState: "scheduled",
      expectedArrival: null,
      expectedDeparture: null,
      delaySeconds: null,
      alerts: "not_enabled",
    },
    meta: meta as Trip["meta"],
  };
  return { request: { method: "GET", path: `/v1/trips/${tripRef}`, params: null, body: null }, status: 200, body };
}
