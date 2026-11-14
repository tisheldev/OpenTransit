import { fixture, type Fixture } from "../api/fixtures";
import { haversineMeters } from "../nav/geo";

// SYNTHETIC answers for the stops-and-lines contracts A2 (lines) and A3 (a journey pinned to
// one trip), built in code from recorded-live-stop-lines (the lines through Dizengoff
// Center, 13583). Not recorded and not real API responses; for the MSW mock only. What is
// made up:
// - A line per recorded route there. Its key ("<operator>:9<number>", shaped like the real "5:55008") is invented:
//   the real key holds the MOT line code, which the recorded answers do not carry.
// - Each line's other direction: the recorded pattern reversed, on route
//   "<routeId>-back" (line 8's is "mot:route:16076", the id its recorded journeys use).
// - Departures of a line at any of its stops every 12 minutes from the request's `from`,
//   on trips "derived-line~<routeId>~<start>" that take 90 s per stop.
// - Journeys pinned to one of those trips: a straight walk to the board stop at 1.1 m/s
//   arriving a minute early, then the ride.

type Stop = { stopId: string; name: string | null; latitude: number; longitude: number; pickupType: number | null; dropOffType: number | null };
type Pattern = { patternId: string; routeId: string; directionId: string | null; headsign: string | null; servesStop: boolean; stopIndex: number | null; stops: Stop[] } & Record<string, unknown>;
type RouteLines = { routeId: string; routeShortName: string | null; operatorId: string | null; operatorName: string | null; mode: string | null; patterns: Pattern[] } & Record<string, unknown>;

export const DERIVED_TRIP_PREFIX = "derived-line~";
const HEADWAY_MIN = 12;
const SECONDS_PER_STOP = 90;

const recorded = () => fixture("recorded-live-stop-lines");
const routesAtStop = () => (recorded().body as { data: RouteLines[] }).data;

const BACK_IDS: Record<string, string> = { "mot:route:16077": "mot:route:16076" };
const backId = (routeId: string) => BACK_IDS[routeId] ?? `${routeId}-back`;

export interface DerivedLine {
  lineKey: string;
  route: RouteLines;
  /** Both directions, each one pattern: the recorded one and its reverse. */
  patterns: Pattern[];
}

function lines(): DerivedLine[] {
  return routesAtStop().map((route) => {
    const forward = [...route.patterns].sort((a, b) => b.stops.length - a.stops.length)[0]!;
    const stops = [...forward.stops].reverse();
    const back: Pattern = {
      ...forward,
      patternId: `${forward.patternId}-back`,
      routeId: backId(route.routeId),
      directionId: forward.directionId === "1" ? "0" : "1",
      headsign: forward.stops[0]?.name ?? null,
      stops,
    };
    return { lineKey: `${route.operatorId}:9${String(route.routeShortName).padStart(4, "0")}`, route, patterns: [{ ...forward, routeId: route.routeId }, back] };
  });
}

let cached: DerivedLine[] | null = null;
const allLines = () => (cached ??= lines());

const lineOfRoute = (routeId: string) => allLines().find((line) => line.patterns.some((pattern) => pattern.routeId === routeId)) ?? null;
const patternOfRoute = (routeId: string) => lineOfRoute(routeId)?.patterns.find((pattern) => pattern.routeId === routeId) ?? null;

/** The recorded meta, marked as fixture data: these answers are made up. */
const meta = () => ({ ...(recorded().body as { meta: Record<string, unknown> }).meta, mode: "fixture" });

