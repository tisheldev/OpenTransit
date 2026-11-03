import { afterEach, describe, expect, it, vi } from "vitest";
import type { Metadata } from "../api/types";
import type { Fix } from "../lib/geolocation";
import { startActiveTrip } from "./activeTrip";
import { initialNavState } from "./engine";
import { isSimulatedFix, simulatedSource } from "./simulatedSource";
import { buildSteps } from "./steps";
import { recordedJourneys, recordedTrips } from "./testdata";
import { restoreNavState, simStartFor } from "./useNavigation";

afterEach(() => vi.useRealTimers());

describe("simulated source", () => {
  it("plays fixes in order at the speed-up, every one labelled simulated, and stops cleanly", () => {
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout", "Date"] });
    const journey = recordedJourneys[0]!;
    const got: Fix[] = [];
    const stop = simulatedSource(journey, { speedUp: 100 }).watch((fix) => got.push(fix), () => {});
    expect(got).toHaveLength(1); // the first fix plays at once
    vi.advanceTimersByTime(1_000); // 1 s × 100 = 100 s of timetable time, fixes every 5 s
    expect(got.length).toBeGreaterThanOrEqual(20);
    expect(got.length).toBeLessThanOrEqual(22);
    expect(got.every(isSimulatedFix)).toBe(true);
    expect(got.every((fix, i) => i === 0 || fix.at > got[i - 1]!.at)).toBe(true);
    stop();
    const count = got.length;
    vi.advanceTimersByTime(10_000);
    expect(got).toHaveLength(count);
  });

  it("can start at a step: fixes before its start are skipped", () => {
    const journey = recordedJourneys[0]!;
    const steps = buildSteps(journey, recordedTrips);
    const from = simStartFor(steps, 2)!;
    const got: Fix[] = [];
    simulatedSource(journey, { speedUp: 1, fromTime: from }).watch((fix) => got.push(fix), () => {})();
    expect(got[0]!.at).toBeGreaterThanOrEqual(from);
    expect(simStartFor(steps, steps.length - 1)).toBeNull();
  });

  it("real fixes are not labelled simulated", () => {
    expect(isSimulatedFix({ latitude: 32, longitude: 34, accuracyMeters: 5, at: 1 })).toBe(false);
  });
});

describe("restore", () => {
  it("keeps a stored engine state, and starts a fresh fix timeline", () => {
    const journey = recordedJourneys[0]!;
    const steps = buildSteps(journey, recordedTrips);
    const trip = startActiveTrip({ journey, meta: {} as Metadata, trips: recordedTrips });
    const stored = { ...initialNavState(steps, 0), stepIndex: 2, phase: "riding" as const, lastFixAt: 99, locationMode: "manual" as const };
    const restored = restoreNavState({ ...trip, nav: stored }, steps, 1_000);
    expect(restored).toMatchObject({ stepIndex: 2, phase: "riding", lastFixAt: null, locationMode: "auto", autoSince: 1_000 });
  });

  it("a bare step index (as Compare's Start stores) or a bad one is clamped onto the steps", () => {
    const journey = recordedJourneys[0]!;
    const steps = buildSteps(journey, recordedTrips);
    const trip = startActiveTrip({ journey, meta: {} as Metadata, trips: recordedTrips });
    expect(restoreNavState({ ...trip, nav: { stepIndex: 3 } }, steps, 0).stepIndex).toBe(3);
    expect(restoreNavState({ ...trip, nav: { stepIndex: 99 } }, steps, 0).stepIndex).toBe(steps.length - 1);
    expect(restoreNavState({ ...trip, nav: { stepIndex: 0 } }, steps, 0).phase).toBe("waiting");
  });
});
