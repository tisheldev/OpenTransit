import { describe, expect, it } from "vitest";
import type { Journey } from "../api/types";
import type { Fix } from "../lib/geolocation";
import { NAV_THRESHOLDS } from "./constants";
import { advance, initialNavState, isNavState, type CallPosition, type NavContext, type NavEffect, type NavState } from "./engine";
import { destinationPoint, pointAlongLine } from "./geo";
import { simulateJourney, type SimulateOptions } from "./simulate";
import { buildSteps, type NavStep } from "./steps";
import { callPositionsFor, recordedJourneys, recordedTrips } from "./testdata";

type Positions = "none" | "all" | "two_before_exit";

function setup(journey: Journey, positions: Positions = "none", trips = recordedTrips) {
  const steps = buildSteps(journey, trips);
  const callPositions: Record<number, CallPosition[]> = positions === "none" ? {} : callPositionsFor(steps, positions);
  const ctx = (now: number): NavContext => ({ steps, journey, callPositions, now });
  return { steps, ctx };
}

interface Log {
  state: NavState;
  effects: NavEffect[];
  /** Step index after each fix. */
  trail: number[];
  stopsLeftByStep: Record<number, Array<number | null>>;
}

function run(journey: Journey, positions: Positions, options: SimulateOptions = {}): Log {
  const { steps, ctx } = setup(journey, positions);
  const fixes = simulateJourney(journey, options);
  let state = initialNavState(steps, fixes[0]!.at);
  const effects: NavEffect[] = [];
  const trail: number[] = [];
  const stopsLeftByStep: Log["stopsLeftByStep"] = {};
  for (const fix of fixes) {
    const result = advance(state, { type: "fix", fix }, ctx(fix.at));
    state = result.state;
    effects.push(...result.effects);
    trail.push(state.stepIndex);
    (stopsLeftByStep[state.stepIndex] ??= []).push(state.stopsLeft);
  }
  return { state, effects, trail, stopsLeftByStep };
}

const stepChanges = (effects: NavEffect[]) => effects.filter((e) => e.type === "step_changed");
const cues = (effects: NavEffect[]) => effects.filter((e) => e.type === "cue").map((e) => (e.type === "cue" ? `${e.stepIndex}:${e.cue}` : ""));

function expectedCues(steps: readonly NavStep[]): string[] {
  return steps.flatMap((step) => {
    const count = step.ride?.stopCount;
    if (!count) return [];
    return count >= 2 ? [`${step.index}:two_stops`, `${step.index}:next_stop`] : [`${step.index}:next_stop`];
  });
}

const at = (fix: Partial<Fix> & Pick<Fix, "latitude" | "longitude" | "at">): Fix => ({ accuracyMeters: 10, ...fix });

