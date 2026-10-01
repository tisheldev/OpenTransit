import test from "node:test";
import assert from "node:assert/strict";
import { buildJourneyRequest, buildQuery, idKind } from "../src/opentransit/api/playground/explorer-request.mjs";
import { departureInstant } from "../src/opentransit/api/playground/time.mjs";

test("identifiers open the endpoint that owns them", () => {
  assert.equal(idKind("mot:stop:12345"), "stop");
  assert.equal(idKind("mot:route:7"), "route");
  assert.equal(idKind("20261002_08:00_mot60day_123_021026"), "trip");
  assert.equal(idKind("20261002_08:00:30_mot60day_9"), "trip");
  assert.equal(idKind("mot60day_123"), null);
  assert.equal(idKind(undefined), null);
});

test("query strings omit blanks so server defaults apply, and repeat array keys", () => {
  assert.equal(buildQuery({ q: " Savidor ", lang: "en", near: "", limit: undefined, type: ["stop", "station"] }),
    "q=Savidor&lang=en&type=stop&type=station");
  assert.equal(buildQuery({ cursor: null }), "");
});

const base = {
  fromKind: "coordinate", fromLat: "32.0757", fromLon: "34.7748",
  toKind: "stop", toStop: "mot:stop:1",
  anchor: "departAt", time: "2026-10-05T08:00", offset: "auto",
  modes: ["bus", "rail", "light_rail"], results: "", lang: "",
  maxAccessWalkMinutes: "", maxEgressWalkMinutes: "", maxDirectWalkMinutes: "",
};

test("journey body uses the declared location kinds and omits blank optionals", () => {
  assert.deepEqual(buildJourneyRequest(base, departureInstant), {
    from: { kind: "coordinate", latitude: 32.0757, longitude: 34.7748 },
    to: { kind: "stop", stopId: "mot:stop:1" },
    departAt: "2026-10-05T08:00:00+03:00",
    modes: ["bus", "rail", "light_rail"],
  });
});

test("arrive-by, place references and every option are passed through as numbers", () => {
  const body = buildJourneyRequest({
    ...base, fromKind: "place", fromPlace: "opaque-ref", anchor: "arriveBy", time: "2026-10-30T09:15",
    modes: ["rail"], results: "5", lang: "en", maxAccessWalkMinutes: "5", maxEgressWalkMinutes: "6", maxDirectWalkMinutes: "7",
  }, departureInstant);
  assert.deepEqual(body, {
    from: { kind: "place", placeRef: "opaque-ref" },
    to: { kind: "stop", stopId: "mot:stop:1" },
    arriveBy: "2026-10-30T09:15:00+02:00",
    modes: ["rail"], results: 5, maxAccessWalkMinutes: 5, maxEgressWalkMinutes: 6, maxDirectWalkMinutes: 7, lang: "en",
  });
  assert.equal("departAt" in body, false);
});

test("out-of-range values reach the API unchanged so its validation can be inspected", () => {
  const body = buildJourneyRequest({ ...base, modes: [], results: "9" }, departureInstant);
  assert.deepEqual(body.modes, []);
  assert.equal(body.results, 9);
});
