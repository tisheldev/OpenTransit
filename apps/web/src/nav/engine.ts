import type { Journey } from "../api/types";
import type { Fix } from "../lib/geolocation";
import { NAV_THRESHOLDS as T } from "./constants";
import { haversineMeters, projectOntoLine, type LatLon, type Position } from "./geo";
import type { NavStep } from "./steps";

// The navigation engine (design: Navigation engine): a pure reducer. It holds no timers
// and performs no I/O; the caller supplies `now`. It never advances a step from the
// clock, and its state holds no position (the state is persisted).

export type NavPhase = "walking" | "waiting" | "riding" | "cue_two" | "cue_next" | "arrived";
export type NavCue = "none" | "two_stops" | "next_stop";
export type LocationMode = "auto" | "manual";

// A type alias (not an interface) so it is assignable to ActiveTrip's NavProgress.
export type NavState = {
  stepIndex: number;
  phase: NavPhase;
  /** Stops left on the current ride; null off a ride or without trip detail. */
  stopsLeft: number | null;
  cue: NavCue;
  locationMode: LocationMode;
  /** When the last accepted fix was taken (epoch ms). */
  lastFixAt: number | null;
  /** No accepted fix for 60 s while location is on. */
  locationLost: boolean;
  /** The current (or next) ride's boarding stop has been reached or approached. */
  nearBoarding: boolean;
  /** When automatic location started (epoch ms): "lost" is measured from here before a first fix. */
  autoSince: number | null;
};

export type NavEvent =
  | { type: "fix"; fix: Fix }
  | { type: "tick" }
  | { type: "next" }
  | { type: "jump"; stepIndex: number }
  | { type: "locationMode"; mode: LocationMode };

/** A call position (from `GET /v1/stops/{id}` until API-C1 puts them in the trip). */
export interface CallPosition {
  ordinal: number;
  latitude: number;
  longitude: number;
}

export interface NavContext {
  steps: readonly NavStep[];
  /** The journey the steps were built from (leg geometry). */
  journey: Journey;
  /** Known call positions per ride step index; any subset, or none. */
  callPositions?: Readonly<Record<number, readonly CallPosition[]>>;
  /** Epoch milliseconds, from the caller's clock. */
  now: number;
}

export type NavEffect =
  | { type: "cue"; cue: Exclude<NavCue, "none">; stepIndex: number }
  | { type: "step_changed"; stepIndex: number; from: number; reason: "auto" | "manual" }
  | { type: "arrived" };

export interface NavResult {
  state: NavState;
  effects: NavEffect[];
}

const PHASES: readonly NavPhase[] = ["walking", "waiting", "riding", "cue_two", "cue_next", "arrived"];
const CUES: readonly NavCue[] = ["none", "two_stops", "next_stop"];

const isWalk = (step: NavStep | undefined) =>
  !!step && (step.kind === "walk_to_stop" || step.kind === "transfer_walk" || step.kind === "walk_to_destination");

/** A ride entered after a walk means the passenger boarded; otherwise they wait at the stop. */
function rideEntry(steps: readonly NavStep[], index: number): "riding" | "waiting" {
  return isWalk(steps[index - 1]) ? "riding" : "waiting";
}

function enter(state: NavState, steps: readonly NavStep[], index: number, rideAs: "riding" | "waiting"): NavState {
  const step = steps[index]!;
  if (step.kind === "ride") {
    return {
      ...state,
      stepIndex: index,
      phase: rideAs,
      stopsLeft: step.ride?.stopCount ?? null,
      cue: "none",
      nearBoarding: rideAs === "waiting",
    };
  }
  return {
    ...state,
    stepIndex: index,
    phase: step.kind === "arrive" ? "arrived" : "walking",
    stopsLeft: null,
    cue: "none",
    nearBoarding: false,
  };
}

/** The state at Start: first step, location automatic unless told otherwise. */
export function initialNavState(steps: readonly NavStep[], now: number, locationMode: LocationMode = "auto"): NavState {
  const base: NavState = {
    stepIndex: 0,
    phase: "walking",
    stopsLeft: null,
    cue: "none",
    locationMode,
    lastFixAt: null,
    locationLost: false,
    nearBoarding: false,
    autoSince: locationMode === "auto" ? now : null,
  };
  if (steps.length === 0) return { ...base, phase: "arrived" };
  // A journey starting with a ride: the passenger is at its stop, waiting.
  return enter(base, steps, 0, "waiting");
}

/** A stored state is usable for these steps (restore after the app is killed). */
export function isNavState(value: unknown, steps: readonly NavStep[]): value is NavState {
  if (!value || typeof value !== "object") return false;
  const s = value as Partial<NavState>;
  const nullableNumber = (v: unknown) => v === null || (typeof v === "number" && Number.isFinite(v));
  return (
    typeof s.stepIndex === "number" &&
    Number.isInteger(s.stepIndex) &&
    s.stepIndex >= 0 &&
    s.stepIndex < steps.length &&
    PHASES.includes(s.phase as NavPhase) &&
    CUES.includes(s.cue as NavCue) &&
    (s.locationMode === "auto" || s.locationMode === "manual") &&
    nullableNumber(s.stopsLeft) &&
    nullableNumber(s.lastFixAt) &&
    nullableNumber(s.autoSince) &&
    typeof s.locationLost === "boolean" &&
    typeof s.nearBoarding === "boolean"
  );
}

