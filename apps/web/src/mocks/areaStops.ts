import { fixture, type Fixture } from "../api/fixtures";

// DERIVED answers for GET /v1/stops?bbox=…[&mode=…] (the stops layer; A1 adds the mode
// filter), built at runtime from recorded fixtures; none is presented as a real API answer.
//
// - Bus stops: every stop on the recorded lines through Dizengoff Center
//   (recorded-live-stop-lines, 226 stops on 7 lines' patterns) and the five recorded stops
//   around it (recorded-live-stops-near). Each takes its line's mode and a direction of
//   travel computed the way API-C6 does (the straight line to the next stop on each
//   pattern, their circular mean when 80% agree, else null); a stop only ever last on a
//   pattern takes the line from the previous stop. The five recorded nearby stops not on
//   those patterns keep no direction.
// - Stations: the rail stops the recorded journeys ride from or to (recorded-journey-*),
//   mode "rail", with no direction.
// - The area limit: 100 km², or 120,000 km² when every listed mode is rail or light rail
//   (A1); beyond it a 422 derived from synthetic-problem-invalid-request.
// - Paging: 100 a page by default, the cursor an offset ("derived-<n>").

interface DerivedStop {
  stopId: string;
  sourceId: string;
  code: string | null;
  name: string | null;
  description: null;
  latitude: number;
  longitude: number;
  locationType: number;
  parentStationId: null;
  wheelchairBoarding: null;
  platformCode: null;
  mode: string | null;
  bearingDegrees: number | null;
  bearingSource: "next_stop" | "previous_stop" | null;
}

const toRad = (deg: number) => (deg * Math.PI) / 180;