function lineItem(line: DerivedLine, near: { latitude: number; longitude: number } | null) {
  const { route, patterns } = line;
  let nearestStop: { stopId: string; name: string | null; distanceM: number } | null = null;
  if (near) {
    for (const stop of patterns.flatMap((pattern) => pattern.stops)) {
      const distanceM = Math.round(haversineMeters(near, stop));
      if (distanceM <= 2000 && (!nearestStop || distanceM < nearestStop.distanceM)) nearestStop = { stopId: stop.stopId, name: stop.name, distanceM };
    }
  }
  return {
    lineKey: line.lineKey,
    shortName: route.routeShortName ?? "",
    operatorId: route.operatorId ?? "",
    operatorName: route.operatorName,
    mode: route.mode ?? "bus",
    routeIds: patterns.map((pattern) => pattern.routeId),
    directions: patterns.map((pattern) => ({
      routeId: pattern.routeId,
      headsign: pattern.headsign,
      originName: pattern.stops[0]?.name ?? null,
      destinationName: pattern.stops[pattern.stops.length - 1]?.name ?? null,
    })),
    area: "תל אביב-יפו",
    nearestStop,
  };
}

const answer = (path: string, body: unknown, status = 200): Fixture => ({
  request: { method: "GET", path, params: null, body: null },
  status,
  body,
});

function notFound(path: string, code: string, detail: string): Fixture {
  const base = fixture("synthetic-problem-stop-not-found");
  return { ...base, request: { ...base.request, path }, body: { ...(base.body as Record<string, unknown>), code, detail } };
}

const pointOf = (lat: string | null, lon: string | null) =>
  lat !== null && lon !== null && Number.isFinite(Number(lat)) && Number.isFinite(Number(lon)) ? { latitude: Number(lat), longitude: Number(lon) } : null;

/** A2 `GET /v1/lines/{lineKey}`. */
export function derivedLine(lineKey: string, lat: string | null, lon: string | null): Fixture {
  const line = allLines().find((item) => item.lineKey === lineKey);
  if (!line) return notFound(`/v1/lines/${lineKey}`, "NOT_FOUND", "No line with this key in this generation.");
  return answer(`/v1/lines/${lineKey}`, { data: lineItem(line, pointOf(lat, lon)), meta: meta() });
}

/** A2 `GET /v1/lines?q=`: number prefix, exact first, then by number. */
export function derivedLineSearch(q: string, lat: string | null, lon: string | null): Fixture {
  const query = q.trim().toLowerCase();
  const near = pointOf(lat, lon);
  const found = allLines()
    .filter((line) => query !== "" && (line.route.routeShortName ?? "").toLowerCase().startsWith(query))
    .sort((a, b) => {
      const exact = Number(b.route.routeShortName === query) - Number(a.route.routeShortName === query);
      return exact || (a.route.routeShortName ?? "").localeCompare(b.route.routeShortName ?? "", "en", { numeric: true });
    })
    .map((line) => lineItem(line, near));
  return answer("/v1/lines", { data: found, page: { nextCursor: null }, meta: meta() });
}

/** `GET /v1/stops/{id}/lines?patterns=all`: the recorded lines with each one's other direction. */
export function derivedStopLinesAll(stopId: string): Fixture {
  const base = recorded();
  const body = structuredClone(base.body) as { data: RouteLines[]; meta: unknown };
  body.meta = meta();
  body.data = body.data.map((route) => {
    const line = lineOfRoute(route.routeId)!;
    const back = line.patterns[1]!;
    const index = back.stops.findIndex((stop) => stop.stopId === stopId);
    return { ...route, patterns: [...route.patterns, { ...back, servesStop: index >= 0, stopIndex: index >= 0 ? index : null }] };
  });
  return { ...base, request: { ...base.request, path: `/v1/stops/${stopId}/lines`, params: { patterns: "all", limit: 50 } }, body };
}

/** `GET /v1/routes/{id}/patterns` for a derived line's route; null for any other route. */
export function derivedRoutePatterns(routeId: string): Fixture | null {
  const pattern = patternOfRoute(routeId);
  if (!pattern) return null;
  const data = [
    {
      patternId: pattern.patternId,
      routeId,
      directionId: pattern.directionId,
      headsign: pattern.headsign,
      stops: pattern.stops.map((stop, index) => ({ sequence: index + 1, stopId: stop.stopId, pickupType: stop.pickupType, dropOffType: stop.dropOffType })),
    },
  ];
  return answer(`/v1/routes/${routeId}/patterns`, { data, page: { nextCursor: null }, meta: meta() });
}

