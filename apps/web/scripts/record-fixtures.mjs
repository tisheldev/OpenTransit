#!/usr/bin/env node
// Record `recorded-live-*` fixtures from a running API and check trip-ref encoding
// against real engine trip IDs. Refuses to record unless /readyz is 200.
//
//   OPENTRANSIT_API_ORIGIN=http://localhost:8000 npm run fixtures:record
//
// Writes sanitised fixtures plus manifest entries (generation, time, origin class).
// The Sept 30 `recorded-*` fixtures are kept: new recordings get their own names so
// historical comparisons stay attributable.

import { readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { sanitise, stableJson } from "./sanitise.mjs";

const origin = process.env.OPENTRANSIT_API_ORIGIN ?? "http://localhost:8000";
const out = join(dirname(fileURLToPath(import.meta.url)), "..", "src", "api", "fixtures");
const DIZENGOFF_CENTER = "mot:stop:13583";
const TECHNION = { kind: "coordinate", latitude: 32.7767, longitude: 35.0231 };

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

/** Next 08:00 in Israel, with its explicit offset, at least an hour away. */
function nextMorning() {
  const zone = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Jerusalem", year: "numeric", month: "2-digit", day: "2-digit", timeZoneName: "longOffset",
  });
  const tomorrow = new Date(Date.now() + 24 * 3600_000);
  const parts = Object.fromEntries(zone.formatToParts(tomorrow).map((p) => [p.type, p.value]));
  const offset = parts.timeZoneName.replace("GMT", "") || "+00:00";
  return `${parts.year}-${parts.month}-${parts.day}T08:00:00${offset}`;
}

const ready = await call("GET", "/readyz").catch((error) => ({ status: 0, body: String(error) }));
if (ready.status !== 200) {
  console.error(`API at ${origin} is not ready (/readyz ${ready.status}); nothing recorded. Real-API checks remain pending.`);
  process.exit(2);
}

const recorded = {};
async function record(name, method, path, options = {}) {
  const result = await call(method, path, options);
  const fixture = {
    request: { method, path, params: options.params ?? null, body: options.body ?? null },
    status: result.status,
    ...(Object.keys(result.headers).length ? { headers: result.headers } : {}),
    body: sanitise(result.body),
  };
  writeFileSync(join(out, `recorded-live-${name}.json`), stableJson(fixture));
  recorded[`recorded-live-${name}`] = result;
  return result;
}

await record("status", "GET", "/v1/status");
await record("places-stop-he", "GET", "/v1/places", { params: { q: "דיזנגוף סנטר", limit: 5 } });
await record("places-stop-en", "GET", "/v1/places", { params: { q: "Dizengoff Center", lang: "en", type: "stop" } });
await record("places-poi-en", "GET", "/v1/places", { params: { q: "Dizengoff", lang: "en", type: "poi" } });
await record("places-address-he", "GET", "/v1/places", { params: { q: "דיזנגוף 50 תל אביב", type: "address" } });
await record("places-empty", "GET", "/v1/places", { params: { q: "zzzznotarealstop", lang: "en", type: "stop" } });
const departAt = nextMorning();
const journey = await record("journey-routes", "POST", "/v1/journeys", {
  body: { from: { kind: "stop", stopId: DIZENGOFF_CENTER }, to: TECHNION, departAt, results: 3 },
});
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
  await record("route", "GET", `/v1/routes/${routeId}`);
  await record("route-patterns", "GET", `/v1/routes/${routeId}/patterns`, { params: { limit: 2 } });
}
await record("problem-trip-not-found", "GET", "/v1/trips/20261001_08:00_mot60day_missing");
await record("problem-outside-window", "POST", "/v1/journeys", {
  body: { from: { kind: "stop", stopId: DIZENGOFF_CENTER }, to: TECHNION, departAt: "2030-01-01T08:00:00+02:00" },
});

// Trip-ref encoding against real IDs: the encoded path the client sends must return
// the same trip as the raw ID, and no real ID may contain "/".
const tripIds = [
  ...new Set(
    (journey.body?.data?.journeys ?? []).flatMap((item) =>
      item.legs.flatMap((leg) => (leg.transit ? [leg.transit.engineTripId] : [])),
    ),
  ),
];
const checks = [];
for (const [index, id] of tripIds.entries()) {
  const encoded = await call("GET", `/v1/trips/${encodeURIComponent(id)}`);
  if (index === 0) {
    writeFileSync(
      join(out, "recorded-live-trip.json"),
      stableJson({ request: { method: "GET", path: `/v1/trips/${id}`, params: null, body: null }, status: encoded.status, body: sanitise(encoded.body) }),
    );
    recorded["recorded-live-trip"] = encoded;
  }
  checks.push({
    id,
    containsSlash: id.includes("/"),
    encodedStatus: encoded.status,
    sameTrip: encoded.body?.data?.tripRef === id,
  });
}

const manifestPath = join(out, "manifest.json");
const manifest = JSON.parse(readFileSync(manifestPath, "utf8"));
const generationId = recorded["recorded-live-status"].body?.meta?.generationId ?? null;
const recordedAt = new Date().toISOString();
for (const name of Object.keys(recorded)) {
  manifest[name] = {
    provenance: "recorded",
    source: "live API via apps/web/scripts/record-fixtures.mjs",
    sourceSha256: generationId && /^[0-9a-f]{64}$/.test(generationId) ? generationId : "0".repeat(64),
    generationId,
    recordedAt,
  };
}
writeFileSync(manifestPath, stableJson(Object.fromEntries(Object.entries(manifest).sort(([a], [b]) => a.localeCompare(b)))));

const failed = checks.filter((check) => check.containsSlash || check.encodedStatus !== 200 || !check.sameTrip);
console.log(JSON.stringify({ origin, generationId, recordedAt, fixtures: Object.keys(recorded).length, tripRefChecks: checks }, null, 2));
if (!tripIds.length || failed.length) {
  console.error(tripIds.length ? `${failed.length} trip-ref checks failed` : "journey returned no transit legs to check");
  process.exit(1);
}
