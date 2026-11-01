#!/usr/bin/env node
// Record `recorded-live-*` fixtures from a running API and run the S1 real-API checks
// (trip-ref encoding on real engine trip IDs, placeRef vs coordinate planning).
// Refuses to record unless /readyz is 200.
//
//   OPENTRANSIT_API_ORIGIN=http://localhost:8000 npm run fixtures:record
//
// Optional: OT_RECORD_DEPART_AT (ISO with offset; default the next Sun-Thu 08:00 in
// Israel at least a day away) and OT_RECORD_REPORT (path for the raw check results as
// JSON; keep it outside the repository).
//
// Writes sanitised fixtures plus manifest entries (generation, time, origin class, case).
// Only corpus journeys are recorded (Dizengoff Center stop, the Technion corpus point,
// public places found by search); no device or personal coordinates are sent.
// The Sept 30 `recorded-*` fixtures are kept: new recordings get their own names so
// historical comparisons stay attributable.

import { readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import ts from "typescript";
import { sanitise, stableJson } from "./sanitise.mjs";

const origin = process.env.OPENTRANSIT_API_ORIGIN ?? "http://localhost:8000";
const web = join(dirname(fileURLToPath(import.meta.url)), "..");
const out = join(web, "src", "api", "fixtures");
const DIZENGOFF_CENTER = "mot:stop:13583";
const FROM_STOP = { kind: "stop", stopId: DIZENGOFF_CENTER };
const TECHNION = { kind: "coordinate", latitude: 32.7767, longitude: 35.0231 };

/** The client's own encodePathRef (src/api/pathRef.ts), transpiled, so the check uses it. */
async function loadPathRef() {
  const source = readFileSync(join(web, "src", "api", "pathRef.ts"), "utf8");
  const { outputText } = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
  });
  return import(`data:text/javascript;base64,${Buffer.from(outputText).toString("base64")}`);
}
const { encodePathRef } = await loadPathRef();

/** loopback | private | public: recorded instead of the origin itself. */
function originClass(value) {
  const host = new URL(value).hostname.replace(/^\[|\]$/g, "");
  if (host === "localhost" || host === "::1" || /^127\./.test(host)) return "loopback";
  if (/^(10\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.)/.test(host) || host.endsWith(".local")) return "private";
  return "public";
}

async function call(method, path, { params, body } = {}) {
  const url = new URL(path, origin);
  for (const [key, value] of Object.entries(params ?? {})) {
    for (const item of [value].flat()) url.searchParams.append(key, String(item));
  }
  const response = await fetch(url, {
    method,
    headers: body ? { "Content-Type": "application/json" } : {},
    body: body ? JSON.stringify(body) : undefined,
  });
  const headers = {};
  const retryAfter = response.headers.get("retry-after");
  if (retryAfter) headers["retry-after"] = retryAfter;
  return { status: response.status, headers, body: await response.json() };
}

/** Next Sunday-Thursday 08:00 in Israel, with its explicit offset, at least a day away. */
function nextWeekdayMorning() {
  const zone = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Jerusalem", year: "numeric", month: "2-digit", day: "2-digit", weekday: "short",
    timeZoneName: "longOffset",
  });
  for (let days = 1; days < 8; days += 1) {
    const day = new Date(Date.now() + days * 24 * 3600_000);
    const parts = Object.fromEntries(zone.formatToParts(day).map((p) => [p.type, p.value]));
    if (parts.weekday === "Fri" || parts.weekday === "Sat") continue;
    const offset = parts.timeZoneName.replace("GMT", "") || "+00:00";
    return `${parts.year}-${parts.month}-${parts.day}T08:00:00${offset}`;
  }
  throw new Error("no weekday found");
}

const ready = await call("GET", "/readyz").catch((error) => ({ status: 0, body: String(error) }));
if (ready.status !== 200) {
  console.error(`API at ${origin} is not ready (/readyz ${ready.status}); nothing recorded. Real-API checks remain pending.`);
  process.exit(2);
}