/**
 * Contract A1 `GET /v1/stops?bbox=…&mode=rail,light_rail`: a train station 60 m north of
 * every recorded pattern stop named "ת. רכבת …" (made up: the recorded answers hold no
 * stations), each with `mode: "rail"`.
 */
export function derivedRailStations(): Fixture {
  const seen = new Set<string>();
  const data = routesAtStop()
    .flatMap((route) => route.patterns.flatMap((pattern) => pattern.stops))
    .filter((stop) => /^ת\. רכבת/.test(stop.name ?? "") && !seen.has(stop.stopId) && (seen.add(stop.stopId), true))
    .map((stop) => ({
      stopId: `${stop.stopId}-station`,
      sourceId: `${stop.stopId}-station`,
      code: null,
      name: stop.name,
      description: null,
      latitude: stop.latitude + 0.00054,
      longitude: stop.longitude,
      locationType: 1,
      parentStationId: null,
      wheelchairBoarding: null,
      platformCode: null,
      mode: "rail",
      bearingDegrees: null,
      bearingSource: null,
    }));
  return answer("/v1/stops", { data, page: { nextCursor: null }, meta: meta() });
}

const iso = (ms: number) => new Date(ms).toISOString().replace(".000Z", "Z");
const tripRefOf = (routeId: string, startMs: number) => `${DERIVED_TRIP_PREFIX}${routeId}~${iso(startMs)}`;

function parseTripRef(tripRef: string): { routeId: string; start: number } | null {
  if (!tripRef.startsWith(DERIVED_TRIP_PREFIX)) return null;
  const [routeId, start] = tripRef.slice(DERIVED_TRIP_PREFIX.length).split("~");
  const at = Date.parse(start ?? "");
  return routeId && Number.isFinite(at) ? { routeId, start: at } : null;
}

const atStop = (start: number, index: number) => start + index * SECONDS_PER_STOP * 1000;
/** Whole minutes, as a timetable gives them. */
const minute = (ms: number) => Math.round(ms / 60_000) * 60_000;

/**
 * `GET /v1/stops/{id}/departures?routeId=…` for a derived line's route: every 12 minutes
 * from `from`. A route that is not a derived line, or a stop it does not call at, gets
 * departures on made-up trips ("derived-dep~…"), so a journey's ride has later times.
 */
export function derivedRouteDepartures(stopId: string, routeId: string, from: string | null, limit: number): Fixture {
  const base = fixture("recorded-live-departures-page-1");
  const sample = (base.body as { data: Array<Record<string, unknown>> }).data[0]!;
  const start = Number.isFinite(Date.parse(from ?? "")) ? Date.parse(from!) : Date.now();
  const pattern = patternOfRoute(routeId);
  const index = pattern ? pattern.stops.findIndex((stop) => stop.stopId === stopId) : -1;
  const line = lineOfRoute(routeId);
  const count = Math.max(1, Math.min(limit, 8));
  const data = Array.from({ length: count }, (_, n) => {
    const departs = minute(start + (2 + n * HEADWAY_MIN) * 60_000);
    if (pattern && line && index >= 0 && index < pattern.stops.length - 1) {
      const tripStart = departs - index * SECONDS_PER_STOP * 1000;
      return {
        ...sample,
        stopId,
        routeId,
        routeShortName: line.route.routeShortName ?? "",
        headsign: pattern.headsign,
        tripRef: tripRefOf(routeId, tripStart),
        callSequence: index + 1,
        scheduledDeparture: iso(minute(atStop(tripStart, index))),
        operatorId: line.route.operatorId,
        operatorName: line.route.operatorName,
        mode: line.route.mode,
        directionId: pattern.directionId,
      };
    }
    return { ...sample, stopId, routeId, tripRef: `derived-dep~${routeId}~${iso(departs)}`, callSequence: 1, scheduledDeparture: iso(departs) };
  });
  const body = structuredClone(base.body) as { data: unknown[]; page: { nextCursor: string | null } };
  body.data = data;
  body.page = { nextCursor: null };
  return { ...base, request: { ...base.request, path: `/v1/stops/${stopId}/departures` }, body };
}