describe("advance through whole simulated journeys", () => {
  it.each([0, 1, 2])("journey %i reaches arrived, one automatic step at a time", (index) => {
    const journey = recordedJourneys[index]!;
    const { steps } = setup(journey);
    const log = run(journey, "none");
    expect(log.state.phase).toBe("arrived");
    expect(log.state.stepIndex).toBe(steps.length - 1);
    const changes = stepChanges(log.effects);
    expect(changes.map((e) => (e.type === "step_changed" ? e.stepIndex : -1))).toEqual(steps.slice(1).map((s) => s.index));
    expect(changes.every((e) => e.type === "step_changed" && e.reason === "auto")).toBe(true);
    expect(log.effects.filter((e) => e.type === "arrived")).toHaveLength(1);
    // Without call positions there are no cues; stops left stays at the stop count.
    expect(cues(log.effects)).toEqual([]);
    expect(log.state.lastFixAt).not.toBeNull();
  });

  it.each([0, 1, 2])("journey %i with every call position cues two stops, then the next stop, on every ride", (index) => {
    const journey = recordedJourneys[index]!;
    const log = run(journey, "all", { jitterMeters: 15, seed: 7 });
    expect(log.state.phase).toBe("arrived");
    const expected = expectedCues(setup(journey).steps);
    expect(expected.length).toBeGreaterThanOrEqual(4);
    expect(cues(log.effects)).toEqual(expected);
  });

  it.each([0, 1, 2])("journey %i with only the two calls before each exit gives the same cues", (index) => {
    const journey = recordedJourneys[index]!;
    const log = run(journey, "two_before_exit", { jitterMeters: 10, seed: 3 });
    expect(log.state.phase).toBe("arrived");
    const expected = expectedCues(setup(journey).steps);
    expect(expected.length).toBeGreaterThanOrEqual(4);
    expect(cues(log.effects)).toEqual(expected);
  });

  it("cues only the rides that have positions", () => {
    const journey = recordedJourneys[0]!;
    const { steps } = setup(journey);
    const some = callPositionsFor(steps, "two_before_exit");
    delete some[2];
    const fixes = simulateJourney(journey);
    let state = initialNavState(steps, fixes[0]!.at);
    const effects: NavEffect[] = [];
    for (const fix of fixes) {
      const result = advance(state, { type: "fix", fix }, { steps, journey, callPositions: some, now: fix.at });
      state = result.state;
      effects.push(...result.effects);
    }
    expect(state.phase).toBe("arrived");
    expect(cues(effects)).toEqual(expectedCues(steps).filter((cue) => !cue.startsWith("2:")));
  });

  it("never moves ride progress backwards on noisy fixes", () => {
    const journey = recordedJourneys[2]!;
    const log = run(journey, "all", { jitterMeters: 30, seed: 11, intervalMs: 2_000 });
    expect(log.state.phase).toBe("arrived");
    for (const values of Object.values(log.stopsLeftByStep)) {
      const numbers = values.filter((v): v is number => v !== null);
      for (let i = 1; i < numbers.length; i += 1) expect(numbers[i]!).toBeLessThanOrEqual(numbers[i - 1]!);
    }
    // The step index only ever increases on automatic advance.
    for (let i = 1; i < log.trail.length; i += 1) expect(log.trail[i]!).toBeGreaterThanOrEqual(log.trail[i - 1]!);
  });

  it("does not undo a passed call when a later fix falls behind it", () => {
    const journey = recordedJourneys[0]!;
    const { steps, ctx } = setup(journey, "all");
    const line = journey.legs[0]!.geometry!.coordinates;
    const departure = Date.parse(steps[0]!.scheduledDeparture);
    let state = initialNavState(steps, departure - 60_000);
    const fixAt = (meters: number, t: number) => at({ ...pointAlongLine(line, meters)!, at: t });
    state = advance(state, { type: "fix", fix: fixAt(0, departure - 30_000) }, ctx(departure - 30_000)).state;
    // Far along the ride: several calls passed.
    const far = fixAt(1500, departure + 200_000);
    state = advance(state, { type: "fix", fix: far }, ctx(far.at)).state;
    expect(state.phase).not.toBe("waiting");
    const left = state.stopsLeft!;
    expect(left).toBeLessThan(steps[0]!.ride!.stopCount!);
    const back = fixAt(300, departure + 205_000);
    const after = advance(state, { type: "fix", fix: back }, ctx(back.at)).state;
    expect(after.stopsLeft).toBe(left);
    expect(after.stepIndex).toBe(0);
  });
});