const recorded = {};
const cases = {};
async function record(name, method, path, options = {}, label = name) {
  const result = await call(method, path, options);
  const fixture = {
    request: { method, path, params: options.params ?? null, body: options.body ?? null },
    status: result.status,
    ...(Object.keys(result.headers).length ? { headers: result.headers } : {}),
    body: sanitise(result.body),
  };
  writeFileSync(join(out, `recorded-live-${name}.json`), stableJson(fixture));
  recorded[`recorded-live-${name}`] = result;
  cases[`recorded-live-${name}`] = label;
  return result;
}

const legsOf = (response) => (response.body?.data?.journeys ?? []).flatMap((item) => item.legs);
const transitIds = (response) => legsOf(response).flatMap((leg) => (leg.transit ? [leg.transit.engineTripId] : []));

await record("status", "GET", "/v1/status");
await record("places-stop-he", "GET", "/v1/places", { params: { q: "דיזנגוף סנטר", limit: 5 } }, "stop search, Hebrew");
await record("places-stop-en", "GET", "/v1/places", { params: { q: "Dizengoff Center", lang: "en", type: "stop" } }, "stop search, English");
await record("places-poi-en", "GET", "/v1/places", { params: { q: "Technion", lang: "en", type: "poi" } }, "POI search, English");
await record("places-poi-he", "GET", "/v1/places", { params: { q: "עזריאלי", type: "poi" } }, "POI search, Hebrew");
await record("places-address-he", "GET", "/v1/places", { params: { q: "דיזנגוף 50 תל אביב", type: "address" } }, "address search, Hebrew");
await record("places-mixed-en", "GET", "/v1/places", { params: { q: "Technion", lang: "en" } }, "all categories, English");
await record("places-empty", "GET", "/v1/places", { params: { q: "zzzznotarealstop", lang: "en", type: "stop" } }, "valid empty search");
const departAt = process.env.OT_RECORD_DEPART_AT ?? nextWeekdayMorning();
const journey = await record("journey-routes", "POST", "/v1/journeys", {
  body: { from: FROM_STOP, to: TECHNION, departAt, results: 3 },
}, "routes found: Dizengoff Center -> Technion, weekday 08:00 (rail with transfers)");
const noRoute = await record("journey-no-route", "POST", "/v1/journeys", {
  body: { from: FROM_STOP, to: TECHNION, departAt, modes: ["light_rail"] },
}, "no route: Dizengoff Center -> Technion by light rail only");
await record("stop", "GET", `/v1/stops/${DIZENGOFF_CENTER}`);
const first = await record("departures-page-1", "GET", `/v1/stops/${DIZENGOFF_CENTER}/departures`, {
  params: { from: departAt, horizonMinutes: 60, limit: 2 },
});
if (first.body?.page?.nextCursor) {
  await record("departures-page-2", "GET", `/v1/stops/${DIZENGOFF_CENTER}/departures`, {
    params: { from: departAt, horizonMinutes: 60, limit: 2, cursor: first.body.page.nextCursor },
  });
}
await record("stops-near", "GET", "/v1/stops", { params: { near: "32.0757,34.7748", radius: 300, limit: 5 } });
const routes = await record("routes", "GET", "/v1/routes", { params: { stopId: DIZENGOFF_CENTER, limit: 5 } });
const routeId = routes.body?.data?.[0]?.routeId;
if (routeId) {
  await record("route", "GET", `/v1/routes/${encodePathRef(routeId).segment}`);
  await record("route-patterns", "GET", `/v1/routes/${encodePathRef(routeId).segment}/patterns`, { params: { limit: 2 } });
}
await record("problem-trip-not-found", "GET", "/v1/trips/20261001_08:00_mot60day_missing");
await record("problem-outside-window", "POST", "/v1/journeys", {
  body: { from: FROM_STOP, to: TECHNION, departAt: "2030-01-01T08:00:00+02:00" },
}, "OUTSIDE_SERVICE_WINDOW");