/** `GET /v1/trips/{tripRef}` for a derived line's trip; null for any other ref. */
export function derivedLineTrip(tripRef: string): Fixture | null {
  const parsed = parseTripRef(tripRef);
  const pattern = parsed ? patternOfRoute(parsed.routeId) : null;
  const line = parsed ? lineOfRoute(parsed.routeId) : null;
  if (!parsed || !pattern || !line) return null;
  const last = pattern.stops.length - 1;
  const calls = pattern.stops.map((stop, index) => {
    const at = iso(minute(atStop(parsed.start, index)));
    return {
      callSequence: index + 1,
      ordinal: index,
      stopId: stop.stopId,
      scheduledArrival: index === 0 ? null : at,
      scheduledDeparture: index === last ? null : at,
      pickupType: index === last ? 1 : 0,
      dropOffType: index === 0 ? 1 : 0,
    };
  });
  const israel = new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Jerusalem", year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hourCycle: "h23" });
  const parts = Object.fromEntries(israel.formatToParts(new Date(parsed.start)).map((part) => [part.type, part.value]));
  const body = {
    data: {
      tripRef,
      sourceTripId: tripRef,
      serviceDate: `${parts.year}-${parts.month}-${parts.day}`,
      startTime: `${parts.hour}:${parts.minute}`,
      routeId: parsed.routeId,
      routeShortName: line.route.routeShortName ?? "",
      headsign: pattern.headsign,
      shape: { type: "LineString", coordinates: pattern.stops.map((stop) => [stop.longitude, stop.latitude]) },
      calls,
      timingState: "scheduled",
      expectedArrival: null,
      expectedDeparture: null,
      delaySeconds: null,
      alerts: "not_enabled",
    },
    meta: meta(),
  };
  return answer(`/v1/trips/${tripRef}`, body);
}

interface PinnedBody {
  from?: { kind?: string; latitude?: number; longitude?: number; stopId?: string };
  departAt?: string;
  pinnedTrip?: { tripRef?: string; boardStopId?: string; alightStopId?: string };
}

function problem(status: number, code: string, detail: string): Fixture {
  const base = fixture("synthetic-problem-invalid-request");
  return { ...base, status, body: { ...(base.body as Record<string, unknown>), status, code, detail } };
}

