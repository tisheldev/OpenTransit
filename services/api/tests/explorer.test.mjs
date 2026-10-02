import test from "node:test";
import assert from "node:assert/strict";
import {
  buildJourneyRequest, buildQuery, describeRequest, idKind, latestOnly, metaFacts, pillState, sameOriginTarget,
} from "../src/opentransit/api/playground/explorer-request.mjs";
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

test("raw requests stay on this origin, including protocol-relative and backslash tricks", () => {
  const origin = "http://127.0.0.1:8000";
  assert.equal(sameOriginTarget("/v1/places?q=a", origin), "/v1/places?q=a");
  assert.equal(sameOriginTarget("http://127.0.0.1:8000/v1/status#x", origin), "/v1/status");
  for (const path of ["//example.com/x", "/\\example.com/x", "https://example.com/v1/status", "javascript:alert(1)"]) {
    assert.throws(() => sameOriginTarget(path, origin), /this API only/, path);
  }
});

test("the shown request is the encoded path that was sent, with a decoded line only when it differs", () => {
  assert.deepEqual(describeRequest("GET", "/v1/status"), { exact: "GET /v1/status", decoded: null });
  assert.deepEqual(describeRequest("GET", "/v1/places?q=%D7%90%D7%91"), { exact: "GET /v1/places?q=%D7%90%D7%91", decoded: "/v1/places?q=אב" });
  assert.deepEqual(describeRequest("GET", "/v1/x?q=%E0%A4%A"), { exact: "GET /v1/x?q=%E0%A4%A", decoded: null });
});

test("only the latest request may render; superseded responses are ignored", () => {
  const begin = latestOnly();
  const first = begin();
  assert.equal(first(), true);
  const second = begin();
  assert.equal(first(), false);
  assert.equal(second(), true);
});

const realMeta = { requestId: "r1", generationId: "abc", mode: "real", freshness: "current" };

test("meta labels flag synthetic fixture data and skip fields the response lacks", () => {
  assert.equal(metaFacts(undefined), null);
  assert.deepEqual(metaFacts(realMeta), { synthetic: false, caution: false, parts: ["freshness current", "mode real"] });
  assert.deepEqual(metaFacts({ ...realMeta, mode: "fixture", freshness: "aging" }),
    { synthetic: true, caution: true, parts: ["freshness aging", "mode fixture"] });
  assert.deepEqual(metaFacts({ requestId: "r2", generatedAt: "2026-10-02T06:00:00Z", generationId: null }),
    { synthetic: false, caution: true, parts: ["no generation loaded"] });
});

test("status pill is green only for ready, current, real data", () => {
  const ready = { ready: true, staticData: "available", routing: "available" };
  assert.deepEqual(pillState(200, { data: ready, meta: realMeta }), { tone: "ok", text: "Ready · current · real" });
  assert.deepEqual(pillState(200, { data: ready, meta: { ...realMeta, freshness: "aging", mode: "fixture" } }),
    { tone: "warn", text: "Ready · aging · SYNTHETIC fixture" });
  assert.deepEqual(pillState(200, { data: ready, meta: { ...realMeta, freshness: "stale" } }), { tone: "warn", text: "Ready · stale · real" });
  assert.deepEqual(pillState(200, { data: { ready: false, staticData: "unavailable", routing: "unavailable" }, meta: { generationId: null } }),
    { tone: "bad", text: "Not ready · data unavailable · routing unavailable" });
  assert.deepEqual(pillState(500, { code: "INTERNAL" }), { tone: "bad", text: "API error (HTTP 500)" });
});