// Shapes the client must handle, found in the routes answer.
const walks = legsOf(journey).filter((leg) => leg.mode === "walk");
const timeOnlyWalk = walks.find((leg) => leg.distanceMeters === null && leg.geometry === null) ?? null;
const railLeg = legsOf(journey).find((leg) => leg.mode === "rail") ?? null;
const railJourney = (journey.body?.data?.journeys ?? []).find((item) => item.legs.some((leg) => leg.mode === "rail"));
const shapes = {
  routesFound: journey.body?.data?.outcome === "routes_found",
  journeys: journey.body?.data?.journeys?.length ?? 0,
  warnings: journey.body?.meta?.warnings ?? [],
  timeOnlyWalk: timeOnlyWalk && {
    distanceMeters: timeOnlyWalk.distanceMeters,
    geometry: timeOnlyWalk.geometry,
    geometryUnavailableReason: timeOnlyWalk.geometryUnavailableReason ?? null,
    durationSeconds: timeOnlyWalk.durationSeconds,
  },
  railWithTransfer: railJourney
    ? { transfers: railJourney.transfers ?? null, legs: railJourney.legs.map((leg) => leg.mode) }
    : null,
  railLeg: railLeg && { routeShortName: railLeg.transit.routeShortName, headsign: railLeg.transit.headsign },
  noRoute: noRoute.body?.data?.outcome === "no_route" && (noRoute.body?.data?.journeys?.length ?? -1) === 0,
};

// placeRef vs coordinate: plan the same journey with a searched place's placeRef and
// with the coordinate the search returned for it. The design keeps the client's
// INVALID_PLACE_REF retry only if the two differ.
function itinerary(response) {
  return (response.body?.data?.journeys ?? []).map((item) =>
    item.legs.map((leg) => [
      leg.mode,
      leg.transit?.engineTripId ?? null,
      leg.timing?.scheduledDeparture,
      leg.timing?.scheduledArrival,
      leg.distanceMeters,
    ]),
  );
}
/** Body without per-request fields and endpoint names (the engine names coordinates START/END). */
function comparable(response) {
  const copy = structuredClone(response.body);
  if (copy?.meta) {
    delete copy.meta.requestId;
    delete copy.meta.generatedAt;
  }
  for (const item of copy?.data?.journeys ?? []) {
    const legs = item.legs;
    if (legs.length) {
      delete legs[0].from.name;
      delete legs[legs.length - 1].to.name;
    }
  }
  return JSON.stringify(copy);
}
const placeQueries = [
  { q: "דיזנגוף 50 תל אביב", type: "address" },
  { q: "Technion", lang: "en", type: "poi" },
  { q: "עזריאלי", type: "poi" },
  { q: "Haifa University", lang: "en", type: "poi" },
];
const placeRefComparison = [];
const plannedTripIds = [];
for (const query of placeQueries) {
  const found = await call("GET", "/v1/places", { params: { ...query, limit: 1 } });
  const place = found.body?.data?.[0];
  if (!place?.placeRef || !place.coordinates) {
    placeRefComparison.push({ query, found: false });
    continue;
  }
  const coordinate = { kind: "coordinate", ...place.coordinates };
  const byRef = { kind: "place", placeRef: place.placeRef };
  for (const direction of ["to", "from"]) {
    const ends = (end) => (direction === "to" ? { from: FROM_STOP, to: end } : { from: end, to: TECHNION });
    const viaRef = await call("POST", "/v1/journeys", { body: { ...ends(byRef), departAt, results: 3 } });
    const viaCoordinate = await call("POST", "/v1/journeys", { body: { ...ends(coordinate), departAt, results: 3 } });
    plannedTripIds.push(...transitIds(viaRef), ...transitIds(viaCoordinate));
    const a = itinerary(viaRef);
    const b = itinerary(viaCoordinate);
    placeRefComparison.push({
      query,
      kind: place.kind,
      name: place.name,
      direction,
      statusRef: viaRef.status,
      statusCoordinate: viaCoordinate.status,
      journeysRef: a.length,
      journeysCoordinate: b.length,
      itinerariesIdentical: JSON.stringify(a) === JSON.stringify(b),
      bodiesIdenticalExceptEndpointNames: comparable(viaRef) === comparable(viaCoordinate),
      endpointNameRef: direction === "to" ? viaRef.body?.data?.journeys?.[0]?.legs.at(-1)?.to?.name : viaRef.body?.data?.journeys?.[0]?.legs[0]?.from?.name,
      endpointNameCoordinate: direction === "to" ? viaCoordinate.body?.data?.journeys?.[0]?.legs.at(-1)?.to?.name : viaCoordinate.body?.data?.journeys?.[0]?.legs[0]?.from?.name,
      warningsRef: viaRef.body?.meta?.warnings ?? null,
      warningsCoordinate: viaCoordinate.body?.meta?.warnings ?? null,
    });
  }
}

