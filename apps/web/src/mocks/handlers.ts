import { http, HttpResponse } from "msw";
import { fixture, fixtures, type Fixture } from "../api/fixtures";

// MSW handlers that answer every public endpoint from fixtures. Used by Vitest (node)
// and by the dev server's `fixtures` mode (browser), so mocked e2e needs no API.

export function respond(found: Fixture, extraHeaders: Record<string, string> = {}): HttpResponse<string> {
  const headers = new Headers({
    "Content-Type": found.status >= 400 ? "application/problem+json" : "application/json",
    "Cache-Control": "no-store",
    ...found.headers,
  });
  for (const [key, value] of Object.entries(extraHeaders)) headers.set(key, value);
  return new HttpResponse(JSON.stringify(found.body), { status: found.status, headers });
}

const send = (name: string) => respond(fixture(name));

/**
 * The fixture scenario chosen by a mocked e2e test (e2e/helpers.ts useScenario) or by a
 * person trying fixture mode: localStorage "ot-fixture-scenario". Null means the default.
 * Unit tests use server.use() overrides instead.
 */
export function scenario(): string | null {
  try {
    return globalThis.localStorage?.getItem("ot-fixture-scenario") ?? null;
  } catch {
    return null;
  }
}
const decoded = (value: string | readonly string[] | undefined) => decodeURIComponent(String(value ?? ""));

/** Fixtures holding a trip, keyed by trip ref. */
const tripsByRef = new Map(
  Object.entries(fixtures)
    .filter(([name]) => name.startsWith("recorded-trip-"))
    .map(([, found]) => [(found.body as { data: { tripRef: string } }).data.tripRef, found]),
);

export const handlers = [
  http.get("*/v1/status", () => send("synthetic-status-ready")),

  http.get("*/v1/places", ({ request }) => {
    const url = new URL(request.url);
    const q = url.searchParams.get("q") ?? "";
    const lang = url.searchParams.get("lang") ?? "he";
    const types = url.searchParams.getAll("type");
    if (q.trim().length < 2) return send("synthetic-problem-invalid-request");
    if (q.startsWith("zzz")) return send("recorded-places-empty");
    if (types.length === 1 && types[0] === "address") return send("recorded-places-address-he");
    if (lang === "en") return send(types.includes("poi") ? "recorded-places-poi-en" : "recorded-places-stop-en");
    return send("recorded-places-stop-he");
  }),

  http.post("*/v1/journeys", () => send("recorded-journey-routes")),

  http.get("*/v1/trips/:tripRef", ({ params }) => {
    const found = tripsByRef.get(decoded(params.tripRef));
    return found ? respond(found) : send("recorded-problem-trip-not-found");
  }),

  http.get("*/v1/stops/:stopId/departures", ({ request }) => {
    const cursor = new URL(request.url).searchParams.get("cursor");
    return send(cursor ? "recorded-departures-page-2" : "recorded-departures-page-1");
  }),

  http.get("*/v1/stops/:stopId", ({ params }) => {
    const stopId = decoded(params.stopId);
    if (stopId === "mot:stop:13583") return send("recorded-stop");
    if (stopId === "mot:stop:station") return send("synthetic-stop-station");
    return send("synthetic-problem-stop-not-found");
  }),

  http.get("*/v1/stops", ({ request }) => {
    const url = new URL(request.url);
    if (url.searchParams.has("bbox")) return send("synthetic-stops-bbox");
    return send(url.searchParams.has("cursor") ? "synthetic-stops-near-page-2" : "synthetic-stops-near-page-1");
  }),

  http.get("*/v1/routes/:routeId/patterns", () => send("synthetic-route-patterns")),
  http.get("*/v1/routes/:routeId", () => send("synthetic-route")),
  http.get("*/v1/routes", () => send("synthetic-routes")),
];
