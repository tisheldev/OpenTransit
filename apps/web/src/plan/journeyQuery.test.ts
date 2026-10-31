import { describe, expect, it, vi } from "vitest";
import { setLocationSource, type LocationSource } from "../lib/geolocation";
import type { PlaceChoice, PlanDraft } from "./draft";
import { buildJourneyRequest, resolveJourneyRequest, type BuildContext } from "./journeyQuery";

const place = (over: Partial<PlaceChoice>): PlaceChoice => ({
  label: "מקום",
  locality: null,
  kind: "address",
  latitude: 32.1,
  longitude: 34.8,
  stopId: null,
  placeRef: null,
  refGenerationId: null,
  ...over,
});

const stop = place({ label: "דיזנגוף סנטר", kind: "stop", stopId: "mot:stop:13583", latitude: 32.075, longitude: 34.775 });
const technion = place({ label: "טכניון", kind: "pin", latitude: 32.7767, longitude: 35.0231 });
const searched = place({ label: "אלנבי 30", placeRef: "mot:place:v1:abc", refGenerationId: "gen-a", latitude: 32.07, longitude: 34.77 });

const ctx = (over: Partial<BuildContext> = {}): BuildContext => ({
  myLocation: null,
  now: new Date("2026-11-02T06:00:00Z"),
  lang: "he",
  generationId: "gen-a",
  ...over,
});

const draft = (over: Partial<PlanDraft>): PlanDraft => ({
  from: { type: "place", place: stop },
  to: { type: "place", place: technion },
  when: { mode: "now" },
  ...over,
});

