import { delay, http, HttpResponse } from "msw";
import { fixture, fixtures, type Fixture } from "../api/fixtures";
import { derivedEngineTimeout, derivedJourneyFixtures, derivedTrip } from "../screens/compare/derivedFixtures";

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

// DERIVED answers (not recorded): built at runtime from a recorded fixture to show a
// state the recorded evidence lacks. Each says what it changed; none is presented as a
// real API response. (Kept in code: schemas.test.ts accepts only recorded-/synthetic-
// fixture files.)

/** Derived from recorded-places-stop-he: addresses marked unavailable, partial answer. */
export function derivedPartialPlaces(): Fixture {
  const base = fixture("recorded-places-stop-he");
  const body = structuredClone(base.body) as {
    data: Array<{ kind: string }>;
    matchedTypes: string[];
    unavailableTypes: string[];
    partial: boolean;
  };
  body.data = body.data.filter((item) => item.kind !== "address");
  body.matchedTypes = body.matchedTypes.filter((type) => type !== "address");
  body.unavailableTypes = ["address"];
  body.partial = true;
  return { ...base, body };
}

/** Derived from recorded-places-address-he: the first address resolved to street level only. */
export function derivedStreetLevelAddress(): Fixture {
  const base = fixture("recorded-places-address-he");
  const body = structuredClone(base.body) as { data: Array<Record<string, unknown>> };
  body.data = body.data.slice(0, 1).map((item) => ({
    ...item,
    name: "דיזנגוף",
    displayName: "דיזנגוף",
    houseNumber: null,
    addressLevel: "street",
  }));
  return { ...base, body };
}

/** Derived from synthetic-problem-feed-expired: every search category unavailable (503). */
export function derivedCategoryUnavailable(): Fixture {
  const base = fixture("synthetic-problem-feed-expired");
  return {
    ...base,
    request: { ...base.request, path: "/v1/places" },
    status: 503,
    body: {
      ...(base.body as Record<string, unknown>),
      type: "urn:opentransit:problem:category-unavailable",
      title: "Category unavailable",
      status: 503,
      code: "CATEGORY_UNAVAILABLE",
      detail: "No requested place category is available.",
    },
  };
}

/** Fixtures holding a trip, keyed by trip ref. */
const tripsByRef = new Map(
  Object.entries(fixtures)
    .filter(([name]) => name.startsWith("recorded-trip-"))
    .map(([, found]) => [(found.body as { data: { tripRef: string } }).data.tripRef, found]),
);

// --- journeys (slice S5): one scenario per Compare state -----------------------

/** Journey requests answered so far in this page (the "...-once" scenarios fail first). */
let journeyCalls = 0;

function journeyAnswer(): HttpResponse<string> {
  journeyCalls += 1;
  const three = () => respond(derivedJourneyFixtures["derived-journey-three"]());
  switch (scenario()) {
    case "compare-one":
      return send("recorded-journey-routes");
    case "compare-two":
      return respond(derivedJourneyFixtures["derived-journey-two"]());
    case "compare-no-route":
      return respond(derivedJourneyFixtures["derived-journey-no-route"]());
    case "compare-walk-only":
      return respond(derivedJourneyFixtures["derived-journey-walk-only"]());
    case "compare-outside-window":
      return send("recorded-problem-outside-window");
    case "compare-unavailable":
      return send("recorded-problem-not-ready");
    case "compare-unavailable-once":
      return journeyCalls === 1 ? send("recorded-problem-not-ready") : three();
    case "compare-timeout":
      return respond(derivedEngineTimeout());
    case "compare-rate-limited":
      return send("synthetic-problem-rate-limited");
    case "compare-offline":
      return HttpResponse.error() as unknown as HttpResponse<string>;
    default:
      return three();
  }
}

export const handlers = [
  http.get("*/v1/status", () => {
    switch (scenario()) {
      case "status-expired":
        return send("synthetic-status-expired");
      case "status-offline":
        return HttpResponse.error();
      case "status-not-ready":
        return send("recorded-problem-not-ready");
      default:
        return send("synthetic-status-ready");
    }
  }),

  http.get("*/v1/places", async ({ request }) => {
    const url = new URL(request.url);
    const q = url.searchParams.get("q") ?? "";
    const lang = url.searchParams.get("lang") ?? "he";
    const types = url.searchParams.getAll("type");
    if (q.trim().length < 2) return send("synthetic-problem-invalid-request");
    switch (scenario()) {
      case "places-partial":
        return respond(derivedPartialPlaces());
      case "places-unavailable":
        return respond(derivedCategoryUnavailable());
      case "places-rate-limited":
        return send("synthetic-problem-rate-limited");
      case "places-offline":
        return HttpResponse.error();
      case "places-slow":
        await delay(4000);
        break;
    }
    if (q.startsWith("street")) return respond(derivedStreetLevelAddress());
    if (q.startsWith("zzz")) return send("recorded-places-empty");
    if (types.length === 1 && types[0] === "address") return send("recorded-places-address-he");
    if (lang === "en") return send(types.includes("poi") ? "recorded-places-poi-en" : "recorded-places-stop-en");
    return send("recorded-places-stop-he");
  }),

  http.post("*/v1/journeys", () => journeyAnswer()),

  http.get("*/v1/trips/:tripRef", ({ params }) => {
    if (scenario() === "compare-trip-failed") return send("recorded-problem-not-ready");
    const ref = decoded(params.tripRef);
    const found = tripsByRef.get(ref) ?? derivedTrip(ref);
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