// Trip-ref encoding against every real trip ID planned above (the routes fixture and the
// placeRef comparisons), through the client's encodePathRef: the encoded path must
// return the same trip as the raw ID, and no real ID may contain "/".
const tripIds = [...new Set([...transitIds(journey), ...plannedTripIds])];
const tripRefChecks = [];
for (const id of tripIds) {
  const encoded = encodePathRef(id);
  const response = encoded.ok ? await call("GET", `/v1/trips/${encoded.segment}`) : null;
  tripRefChecks.push({
    id,
    containsColon: id.includes(":"),
    containsSlash: id.includes("/"),
    encodeOk: encoded.ok,
    segment: encoded.ok ? encoded.segment : encoded.reason,
    status: response?.status ?? null,
    sameTrip: response?.body?.data?.tripRef === id,
  });
}
const tripFixture = async (name, id, label) => {
  if (!id) return;
  const segment = encodePathRef(id).segment;
  await record(name, "GET", `/v1/trips/${segment}`, {}, label);
};
await tripFixture("trip", tripIds[0], "trip detail of a real engine trip ID containing ':'");
await tripFixture("trip-rail", railLeg?.transit?.engineTripId, "rail trip detail");

const manifestPath = join(out, "manifest.json");
const manifest = JSON.parse(readFileSync(manifestPath, "utf8"));
const generationId = recorded["recorded-live-status"].body?.meta?.generationId ?? null;
const recordedAt = new Date().toISOString();
for (const name of Object.keys(recorded)) {
  manifest[name] = {
    provenance: "recorded",
    source: "live API via apps/web/scripts/record-fixtures.mjs",
    sourceSha256: generationId && /^[0-9a-f]{64}$/.test(generationId) ? generationId : "0".repeat(64),
    case: cases[name],
    generationId,
    originClass: originClass(origin),
    departAt,
    recordedAt,
  };
}
writeFileSync(manifestPath, stableJson(Object.fromEntries(Object.entries(manifest).sort(([a], [b]) => a.localeCompare(b)))));

const partialFixtures = Object.keys(recorded).filter((name) => recorded[name].body?.partial === true);
const failed = tripRefChecks.filter((check) => check.containsSlash || check.status !== 200 || !check.sameTrip);
const report = {
  originClass: originClass(origin),
  generationId,
  coverage: recorded["recorded-live-status"].body?.meta?.coverage ?? null,
  recordedAt,
  departAt,
  fixtures: Object.keys(recorded).sort(),
  shapes,
  partialSearch: partialFixtures.length
    ? { obtained: true, fixtures: partialFixtures }
    : { obtained: false, reason: "every requested category was available; no search reported partial: true" },
  tripRef: {
    checked: tripRefChecks.length,
    withColon: tripRefChecks.filter((check) => check.containsColon).length,
    withSlash: tripRefChecks.filter((check) => check.containsSlash).length,
    failed: failed.length,
    checks: tripRefChecks,
  },
  placeRefComparison,
};
if (process.env.OT_RECORD_REPORT) writeFileSync(process.env.OT_RECORD_REPORT, stableJson(report));
console.log(JSON.stringify({ ...report, tripRef: { ...report.tripRef, checks: undefined } }, null, 2));
if (!tripIds.length || failed.length) {
  console.error(tripIds.length ? `${failed.length} trip-ref checks failed` : "journey returned no transit legs to check");
  process.exit(1);
}
