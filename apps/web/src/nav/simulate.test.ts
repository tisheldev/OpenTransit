import { describe, expect, it } from "vitest";
import { haversineMeters } from "./geo";
import { simulateJourney } from "./simulate";
import { recordedJourneys } from "./testdata";

const journey = recordedJourneys[1]!;
const firstDeparture = Date.parse(journey.legs[0]!.timing.scheduledDeparture);
const arrival = Date.parse(journey.timing.scheduledArrival);

describe("simulateJourney", () => {
  it("follows the schedule from a minute before the first departure, labelled simulated", () => {
    const fixes = simulateJourney(journey);
    expect(fixes[0]!.at).toBe(firstDeparture - 60_000);
    expect(fixes.at(-1)!.at).toBeLessThanOrEqual(arrival + 60_000);
    expect(fixes.every((fix) => fix.simulated && fix.accuracyMeters === 10)).toBe(true);
    for (let i = 1; i < fixes.length; i += 1) expect(fixes[i]!.at - fixes[i - 1]!.at).toBe(5_000);
    const origin = journey.legs[0]!.from;
    expect(haversineMeters(fixes[0]!, origin)).toBeLessThan(1);
    const destination = journey.legs.at(-1)!.to;
    // The walk geometry ends a few metres from the engine's END point.
    expect(haversineMeters(fixes.at(-1)!, destination)).toBeLessThan(10);
  });

  it("is at each leg's end by its scheduled arrival, at plausible speeds", () => {
    const fixes = simulateJourney(journey, { intervalMs: 1_000 });
    for (const leg of journey.legs) {
      const fix = fixes.find((f) => f.at === Date.parse(leg.timing.scheduledArrival))!;
      expect(haversineMeters(fix, leg.to)).toBeLessThan(30);
    }
    for (let i = 1; i < fixes.length; i += 1) {
      const speed = haversineMeters(fixes[i]!, fixes[i - 1]!) / 1; // m/s
      expect(speed).toBeLessThan(70); // a train between stations, never a jump
    }
  });

  it("walks a time-only transfer in a straight line (test data only)", () => {
    const walk = journey.legs[3]!;
    expect(walk.geometry).toBeNull();
    const fixes = simulateJourney(journey, { intervalMs: 1_000 });
    const mid = fixes.find((f) => f.at === Date.parse(walk.timing.scheduledDeparture) + 30_000)!;
    const straight = haversineMeters(walk.from, walk.to);
    expect(haversineMeters(walk.from, mid) + haversineMeters(mid, walk.to)).toBeCloseTo(straight, 0);
  });

  it("adds seeded jitter, a gap and a playback speed-up", () => {
    const plain = simulateJourney(journey);
    const noisy = simulateJourney(journey, { jitterMeters: 20, seed: 5 });
    expect(simulateJourney(journey, { jitterMeters: 20, seed: 5 })).toEqual(noisy);
    const offsets = noisy.map((fix, i) => haversineMeters(fix, plain[i]!));
    expect(Math.max(...offsets)).toBeLessThanOrEqual(20.001);
    expect(Math.max(...offsets)).toBeGreaterThan(5);

    const gapped = simulateJourney(journey, { gap: { afterMs: 120_000, durationMs: 90_000 } });
    expect(gapped.length).toBe(plain.length - 18);
    expect(gapped.some((fix) => fix.at >= plain[0]!.at + 120_000 && fix.at < plain[0]!.at + 210_000)).toBe(false);

    const fast = simulateJourney(journey, { speedUp: 10, accuracyMeters: null });
    expect(fast[1]!.offsetMs).toBe(500);
    expect(fast[1]!.at).toBe(plain[1]!.at);
    expect(fast[0]!.accuracyMeters).toBeNull();
  });
});
