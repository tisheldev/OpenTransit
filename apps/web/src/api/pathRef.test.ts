import { describe, expect, it } from "vitest";
import { fixtures } from "./fixtures";
import { encodePathRef } from "./pathRef";
import { JourneyResponseSchema } from "./schemas";

/** Every trip ref in the recorded real-API fixtures (journey legs, trips, departures). */
function recordedTripRefs(): string[] {
  const refs = new Set<string>();
  for (const [name, found] of Object.entries(fixtures)) {
    if (!name.startsWith("recorded-")) continue;
    const text = JSON.stringify(found.body);
    for (const match of text.matchAll(/"(?:engineTripId|tripRef)":"([^"]+)"/g)) refs.add(match[1]!);
  }
  return [...refs];
}

describe("encodePathRef()", () => {
  it("round-trips every real trip ref recorded from the API", () => {
    const refs = recordedTripRefs();
    expect(refs.length).toBeGreaterThan(10);
    for (const ref of refs) {
      const encoded = encodePathRef(ref);
      expect(encoded.ok, ref).toBe(true);
      if (!encoded.ok) continue;
      expect(encoded.segment).not.toMatch(/[/?#]/);
      expect(decodeURIComponent(encoded.segment)).toBe(ref);
      // The URL parser keeps the segment intact, so the server sees exactly one segment.
      const url = new URL(`/v1/trips/${encoded.segment}`, "http://localhost");
      expect(url.pathname.split("/")).toHaveLength(4);
    }
  });

  it("uses journey engineTripIds verbatim", () => {
    const body = JourneyResponseSchema.parse(fixtures["recorded-journey-routes"]!.body);
    const ids = body.data.journeys.flatMap((journey) =>
      journey.legs.flatMap((leg) => (leg.transit ? [leg.transit.engineTripId] : [])),
    );
    expect(ids.length).toBeGreaterThan(0);
    expect(ids[0]).toMatch(/^\d{8}_\d{2}:\d{2}_mot60day_/);
    expect(encodePathRef(ids[0]!)).toEqual({ ok: true, segment: encodeURIComponent(ids[0]!) });
  });

  it("encodes stop and route IDs as one segment", () => {
    expect(encodePathRef("mot:stop:13583")).toEqual({ ok: true, segment: "mot%3Astop%3A13583" });
    expect(encodePathRef("a b%c?d#e")).toEqual({ ok: true, segment: "a%20b%25c%3Fd%23e" });
  });

  it.each([
    ["", "empty"],
    ["2026_a/b", "contains_slash"],
    ["2026_a\\b", "contains_slash"],
    [".", "dot_segment"],
    ["..", "dot_segment"],
    ["x".repeat(769), "too_long"],
  ])("refuses %j (%s)", (ref, reason) => {
    expect(encodePathRef(ref)).toEqual({ ok: false, reason });
  });
});