/** Initial great-circle bearing, degrees clockwise from north; null for one point. */
function initialBearing(lat1: number, lon1: number, lat2: number, lon2: number): number | null {
  if (lat1 === lat2 && lon1 === lon2) return null;
  const y = Math.sin(toRad(lon2 - lon1)) * Math.cos(toRad(lat2));
  const x = Math.cos(toRad(lat1)) * Math.sin(toRad(lat2)) - Math.sin(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.cos(toRad(lon2 - lon1));
  return ((Math.atan2(y, x) * 180) / Math.PI + 360) % 360;
}

function meanBearing(bearings: number[]): number | null {
  if (bearings.length === 0) return null;
  const east = bearings.reduce((sum, b) => sum + Math.sin(toRad(b)), 0);
  const north = bearings.reduce((sum, b) => sum + Math.cos(toRad(b)), 0);
  if (Math.hypot(east, north) / bearings.length < 0.8) return null;
  return Math.round((((Math.atan2(east, north) * 180) / Math.PI + 360) % 360) * 10) / 10 % 360;
}

type Pattern = { stops: Array<{ stopId: string; name: string | null; latitude: number; longitude: number }> };
type Line = { mode: string | null; patterns: Pattern[] };

let built: DerivedStop[] | null = null;

function derivedStops(): DerivedStop[] {
  if (built) return built;
  const lines = (fixture("recorded-live-stop-lines").body as { data: Line[] }).data;
  const byId = new Map<string, { stop: Pattern["stops"][number]; mode: string; next: number[]; previous: number[] }>();
  for (const line of lines) {
    for (const pattern of line.patterns) {
      pattern.stops.forEach((stop, index) => {
        const entry = byId.get(stop.stopId) ?? { stop, mode: line.mode ?? "bus", next: [], previous: [] };
        const after = pattern.stops[index + 1];
        const before = pattern.stops[index - 1];
        const forward = after ? initialBearing(stop.latitude, stop.longitude, after.latitude, after.longitude) : null;
        const backward = before ? initialBearing(before.latitude, before.longitude, stop.latitude, stop.longitude) : null;
        if (forward !== null) entry.next.push(forward);
        if (backward !== null) entry.previous.push(backward);
        byId.set(stop.stopId, entry);
      });
    }
  }
  const out: DerivedStop[] = [...byId.values()].map(({ stop, mode, next, previous }) => {
    const bearing = next.length > 0 ? meanBearing(next) : meanBearing(previous);
    return {
      stopId: stop.stopId,
      sourceId: stop.stopId.replace(/^mot:stop:/, ""),
      code: null,
      name: stop.name,
      description: null,
      latitude: stop.latitude,
      longitude: stop.longitude,
      locationType: 0,
      parentStationId: null,
      wheelchairBoarding: null,
      platformCode: null,
      mode,
      bearingDegrees: bearing,
      bearingSource: bearing === null ? null : next.length > 0 ? "next_stop" : "previous_stop",
    };
  });
  const near = (fixture("recorded-live-stops-near").body as { data: Array<Record<string, unknown>> }).data;
  for (const item of near) {
    const found = out.find((stop) => stop.stopId === item.stopId);
    if (found) {
      found.code = (item.code as string | null) ?? null;
      continue;
    }
    out.push({
      stopId: String(item.stopId),
      sourceId: String(item.sourceId),
      code: (item.code as string | null) ?? null,
      name: (item.name as string | null) ?? null,
      description: null,
      latitude: Number(item.latitude),
      longitude: Number(item.longitude),
      locationType: 0,
      parentStationId: null,
      wheelchairBoarding: null,
      platformCode: null,
      mode: "bus",
      bearingDegrees: null,
      bearingSource: null,
    });
  }
  for (const name of ["recorded-journey-routes", "recorded-journey-poi"]) {
    const journeys = (fixture(name).body as { data: { journeys: Array<{ legs: Array<Record<string, unknown>> }> } }).data.journeys;
    for (const leg of journeys.flatMap((journey) => journey.legs)) {
      if (String(leg.mode).toLowerCase() !== "rail") continue;
      for (const end of [leg.from, leg.to] as Array<Record<string, unknown> | undefined>) {
        const stopId = end?.stopId;
        if (typeof stopId !== "string" || out.some((stop) => stop.stopId === stopId)) continue;
        out.push({
          stopId,
          sourceId: stopId.replace(/^mot:stop:/, ""),
          code: null,
          name: (end!.name as string | null) ?? null,
          description: null,
          latitude: Number(end!.latitude ?? end!.lat),
          longitude: Number(end!.longitude ?? end!.lon),
          locationType: 0,
          parentStationId: null,
          wheelchairBoarding: null,
          platformCode: null,
          mode: "rail",
          bearingDegrees: null,
          bearingSource: null,
        });
      }
    }
  }
  built = out.filter((stop) => Number.isFinite(stop.latitude) && Number.isFinite(stop.longitude));
  return built;
}

const STATION_ONLY = new Set(["rail", "light_rail"]);

function invalid(detail: string): Fixture {
  const base = fixture("synthetic-problem-invalid-request");
  return { ...base, body: { ...(base.body as Record<string, unknown>), detail } };
}

/** The answer to one bbox request (derived; see the file comment). */
export function derivedAreaStops(url: URL): Fixture {
  const parts = (url.searchParams.get("bbox") ?? "").split(",").map(Number);
  if (parts.length !== 4 || parts.some((n) => !Number.isFinite(n))) return invalid("Use bbox=west,south,east,north.");
  const [west, south, east, north] = parts as [number, number, number, number];
  const modes = (url.searchParams.get("mode") ?? "")
    .split(",")
    .map((mode) => mode.trim())
    .filter(Boolean);
  const mid = toRad((north + south) / 2);
  const km2 = (east - west) * 111.32 * Math.cos(mid) * (north - south) * 110.57;
  const limit = modes.length > 0 && modes.every((mode) => STATION_ONLY.has(mode)) ? 120_000 : 100;
  if (km2 > limit) return invalid(`The area is ${Math.round(km2)} km²; at most ${limit} km² for these modes.`);
  const all = derivedStops().filter(
    (stop) =>
      stop.longitude >= west &&
      stop.longitude <= east &&
      stop.latitude >= south &&
      stop.latitude <= north &&
      (modes.length === 0 || (stop.mode !== null && modes.includes(stop.mode))),
  );
  const pageSize = Math.max(1, Math.min(100, Number(url.searchParams.get("limit") ?? 20)));
  const offset = Number(/^derived-(\d+)$/.exec(url.searchParams.get("cursor") ?? "")?.[1] ?? 0);
  const data = all.slice(offset, offset + pageSize);
  const base = fixture("recorded-live-stops-near");
  const body = structuredClone(base.body) as { data: unknown[]; page: { nextCursor: string | null } };
  body.data = data;
  body.page = { nextCursor: offset + pageSize < all.length ? `derived-${offset + pageSize}` : null };
  return { ...base, request: { method: "GET", path: "/v1/stops", params: Object.fromEntries(url.searchParams), body: null }, body };
}