describe("clock and location", () => {
  const journey = recordedJourneys[2]!;
  const { steps, ctx } = setup(journey);
  const start = Date.parse(steps[0]!.scheduledDeparture) - 60_000;

  it("never advances a step on the clock alone", () => {
    let state = initialNavState(steps, start);
    for (let t = start; t < Date.parse(journey.timing.scheduledArrival) + 3 * 3600_000; t += 30_000) {
      state = advance(state, { type: "tick" }, ctx(t)).state;
    }
    expect(state.stepIndex).toBe(0);
    expect(state.phase).toBe("walking");
  });

  it("flags location lost after 60 s without an accepted fix, and recovers on a fix", () => {
    let state = initialNavState(steps, start);
    state = advance(state, { type: "tick" }, ctx(start + 60_000)).state;
    expect(state.locationLost).toBe(false);
    state = advance(state, { type: "tick" }, ctx(start + 60_001)).state;
    expect(state.locationLost).toBe(true);
    const origin = steps[0]!.from!;
    const fix = at({ latitude: origin.latitude, longitude: origin.longitude, at: start + 61_000 });
    state = advance(state, { type: "fix", fix }, ctx(start + 62_000)).state;
    expect(state.locationLost).toBe(false);
    expect(state.lastFixAt).toBe(start + 61_000);
    state = advance(state, { type: "tick" }, ctx(start + 61_000 + 60_000)).state;
    expect(state.locationLost).toBe(false);
    state = advance(state, { type: "tick" }, ctx(start + 61_000 + 61_000)).state;
    expect(state.locationLost).toBe(true);
  });

  it("goes lost during a GPS gap in a simulated ride and recovers after it", () => {
    const fixes = simulateJourney(journey, { gap: { afterMs: 6 * 60_000, durationMs: 3 * 60_000 } });
    let state = initialNavState(steps, fixes[0]!.at);
    let sawLost = false;
    let previous = fixes[0]!.at;
    for (const fix of fixes) {
      for (let t = previous + 10_000; t < fix.at; t += 10_000) {
        state = advance(state, { type: "tick" }, ctx(t)).state;
        sawLost ||= state.locationLost;
      }
      const stepBefore = state.stepIndex;
      state = advance(state, { type: "fix", fix }, ctx(fix.at)).state;
      expect(state.stepIndex).toBeGreaterThanOrEqual(stepBefore);
      expect(state.locationLost).toBe(false);
      previous = fix.at;
    }
    expect(sawLost).toBe(true);
    expect(state.phase).toBe("arrived");
  });

  it("switches to manual: fixes and ticks are ignored, no lost flag", () => {
    let state = initialNavState(steps, start);
    state = advance(state, { type: "locationMode", mode: "manual" }, ctx(start)).state;
    expect(state).toMatchObject({ locationMode: "manual", autoSince: null });
    state = advance(state, { type: "tick" }, ctx(start + 600_000)).state;
    expect(state.locationLost).toBe(false);
    const target = steps[0]!.target;
    const fix = at({ latitude: target.latitude, longitude: target.longitude, at: start + 600_000 });
    expect(advance(state, { type: "fix", fix }, ctx(start + 600_000)).state).toBe(state);
    // Back to auto: measured from the switch, not from an old fix.
    state = advance(state, { type: "locationMode", mode: "auto" }, ctx(start + 700_000)).state;
    expect(advance(state, { type: "tick" }, ctx(start + 750_000)).state.locationLost).toBe(false);
    expect(advance(state, { type: "tick" }, ctx(start + 761_000)).state.locationLost).toBe(true);
  });

  it("ignores inaccurate, stale, out-of-order and invalid fixes", () => {
    const target = steps[0]!.target;
    const now = start + 120_000;
    const near = { latitude: target.latitude, longitude: target.longitude };
    const state = initialNavState(steps, start);
    const bad: Fix[] = [
      { ...near, accuracyMeters: NAV_THRESHOLDS.maxFixAccuracyMeters + 1, at: now },
      { ...near, accuracyMeters: 5, at: now - NAV_THRESHOLDS.maxFixAgeMs - 1 },
      { ...near, accuracyMeters: Number.NaN, at: now },
      { latitude: Number.NaN, longitude: near.longitude, accuracyMeters: 5, at: now },
    ];
    for (const fix of bad) expect(advance(state, { type: "fix", fix }, ctx(now))).toEqual({ state, effects: [] });
    const accepted = advance(state, { type: "fix", fix: { ...near, accuracyMeters: 100, at: now } }, ctx(now)).state;
    expect(accepted.phase).toBe("waiting");
    expect(accepted.lastFixAt).toBe(now);
    const older = { ...near, accuracyMeters: 5, at: now - 1_000 };
    expect(advance(accepted, { type: "fix", fix: older }, ctx(now)).state).toBe(accepted);
  });

  it("stores no coordinates in the state", () => {
    const log = run(journey, "all", { jitterMeters: 10 });
    const json = JSON.stringify(log.state);
    expect(json).not.toMatch(/latitude|longitude/);
    expect(Object.keys(log.state).sort()).toEqual(
      ["autoSince", "cue", "lastFixAt", "locationLost", "locationMode", "nearBoarding", "phase", "stepIndex", "stopsLeft"].sort(),
    );
    expect(isNavState(log.state, setup(journey).steps)).toBe(true);
    expect(isNavState({ ...log.state, stepIndex: 99 }, setup(journey).steps)).toBe(false);
    expect(isNavState({ stepIndex: 0 }, setup(journey).steps)).toBe(false);
  });
});

