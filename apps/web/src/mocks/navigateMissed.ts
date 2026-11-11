import { fixture, type Fixture } from "../api/fixtures";
import type { DeparturesPage } from "../api/schemas";
import type { Journey, JourneyRequest, JourneyResponse, Leg } from "../api/types";
import { haversineMeters } from "../nav/geo";
import recorded from "../nav/testdata/recorded-oct31a-dizengoff-technion.json";

// DERIVED answers (not recorded) for Navigate's "Bus didn't come" (board 6), built in
// code from the recorded oct31a journeys (src/nav/testdata). The passenger is on journey 2,
// walking to bus 249 at דיזנגוף סנטר/טשרניחובסקי (08:38). Edits, all deterministic:
// - departures there: the 249 that did not come (08:38, its recorded trip), the recorded
//   bus 8 trip's time at another line's slot, and a next 249 at 08:58 (trip ref made up);
// - "wait here": journey 2 from the stop, every leg 20 minutes later (trip IDs suffixed
//   "~wait"), so its first ride is that 08:58 bus;
// - "walk to another stop": journey 1 15 minutes later (trip IDs suffixed "~walk") after
//   a made-up 3-minute straight walk from the passenger's stop to its first stop.
// Mocked e2e reads them under the fixture scenario "navigate-missed"; unit tests use them
// through server.use(). None is presented as a real API response.

const data = recorded as unknown as { journeys: JourneyResponse };
const journeys = data.journeys.data.journeys;

export const MISSED_JOURNEY_INDEX = 2;
const missedJourney = journeys[MISSED_JOURNEY_INDEX]!;
const missedLeg = missedJourney.legs[1]!;
/** The stop where the 249 did not come. */
export const MISSED_STOP_ID = missedLeg.from.stopId!;
export const NEXT_249_AT = "2026-11-02T06:58:00Z";

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

function journeyOf(id: string, legs: Leg[]): Journey {
  const walks = legs.filter((leg) => leg.kind === "walk");
  const rides = legs.filter((leg) => leg.kind === "transit");
  const departure = legs[0]!.timing.scheduledDeparture;
  const arrival = legs[legs.length - 1]!.timing.scheduledArrival;
  const distances = walks.map((leg) => leg.distanceMeters);
  return {
    ...missedJourney,
    id,
    timing: { ...legs[0]!.timing, scheduledDeparture: departure, scheduledArrival: arrival },
    durationSeconds: (Date.parse(arrival) - Date.parse(departure)) / 1000,
    walkingSeconds: walks.reduce((sum, leg) => sum + leg.durationSeconds, 0),
    walkingDistanceMeters: distances.some((d) => d === null) ? null : distances.reduce<number>((s, d) => s + (d ?? 0), 0),
    transfers: Math.max(0, rides.length - 1),
    legs,
  };
}

function journeysFixture(list: Journey[], request: unknown): Fixture {
  const body = structuredClone(data.journeys) as JourneyResponse;
  body.data = { ...body.data, journeys: list };
  // The nav test data was sanitised of request IDs; a response carries one.
  body.meta = { ...body.meta, requestId: "00000000000000000000000000000000" };
  return { request: { method: "POST", path: "/v1/journeys", params: null, body: request }, status: 200, body };
}

/** "Wait here": journey 2 from the stop, 20 minutes later (its first ride is the 08:58 249). */
export function derivedWaitJourney(): Journey {
  return journeyOf("derived-missed-wait", missedJourney.legs.slice(1).map((leg) => shiftLeg(leg, 20 * 60, "~wait")));
}

/** "Walk to another stop": a 3-minute walk to bus 8's stop, then journey 1 15 minutes later. */
export function derivedWalkJourney(): Journey {
  const later = journeys[1]!.legs.map((leg) => shiftLeg(leg, 15 * 60, "~walk"));
  const first = later[0]!;
  const start = missedLeg.from;
  const departs = shiftIso(first.timing.scheduledDeparture, -180);
  const walk: Leg = {
    ...missedJourney.legs[0]!,
    from: { ...start },
    to: { ...first.from },
    timing: { ...first.timing, scheduledDeparture: departs, scheduledArrival: first.timing.scheduledDeparture },
    durationSeconds: 180,
    distanceMeters: Math.round(haversineMeters(start, first.from)),
    geometry: { type: "LineString", coordinates: [[start.longitude, start.latitude], [first.from.longitude, first.from.latitude]] },
    transit: null,
  };
  return journeyOf("derived-missed-walk", [walk, ...later]);
}

/** The journeys answer for a re-plan: from the stop → wait here; from a coordinate → walk elsewhere. */
export function derivedMissedJourneys(request: Partial<JourneyRequest> | null): Fixture {
  const fromStop = request?.from && "kind" in request.from && request.from.kind === "stop";
  return journeysFixture(fromStop ? [derivedWaitJourney()] : [derivedWalkJourney()], request);
}

/** Departures at the stop: the missed 249, another line, and the next 249 at 08:58. */
export function derivedMissedDepartures(): Fixture {
  const base = structuredClone(fixture("recorded-departures-page-1")) as Fixture & { body: DeparturesPage };
  const transit = missedLeg.transit!;
  const item = (at: string, routeId: string, short: string, headsign: string, tripRef: string) => ({
    scheduledDeparture: at,
    stopId: MISSED_STOP_ID,
    routeId,
    routeShortName: short,
    headsign,
    platformCode: null,
    pickupType: 0,
    tripRef,
    callSequence: 10,
  });
  base.body.data = [
    item(new Date(missedLeg.timing.scheduledDeparture).toISOString().replace(".000Z", "Z"), transit.routeId, transit.routeShortName, transit.headsign ?? "", transit.engineTripId),
    item("2026-11-02T06:45:00Z", "mot:route:derived-other", "5", "רידינג", "derived-other-0845"),
    item(NEXT_249_AT, transit.routeId, transit.routeShortName, transit.headsign ?? "", "derived-249-0858"),
  ];
  base.body.page = { nextCursor: null };
  base.request = { ...base.request, path: `/v1/stops/${MISSED_STOP_ID}/departures` };
  return base;
}
