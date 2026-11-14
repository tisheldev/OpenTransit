import { fixture, type Fixture } from "../api/fixtures";
import type { LineItem } from "../api/schemas";
import { haversineMeters } from "../nav/geo";

// Line search and one line (API contract A2), answered from synthetic-lines: a catalogue
// hand-written to the contract (SYNTHETIC: invented lines and route ids, the recorded stops
// around Dizengoff Center as their nearest stops). The search is run here the way the
// contract describes it, so the client's handling of one-character queries, exact-first
// order, operators sharing a number and "N more lines" can be tried in fixture mode.

type LinesBody = { data: LineItem[]; page: { nextCursor: string | null }; meta: Record<string, unknown> };

const catalogue = (): Fixture => fixture("synthetic-lines");
const stopsNear = () =>
  (fixture("recorded-live-stops-near").body as { data: Array<{ stopId: string; latitude: number; longitude: number }> }).data;

/** Contract A2: within 2 km of the passenger, else null. */
const NEAREST_STOP_METERS = 2000;

/** As the API: `nearestStop` absent without lat/lon, null when no stop is within 2 km. */
function withNearest(line: LineItem, near: { latitude: number; longitude: number } | null): LineItem {
  if (!near) {
    const rest: LineItem = { ...line };
    delete rest.nearestStop;
    return rest;
  }
  if (!line.nearestStop) return { ...line, nearestStop: null };
  const stop = stopsNear().find((item) => item.stopId === line.nearestStop!.stopId);
  if (!stop) return { ...line, nearestStop: null };
  const distanceM = Math.round(haversineMeters(near, stop));
  return { ...line, nearestStop: distanceM <= NEAREST_STOP_METERS ? { ...line.nearestStop, distanceM } : null };
}

function point(url: URL): { latitude: number; longitude: number } | null {
  const lat = Number(url.searchParams.get("lat"));
  const lon = Number(url.searchParams.get("lon"));
  return url.searchParams.has("lat") && url.searchParams.has("lon") && Number.isFinite(lat) && Number.isFinite(lon)
    ? { latitude: lat, longitude: lon }
    : null;
}

const numeric = (name: string) => {
  const match = /^\d+/.exec(name);
  return match ? Number(match[0]) : Number.POSITIVE_INFINITY;
};

/**
 * The requests the API refuses with 422 INVALID_REQUEST: an empty or blank `q`, a `q` over
 * 50 characters, or `lat` without `lon` (and the reverse).
 */
export function invalidLineSearch(url: URL): boolean {
  const q = (url.searchParams.get("q") ?? "").trim();
  return q === "" || (url.searchParams.get("q") ?? "").length > 50 || url.searchParams.has("lat") !== url.searchParams.has("lon");
}

/** GET /v1/lines?q=: prefix on the number, exact first, then nearest, then by number (8, 8א, 80, 82). */
export function derivedLineSearch(url: URL): Fixture {
  const base = catalogue();
  const body = structuredClone(base.body) as LinesBody;
  const q = (url.searchParams.get("q") ?? "").trim().toLocaleLowerCase();
  const limit = Math.min(50, Math.max(1, Number(url.searchParams.get("limit") ?? 20) || 20));
  const near = point(url);
  const matches = body.data
    .filter((line) => q !== "" && line.shortName.toLocaleLowerCase().startsWith(q))
    .map((line) => withNearest(line, near))
    .sort((a, b) => {
      const exact = Number(b.shortName.toLocaleLowerCase() === q) - Number(a.shortName.toLocaleLowerCase() === q);
      if (exact) return exact;
      const da = a.nearestStop?.distanceM ?? Number.POSITIVE_INFINITY;
      const db = b.nearestStop?.distanceM ?? Number.POSITIVE_INFINITY;
      if (da !== db) return da - db;
      return numeric(a.shortName) - numeric(b.shortName) || a.shortName.localeCompare(b.shortName);
    });
  body.data = matches.slice(0, limit);
  body.page = { nextCursor: null };
  return {
    ...base,
    request: { ...base.request, params: Object.fromEntries(url.searchParams) },
    body,
  };
}

/** GET /v1/lines/{lineKey}: the catalogue's line, or 404 like any absent resource. */
export function derivedLine(lineKey: string, url: URL): Fixture {
  const line = (catalogue().body as LinesBody).data.find((item) => item.lineKey === lineKey);
  if (!line) {
    const missing = fixture("synthetic-problem-stop-not-found");
    return { ...missing, request: { ...missing.request, path: `/v1/lines/${encodeURIComponent(lineKey)}` } };
  }
  const base = fixture("synthetic-line");
  const body = structuredClone(base.body) as { data: LineItem };
  body.data = withNearest(structuredClone(line), point(url));
  return { ...base, request: { ...base.request, path: `/v1/lines/${encodeURIComponent(lineKey)}` }, body };
}