describe("manual control", () => {
  const journey = recordedJourneys[1]!;
  const { steps, ctx } = setup(journey);
  const now = Date.parse(steps[0]!.scheduledDeparture);

  it("next goes through every step, then stops at arrive", () => {
    let state = initialNavState(steps, now);
    const effects: NavEffect[] = [];
    for (let i = 1; i < steps.length; i += 1) {
      const result = advance(state, { type: "next" }, ctx(now));
      state = result.state;
      effects.push(...result.effects);
      expect(state.stepIndex).toBe(i);
      const kind = steps[i]!.kind;
      expect(state.phase).toBe(kind === "ride" ? "riding" : kind === "arrive" ? "arrived" : "walking");
      expect(state.stopsLeft).toBe(steps[i]!.ride?.stopCount ?? null);
    }
    expect(effects.filter((e) => e.type === "arrived")).toHaveLength(1);
    expect(stepChanges(effects).every((e) => e.type === "step_changed" && e.reason === "manual")).toBe(true);
    expect(advance(state, { type: "next" }, ctx(now))).toEqual({ state, effects: [] });
  });

  it("jump moves forward and back, and ignores out-of-range or same-step jumps", () => {
    let state = initialNavState(steps, now);
    let result = advance(state, { type: "jump", stepIndex: 4 }, ctx(now));
    expect(result.state).toMatchObject({ stepIndex: 4, phase: "riding", cue: "none", stopsLeft: steps[4]!.ride!.stopCount });
    expect(result.effects).toEqual([{ type: "step_changed", stepIndex: 4, from: 0, reason: "manual" }]);
    state = result.state;
    result = advance(state, { type: "jump", stepIndex: 1 }, ctx(now));
    expect(result.state).toMatchObject({ stepIndex: 1, phase: "walking", stopsLeft: null });
    state = result.state;
    // Back to the first ride: the passenger waits at its stop (it starts the journey).
    expect(advance(state, { type: "jump", stepIndex: 0 }, ctx(now)).state).toMatchObject({ stepIndex: 0, phase: "waiting" });
    for (const stepIndex of [-1, steps.length, 1.5, 1]) {
      expect(advance(state, { type: "jump", stepIndex }, ctx(now))).toEqual({ state, effects: [] });
    }
    const arrived = advance(state, { type: "jump", stepIndex: steps.length - 1 }, ctx(now));
    expect(arrived.state.phase).toBe("arrived");
    expect(arrived.effects.some((e) => e.type === "arrived")).toBe(true);
    // A wrong arrival is corrected by jumping back; fixes count again.
    expect(advance(arrived.state, { type: "jump", stepIndex: 5 }, ctx(now)).state.phase).toBe("walking");
  });

  it("a cue in progress is cleared by a jump back to the walk", () => {
    const cueJourney = recordedJourneys[0]!;
    const { steps: cueSteps, ctx: cueCtx } = setup(cueJourney, "all");
    const fixes = simulateJourney(cueJourney);
    let state = initialNavState(cueSteps, fixes[0]!.at);
    for (const fix of fixes) {
      state = advance(state, { type: "fix", fix }, cueCtx(fix.at)).state;
      if (state.cue !== "none") break;
    }
    expect(state).toMatchObject({ stepIndex: 0, cue: "two_stops", phase: "cue_two", stopsLeft: 2 });
    const jumped = advance(state, { type: "jump", stepIndex: 1 }, cueCtx(state.lastFixAt!)).state;
    expect(jumped).toMatchObject({ stepIndex: 1, cue: "none", phase: "walking", stopsLeft: null });
  });
});

