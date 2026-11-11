import { fixture, type Fixture } from "../api/fixtures";

// DERIVED answers for Home and the stop screen (boards 1 and 7), built at runtime from
// recorded fixtures; none is presented as a real API response.
//
// - Nearby departures and a stop's lines (API PR #35): see the two functions below.
// - The fallbacks for an API without them:
// - Nearby stops: recorded-live-stops-near (five real stops around Dizengoff Center).
// - A nearby stop's detail: recorded-live-stop (13583) with the id, name, code and position
//   of that stop from the nearby list; its routes are 13583's, not the stop's own.
// - Departures: the recorded departures of 13583 (two recordings), re-timed to leave a few
//   minutes after the request's `from`, so minutes count down in fixture mode. Line 8 and
//   line 5 point at the recorded trips that carry a shape (recorded-trip-overnight,
//   recorded-trip-dst-fold-first), so their routes can be drawn; the others keep their
//   own refs, which the fixtures do not hold (a line without a shape).

/**
 * recorded-live-departures-nearby (board 1, API PR #35) re-timed: each stop's departures
 * leave 2, 5, 9 and 11 minutes after the request's `from`, in their recorded order.
 */
export function derivedNearbyDepartures(from: string | null): Fixture {
  const base = fixture("recorded-live-departures-nearby");
  const body = structuredClone(base.body) as { data: Array<{ departures: Array<Record<string, unknown>> | null }> };
  const start = Number.isFinite(Date.parse(from ?? "")) ? Date.parse(from!) : Date.now();
  for (const entry of body.data) {
    entry.departures = entry.departures?.map((item, index) => ({
      ...item,
      scheduledDeparture: new Date(start + OFFSETS[index % OFFSETS.length]! * 60_000 - 30_000).toISOString(),
    })) ?? null;
  }
  return { ...base, body };
}

/**
 * recorded-live-stop-lines (board 7, API PR #35): the lines through Dizengoff Center. Any
 * other stop gets the same answer (derived: its lines are 13583's, not its own).
 */
export function derivedStopLines(stopId: string): Fixture {
  const base = fixture("recorded-live-stop-lines");
  return stopId === "mot:stop:13583" ? base : { ...base, request: { ...base.request, path: `/v1/stops/${stopId}/lines` } };
}

type Body ={ data: Array<Record<string, unknown>>; page: { nextCursor: string | null }; meta: Record<string, unknown> };

const nearBody = () => fixture("recorded-live-stops-near").body as Body;

export function derivedStopsNear(): Fixture {
  const base = fixture("recorded-live-stops-near");
  const body = structuredClone(base.body) as Body;
  body.page = { nextCursor: null };
  return { ...base, body };
}

/** recorded-live-stop with the identity and position of another nearby stop; null if not nearby. */
export function derivedNearbyStop(stopId: string): Fixture | null {
  const near = nearBody().data.find((stop) => stop.stopId === stopId);
  if (!near) return null;
  const base = fixture("recorded-live-stop");
  const body = structuredClone(base.body) as { data: Record<string, unknown> };
  const stop = { ...near };
  delete stop.distanceMeters;
  body.data = { ...body.data, ...stop, translations: {}, children: [] };
  return { ...base, request: { ...base.request, path: `/v1/stops/${stopId}` }, body };
}

/** Trip refs that the fixtures hold, by line: their shapes pass the recorded stop. */
const SHAPED_TRIPS: Record<string, string> = {
  "8": "20260930_23:50_mot60day_584668860_300926",
  "5": "20261025_00:00_mot60day_463093_081026",
};
/** Minutes after `from` each re-timed departure leaves. */
const OFFSETS = [2, 5, 9, 11, 14, 18, 23, 27];

export function derivedDepartures(stopId: string, from: string | null, limit: number): Fixture {
  const base = fixture("recorded-live-departures-page-1");
  const recorded = [
    "recorded-live-departures-page-1",
    "recorded-live-departures-page-2",
    "recorded-departures-page-1",
    "recorded-departures-page-2",
  ].flatMap((name) => (fixture(name).body as Body).data);
  const start = Number.isFinite(Date.parse(from ?? "")) ? Date.parse(from!) : Date.now();
  const data = recorded.slice(0, Math.min(limit, OFFSETS.length)).map((item, index) => ({
    ...item,
    stopId,
    tripRef: SHAPED_TRIPS[String(item.routeShortName)] ?? item.tripRef,
    // Half a minute early, so a screen whose clock read a little before `from` still
    // counts whole minutes ("2 דק׳" for the first).
    scheduledDeparture: new Date(start + OFFSETS[index]! * 60_000 - 30_000).toISOString(),
  }));
  const body = structuredClone(base.body) as Body;
  // The recorded cursor stays: the next page is the recorded second page.
  body.data = data;
  return { ...base, request: { ...base.request, path: `/v1/stops/${stopId}/departures` }, body };
}