const lineOf = (journey: Journey, step: NavStep | undefined): readonly Position[] | null => {
  if (!step || step.legIndex === null) return null;
  const coords = journey.legs[step.legIndex]?.geometry?.coordinates;
  return coords && coords.length >= 2 ? coords : null;
};

const point = (fix: Fix): LatLon => ({ latitude: fix.latitude, longitude: fix.longitude });

function acceptable(state: NavState, fix: Fix, now: number): boolean {
  if (state.locationMode !== "auto" || state.phase === "arrived") return false;
  if (!Number.isFinite(fix.latitude) || !Number.isFinite(fix.longitude) || !Number.isFinite(fix.at)) return false;
  if (fix.accuracyMeters !== null && !(fix.accuracyMeters <= T.maxFixAccuracyMeters)) return false;
  if (now - fix.at > T.maxFixAgeMs) return false;
  if (state.lastFixAt !== null && fix.at < state.lastFixAt) return false;
  return true;
}

/**
 * Boarding detected for `ride` (design: after reaching the stop or within 60 m of it,
 * from 1 minute before the scheduled departure, the fix is more than 120 m from the
 * stop and within 80 m of the ride geometry). Also requires the fix to be ahead of the
 * stop along the ride, so walking away the other way does not count.
 */
function boarded(ride: NavStep, line: readonly Position[] | null, fix: Fix, nearBoarding: boolean): boolean {
  if (!nearBoarding || !line || !ride.from) return false;
  if (fix.at < Date.parse(ride.scheduledDeparture) - T.boardingWindowBeforeDepartureMs) return false;
  if (haversineMeters(point(fix), ride.from) <= T.boardingAwayFromStopMeters) return false;
  const here = projectOntoLine(point(fix), line);
  const stop = projectOntoLine(ride.from, line);
  if (!here || !stop || here.distanceMeters > T.boardingOnRideGeometryMeters) return false;
  return here.alongMeters > stop.alongMeters;
}

/** Track nearness to the boarding stop of `ride` while walking to it or waiting at it. */
function approach(state: NavState, ride: NavStep, fix: Fix, walking: boolean): NavState {
  if (!ride.from) return state;
  const d = haversineMeters(point(fix), ride.from);
  const nearBoarding = state.nearBoarding || d <= T.boardingNearStopMeters;
  const phase = walking && d <= T.atStopMeters ? "waiting" : state.phase;
  return nearBoarding === state.nearBoarding && phase === state.phase ? state : { ...state, nearBoarding, phase };
}

/** Ride progress: calls passed (never undone), cues, and exit reached. */
function ride(state: NavState, ctx: NavContext, fix: Fix, effects: NavEffect[]): NavState {
  const step = ctx.steps[state.stepIndex]!;
  const line = lineOf(ctx.journey, step);
  const here = point(fix);
  const exitOrdinal = step.ride?.exitOrdinal ?? null;
  const boardOrdinal = step.ride?.boardOrdinal ?? null;
  let next = state;

  // Calls are projected in ordinal order, each no earlier than the one before, so a
  // looping route keeps every call on its own pass.
  let exitAlong: number | null = null;
  let fixAlong: number | null = null;
  if (line) {
    const boardAlong = step.from ? (projectOntoLine(step.from, line)?.alongMeters ?? 0) : 0;
    const known = [...(ctx.callPositions?.[state.stepIndex] ?? [])]
      .filter((c) => exitOrdinal !== null && boardOrdinal !== null && c.ordinal >= boardOrdinal && c.ordinal < exitOrdinal)
      .sort((a, b) => a.ordinal - b.ordinal);
    let floor = boardAlong;
    const callAlong = known.map((call) => {
      const along = projectOntoLine(call, line, { minAlongMeters: floor })?.alongMeters ?? floor;
      floor = along;
      return { ordinal: call.ordinal, along };
    });
    exitAlong = projectOntoLine(step.target, line, { minAlongMeters: floor })?.alongMeters ?? null;

    // The fix is projected beyond the last call already passed (or the boarding stop).
    const left = state.stopsLeft;
    const passedOrdinal = exitOrdinal !== null && left !== null ? exitOrdinal - left : null;
    const passedAlong = callAlong.filter((c) => passedOrdinal !== null && c.ordinal <= passedOrdinal).at(-1)?.along ?? boardAlong;
    const projection = projectOntoLine(here, line, { minAlongMeters: passedAlong });
    if (projection && projection.distanceMeters <= T.rideCorridorMeters) {
      fixAlong = projection.alongMeters;
      if (exitOrdinal !== null && left !== null) {
        let newLeft = left;
        for (const call of callAlong) {
          if (call.ordinal > exitOrdinal - left && fixAlong > call.along) newLeft = Math.min(newLeft, exitOrdinal - call.ordinal);
        }
        if (newLeft < left) {
          next = { ...next, stopsLeft: newLeft };
          if (newLeft <= 1 && next.cue !== "next_stop") {
            next = { ...next, cue: "next_stop", phase: "cue_next" };
            effects.push({ type: "cue", cue: "next_stop", stepIndex: state.stepIndex });
          } else if (newLeft === 2 && next.cue === "none") {
            next = { ...next, cue: "two_stops", phase: "cue_two" };
            effects.push({ type: "cue", cue: "two_stops", stepIndex: state.stepIndex });
          }
        }
      }
    }
  }

  const atExit = haversineMeters(here, step.target) <= T.exitReachedMeters;
  const notBehind = exitAlong === null || fixAlong === null || fixAlong >= exitAlong - T.exitBehindToleranceMeters;
  if (atExit && notBehind && state.stepIndex + 1 < ctx.steps.length) {
    return moveTo(next, ctx, state.stepIndex + 1, "auto", effects, fix);
  }
  return next;
}