describe("boarding", () => {
  it("a ride at the origin stop waits, and boards only from a minute before departure", () => {
    const journey = recordedJourneys[0]!;
    const { steps, ctx } = setup(journey);
    const departure = Date.parse(steps[0]!.scheduledDeparture);
    const line = journey.legs[0]!.geometry!.coordinates;
    let state = initialNavState(steps, departure - 300_000);
    expect(state).toMatchObject({ stepIndex: 0, phase: "waiting", stopsLeft: 4 });
    const stop = steps[0]!.from!;
    state = advance(state, { type: "fix", fix: at({ latitude: stop.latitude, longitude: stop.longitude, at: departure - 290_000 }) }, ctx(departure - 290_000)).state;
    // 300 m along the route, but four minutes early: not boarded (walking along the street).
    const along = pointAlongLine(line, 300)!;
    state = advance(state, { type: "fix", fix: at({ ...along, at: departure - 240_000 }) }, ctx(departure - 240_000)).state;
    expect(state.phase).toBe("waiting");
    // Off the route, after the window opens: not boarded.
    const off = destinationPoint(along, 0, 400);
    state = advance(state, { type: "fix", fix: at({ ...off, at: departure - 30_000 }) }, ctx(departure - 30_000)).state;
    expect(state.phase).toBe("waiting");
    state = advance(state, { type: "fix", fix: at({ ...along, at: departure + 30_000 }) }, ctx(departure + 30_000)).state;
    expect(state).toMatchObject({ stepIndex: 0, phase: "riding" });
  });

  it("a walk to the stop waits within 40 m and boards when the vehicle leaves", () => {
    const journey = recordedJourneys[2]!;
    const { steps, ctx } = setup(journey);
    const ride = steps[1]!;
    const departure = Date.parse(ride.scheduledDeparture);
    let state = initialNavState(steps, departure - 600_000);
    const stop = ride.from!;
    const result = advance(state, { type: "fix", fix: at({ ...destinationPoint(stop, 90, 35), at: departure - 120_000 }) }, ctx(departure - 120_000));
    state = result.state;
    expect(state).toMatchObject({ stepIndex: 0, phase: "waiting", nearBoarding: true });
    expect(result.effects).toEqual([]);
    const line = journey.legs[1]!.geometry!.coordinates;
    const moved = advance(state, { type: "fix", fix: at({ ...pointAlongLine(line, 400)!, at: departure + 60_000 }) }, ctx(departure + 60_000));
    expect(moved.state).toMatchObject({ stepIndex: 1, phase: "riding" });
    expect(moved.effects).toContainEqual({ type: "step_changed", stepIndex: 1, from: 0, reason: "auto" });
  });

  it("a transfer at the same stop is waiting as soon as the first ride ends", () => {
    const journey = recordedJourneys[2]!;
    const { steps } = setup(journey);
    // Step 4 is the zero-length walk at Olga junction (mot:stop:2563) between rides 3 and 5.
    expect(steps[4]!.distanceMeters).toBe(0);
    const { effects, state } = run(journey, "none");
    expect(state.phase).toBe("arrived");
    expect(stepChanges(effects).map((e) => (e.type === "step_changed" ? e.stepIndex : -1))).toContain(4);
  });

  it("two rides at the same stop: exit goes straight to the next ride, waiting, then boards", () => {
    const base = recordedJourneys[2]!;
    // Sanitised variant: drop the zero-length walk at Olga junction so ride follows ride.
    const journey: Journey = { ...base, legs: base.legs.filter((_, index) => index !== 4) };
    const { steps, ctx } = setup(journey);
    expect(steps[3]!.kind).toBe("ride");
    expect(steps[4]!.kind).toBe("ride");
    const fixes = simulateJourney(journey);
    let state = initialNavState(steps, fixes[0]!.at);
    let enteredSecond: NavState | null = null;
    for (const fix of fixes) {
      const before = state.stepIndex;
      state = advance(state, { type: "fix", fix }, ctx(fix.at)).state;
      if (before === 3 && state.stepIndex === 4) enteredSecond = state;
    }
    expect(enteredSecond).toMatchObject({ stepIndex: 4, phase: "waiting", nearBoarding: true });
    expect(state.phase).toBe("arrived");
    // Manual next from the first ride to the second also waits.
    const manual = advance({ ...initialNavState(steps, 0), stepIndex: 3, phase: "riding" }, { type: "next" }, ctx(0)).state;
    expect(manual).toMatchObject({ stepIndex: 4, phase: "waiting" });
  });

  it("a ride without trip detail advances on reaching the exit, without stops left or cues", () => {
    const journey = recordedJourneys[1]!;
    const steps = buildSteps(journey, {});
    const fixes = simulateJourney(journey, { jitterMeters: 10 });
    let state = initialNavState(steps, fixes[0]!.at);
    const effects: NavEffect[] = [];
    for (const fix of fixes) {
      const result = advance(state, { type: "fix", fix }, { steps, journey, callPositions: callPositionsFor(buildSteps(journey, recordedTrips), "all"), now: fix.at });
      state = result.state;
      effects.push(...result.effects);
      expect(state.stopsLeft).toBeNull();
    }
    expect(state.phase).toBe("arrived");
    expect(cues(effects)).toEqual([]);
  });
});