describe("buildJourneyRequest", () => {
  it("sends a stop as {kind: stop} and a map pin as a coordinate, results 3 and lang", () => {
    const result = buildJourneyRequest(draft({}), ctx({ lang: "en" }));
    expect(result).toEqual({
      ok: true,
      request: {
        from: { kind: "stop", stopId: "mot:stop:13583" },
        to: { kind: "coordinate", latitude: 32.7767, longitude: 35.0231 },
        departAt: "2026-11-02T08:00:00+02:00",
        results: 3,
        lang: "en",
      },
      fallback: null,
    });
  });

  it("sends now as an explicit Israel timestamp with its offset (summer and winter)", () => {
    const summer = buildJourneyRequest(draft({}), ctx({ now: new Date("2026-10-01T05:07:09Z") }));
    expect(summer.ok && summer.request.departAt).toBe("2026-10-01T08:07:09+03:00");
    const winter = buildJourneyRequest(draft({}), ctx());
    expect(winter.ok && winter.request.departAt).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\+02:00$/);
  });

  it("resolves my location to the fix's coordinate", () => {
    const result = buildJourneyRequest(
      draft({ from: { type: "myLocation" } }),
      ctx({ myLocation: { latitude: 32.08, longitude: 34.78, accuracyMeters: 10, at: 0 } }),
    );
    expect(result.ok && result.request.from).toEqual({ kind: "coordinate", latitude: 32.08, longitude: 34.78 });
  });

  it("reports a denied or missing location instead of guessing a start", () => {
    expect(buildJourneyRequest(draft({ from: { type: "myLocation" } }), ctx({ myLocation: "denied" }))).toEqual({
      ok: false,
      reason: "location",
      error: "denied",
    });
    expect(buildJourneyRequest(draft({ from: { type: "myLocation" } }), ctx())).toMatchObject({ ok: false, error: "unavailable" });
  });

  it("sends a searched place as its placeRef from the current generation, with a coordinate fallback", () => {
    const result = buildJourneyRequest(draft({ to: { type: "place", place: searched } }), ctx());
    expect(result.ok && result.request.to).toEqual({ kind: "place", placeRef: "mot:place:v1:abc" });
    expect(result.ok && result.fallback?.to).toEqual({ kind: "coordinate", latitude: 32.07, longitude: 34.77 });
    expect(result.ok && result.fallback?.from).toEqual({ kind: "stop", stopId: "mot:stop:13583" });
  });

  it("sends the coordinate when the ref belongs to another or an unknown generation", () => {
    for (const generationId of ["gen-b", null]) {
      const result = buildJourneyRequest(draft({ to: { type: "place", place: searched } }), ctx({ generationId }));
      expect(result.ok && result.request.to).toEqual({ kind: "coordinate", latitude: 32.07, longitude: 34.77 });
      expect(result.ok && result.fallback).toBeNull();
    }
    const saved = place({ placeRef: "mot:place:v1:old", refGenerationId: null });
    const result = buildJourneyRequest(draft({ to: { type: "place", place: saved } }), ctx());
    expect(result.ok && result.request.to.kind).toBe("coordinate");
  });

  it("sends depart at and arrive by through departureInstant", () => {
    const depart = buildJourneyRequest(draft({ when: { mode: "depart_at", wall: "2026-11-02T08:00", offset: "auto" } }), ctx());
    expect(depart.ok && depart.request).toMatchObject({ departAt: "2026-11-02T08:00:00+02:00" });
    expect(depart.ok && "arriveBy" in depart.request).toBe(false);
    const arrive = buildJourneyRequest(draft({ when: { mode: "arrive_by", wall: "2026-10-01T09:00", offset: "auto" } }), ctx());
    expect(arrive.ok && arrive.request).toMatchObject({ arriveBy: "2026-10-01T09:00:00+03:00" });
  });

  it("refuses a time skipped by the spring change and asks about a repeated autumn hour", () => {
    expect(buildJourneyRequest(draft({ when: { mode: "depart_at", wall: "2026-03-27T02:30", offset: "auto" } }), ctx())).toEqual({
      ok: false,
      reason: "time",
      problem: "nonexistent",
      candidates: [],
    });
    expect(buildJourneyRequest(draft({ when: { mode: "depart_at", wall: "2026-10-25T01:30", offset: "auto" } }), ctx())).toEqual({
      ok: false,
      reason: "time",
      problem: "ambiguous",
      candidates: ["+03:00", "+02:00"],
    });
    const chosen = buildJourneyRequest(draft({ when: { mode: "depart_at", wall: "2026-10-25T01:30", offset: "+02:00" } }), ctx());
    expect(chosen.ok && chosen.request.departAt).toBe("2026-10-25T01:30:00+02:00");
  });

  it("uses an Earlier / Later override instead of the draft's time", () => {
    const result = buildJourneyRequest(draft({}), ctx({ override: { arriveBy: "2026-11-02T09:51:00+02:00" } }));
    expect(result.ok && result.request).toMatchObject({ arriveBy: "2026-11-02T09:51:00+02:00" });
    expect(result.ok && result.request.departAt).toBeUndefined();
  });

  it("needs a destination", () => {
    expect(buildJourneyRequest(draft({ to: null }), ctx())).toEqual({ ok: false, reason: "missing_destination" });
  });
});

describe("resolveJourneyRequest", () => {
  const source = (current: LocationSource["current"]): LocationSource => ({ current, watch: () => () => {} });

  it("asks the location source only when the draft uses my location", async () => {
    const current = vi.fn(async () => ({ ok: true as const, fix: { latitude: 32, longitude: 34.8, accuracyMeters: null, at: 1 } }));
    const restore = setLocationSource(source(current));
    try {
      await resolveJourneyRequest(draft({}), { lang: "he", generationId: null });
      expect(current).not.toHaveBeenCalled();
      const result = await resolveJourneyRequest(draft({ from: { type: "myLocation" } }), { lang: "he", generationId: null });
      expect(current).toHaveBeenCalledTimes(1);
      expect(result.ok && result.request.from).toEqual({ kind: "coordinate", latitude: 32, longitude: 34.8 });
    } finally {
      restore();
    }
  });

  it("passes a denied permission through as a location problem", async () => {
    const restore = setLocationSource(source(async () => ({ ok: false, error: "denied" })));
    try {
      expect(await resolveJourneyRequest(draft({ from: { type: "myLocation" } }), { lang: "he", generationId: null })).toEqual({
        ok: false,
        reason: "location",
        error: "denied",
      });
    } finally {
      restore();
    }
  });
});