function moveTo(state: NavState, ctx: NavContext, index: number, reason: "auto" | "manual", effects: NavEffect[], fix?: Fix): NavState {
  const from = state.stepIndex;
  let next = enter(state, ctx.steps, index, rideEntry(ctx.steps, index));
  effects.push({ type: "step_changed", stepIndex: index, from, reason });
  const step = ctx.steps[index]!;
  if (step.kind === "arrive") {
    effects.push({ type: "arrived" });
    return next;
  }
  // The fix that ended the previous step may already put the passenger at the next
  // boarding stop (a transfer at the same stop): proximity only, never another advance.
  if (fix && reason === "auto") {
    const following = ctx.steps[index + 1];
    if (isWalk(step) && following?.kind === "ride") next = approach(next, following, fix, true);
    if (step.kind === "ride" && next.phase === "waiting") next = approach(next, step, fix, false);
  }
  return next;
}

function onFix(state: NavState, ctx: NavContext, fix: Fix): NavResult {
  if (!acceptable(state, fix, ctx.now)) return { state, effects: [] };
  const effects: NavEffect[] = [];
  let next: NavState = { ...state, lastFixAt: fix.at, locationLost: false };
  const step = ctx.steps[next.stepIndex];
  if (!step) return { state: next, effects };

  if (step.kind === "walk_to_destination") {
    if (haversineMeters(point(fix), step.target) <= T.destinationReachedMeters) {
      next = moveTo(next, ctx, next.stepIndex + 1, "auto", effects);
    }
  } else if (step.kind === "walk_to_stop" || step.kind === "transfer_walk") {
    const following = ctx.steps[next.stepIndex + 1];
    if (following?.kind === "ride") {
      next = approach(next, following, fix, true);
      if (boarded(following, lineOf(ctx.journey, following), fix, next.nearBoarding)) {
        next = moveTo(next, ctx, next.stepIndex + 1, "auto", effects);
        next = ride({ ...next, phase: "riding" }, ctx, fix, effects);
      }
    }
  } else if (step.kind === "ride") {
    if (next.phase === "waiting") {
      next = approach(next, step, fix, false);
      if (boarded(step, lineOf(ctx.journey, step), fix, next.nearBoarding)) {
        next = ride({ ...next, phase: "riding", nearBoarding: false }, ctx, fix, effects);
      }
    } else {
      next = ride(next, ctx, fix, effects);
    }
  }
  return { state: next, effects };
}

/** Advance the navigation state by one event. */
export function advance(state: NavState, event: NavEvent, ctx: NavContext): NavResult {
  switch (event.type) {
    case "fix":
      return onFix(state, ctx, event.fix);
    case "tick": {
      if (state.locationMode !== "auto" || state.locationLost || state.phase === "arrived") return { state, effects: [] };
      const since = Math.max(state.lastFixAt ?? -Infinity, state.autoSince ?? -Infinity);
      if (!Number.isFinite(since) || ctx.now - since <= T.locationLostAfterMs) return { state, effects: [] };
      return { state: { ...state, locationLost: true }, effects: [] };
    }
    case "next": {
      if (state.stepIndex + 1 >= ctx.steps.length) return { state, effects: [] };
      const effects: NavEffect[] = [];
      return { state: moveTo(state, ctx, state.stepIndex + 1, "manual", effects), effects };
    }
    case "jump": {
      const index = event.stepIndex;
      if (!Number.isInteger(index) || index < 0 || index >= ctx.steps.length || index === state.stepIndex) {
        return { state, effects: [] };
      }
      const effects: NavEffect[] = [];
      return { state: moveTo(state, ctx, index, "manual", effects), effects };
    }
    case "locationMode": {
      if (event.mode === state.locationMode) return { state, effects: [] };
      return {
        state: { ...state, locationMode: event.mode, locationLost: false, autoSince: event.mode === "auto" ? ctx.now : null },
        effects: [],
      };
    }
  }
}