/** A3 `POST /v1/journeys` with `pinnedTrip`: walk to the board stop, then the ride. */
export function derivedPinnedJourney(request: PinnedBody): Fixture {
  const pinned = request.pinnedTrip ?? {};
  const parsed = parseTripRef(pinned.tripRef ?? "");
  const pattern = parsed ? patternOfRoute(parsed.routeId) : null;
  const line = parsed ? lineOfRoute(parsed.routeId) : null;
  if (!parsed || !pattern || !line) return problem(404, "TRIP_NOT_FOUND", "No trip with this reference in this generation.");
  const board = pattern.stops.findIndex((stop) => stop.stopId === pinned.boardStopId);
  const alight = pattern.stops.findIndex((stop) => stop.stopId === pinned.alightStopId);
  if (board < 0 || alight <= board) return problem(422, "INVALID_PINNED_TRIP", "The board and alight stops must be on the trip, alighting after boarding.");
  const boardStop = pattern.stops[board]!;
  const alightStop = pattern.stops[alight]!;
  const departs = minute(atStop(parsed.start, board));
  const arrives = minute(atStop(parsed.start, alight));
  const timing = (from: number, to: number) => ({
    scheduledDeparture: iso(from),
    scheduledArrival: iso(to),
    timingState: "scheduled",
    expectedDeparture: null,
    expectedArrival: null,
    delaySeconds: null,
    observedAt: null,
  });
  const place = (stop: Stop) => ({ name: stop.name ?? "", latitude: stop.latitude, longitude: stop.longitude, stopId: stop.stopId, stopCode: null });
  const origin =
    request.from?.kind === "coordinate" && typeof request.from.latitude === "number" && typeof request.from.longitude === "number"
      ? { latitude: request.from.latitude, longitude: request.from.longitude }
      : null;
  const legs: unknown[] = [];
  const warnings: string[] = [];
  let walkSeconds = 0;
  let walkMeters = 0;
  if (origin && haversineMeters(origin, boardStop) > 30) {
    walkMeters = Math.round(haversineMeters(origin, boardStop) * 1.25);
    walkSeconds = Math.max(60, Math.round(walkMeters / 1.1 / 60) * 60);
    const arriveAtStop = departs - 60_000;
    const leave = arriveAtStop - walkSeconds * 1000;
    if (request.departAt && leave < Date.parse(request.departAt)) warnings.push("PINNED_TRIP_MISSED_BY_WALK");
    legs.push({
      kind: "walk",
      mode: "walk",
      from: { name: "START", latitude: origin.latitude, longitude: origin.longitude, stopId: null, stopCode: null },
      to: place(boardStop),
      timing: timing(leave, arriveAtStop),
      durationSeconds: walkSeconds,
      distanceMeters: walkMeters,
      geometry: { type: "LineString", coordinates: [[origin.longitude, origin.latitude], [boardStop.longitude, boardStop.latitude]] },
      geometryUnavailableReason: null,
      transit: null,
    });
  }
  const israel = new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Jerusalem", year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hourCycle: "h23" });
  const parts = Object.fromEntries(israel.formatToParts(new Date(parsed.start)).map((part) => [part.type, part.value]));
  legs.push({
    kind: "transit",
    mode: line.route.mode ?? "bus",
    from: place(boardStop),
    to: place(alightStop),
    timing: timing(departs, arrives),
    durationSeconds: (arrives - departs) / 1000,
    distanceMeters: null,
    geometry: { type: "LineString", coordinates: pattern.stops.slice(board, alight + 1).map((stop) => [stop.longitude, stop.latitude]) },
    geometryUnavailableReason: null,
    transit: {
      operatorId: line.route.operatorId ?? "",
      operatorName: line.route.operatorName ?? "",
      routeId: parsed.routeId,
      routeShortName: line.route.routeShortName ?? "",
      headsign: pattern.headsign,
      engineTripId: pinned.tripRef,
      sourceTripId: pinned.tripRef,
      serviceDate: `${parts.year}-${parts.month}-${parts.day}`,
      startTime: `${parts.hour}:${parts.minute}`,
    },
    intermediateStops: pattern.stops.slice(board + 1, alight).map((stop, offset) => {
      const at = iso(minute(atStop(parsed.start, board + 1 + offset)));
      return { name: stop.name ?? "", stopId: stop.stopId, latitude: stop.latitude, longitude: stop.longitude, scheduledArrival: at, scheduledDeparture: at };
    }),
    boarding: { bearingDegrees: null, stopSide: null, towards: pattern.stops[board + 1]?.name ?? null, stopCount: alight - board },
  });
  const first = legs[0] as { timing: { scheduledDeparture: string } };
  const journey = {
    id: `pinned-${pinned.tripRef}`,
    timing: timing(Date.parse(first.timing.scheduledDeparture), arrives),
    durationSeconds: (arrives - Date.parse(first.timing.scheduledDeparture)) / 1000,
    walkingSeconds: walkSeconds,
    walkingDistanceMeters: walkMeters,
    transfers: 0,
    legs,
  };
  return {
    request: { method: "POST", path: "/v1/journeys", params: null, body: request },
    status: 200,
    body: { data: { outcome: "routes_found", journeys: [journey], alerts: null }, meta: { ...meta(), rankingPolicy: "pinned-trip-v1", warnings } },
  };
}
