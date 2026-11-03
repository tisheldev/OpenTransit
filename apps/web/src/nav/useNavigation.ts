import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { locationSource, type Fix, type LocationError } from "../lib/geolocation";
import { updateActiveTrip, type ActiveTrip } from "./activeTrip";
import { engineCallPositions } from "./callPositions";
import { advance, initialNavState, isNavState, type NavEffect, type NavEvent, type NavState } from "./engine";
import { DEFAULT_SIM_SPEED, isSimulatedFix, simulatedSource } from "./simulatedSource";
import { buildSteps, type NavStep } from "./steps";

// Wiring between the pure engine and the browser (design: Navigation engine): foreground
// location while Navigate is mounted, a clock tick, persistence of the engine state into
// the active trip (never a position), and the simulated source for testing.

/** Clock ticks (location-lost check, countdowns). */
export const TICK_MS = 5_000;
/** Simulated playback starts this long before the step's scheduled start. */
const SIM_LEAD_MS = 60_000;

/** Restore a stored state for these steps; anything else starts at the stored step index. */
export function restoreNavState(trip: ActiveTrip, steps: readonly NavStep[], now: number): NavState {
  const stored = trip.nav;
  let state: NavState;
  if (isNavState(stored, steps)) state = stored;
  else {
    state = initialNavState(steps, now);
    const index = Math.max(0, Math.min(steps.length - 1, Math.trunc(Number(stored?.stepIndex) || 0)));
    if (index !== state.stepIndex) state = advance(state, { type: "jump", stepIndex: index }, { steps, journey: trip.journey, now }).state;
  }
  // Fix times are session-only: a reload starts a fresh location watch.
  return { ...state, locationMode: "auto", lastFixAt: null, locationLost: false, autoSince: now };
}

/** Timetable time to start a simulated replay of `step` from. */
export function simStartFor(steps: readonly NavStep[], index: number): number | null {
  const step = steps[index];
  if (!step || step.kind === "arrive") return null;
  return Date.parse(step.scheduledDeparture) - SIM_LEAD_MS;
}

const persisted = (s: NavState) =>
  `${s.stepIndex}|${s.phase}|${s.stopsLeft}|${s.cue}|${s.locationMode}|${s.locationLost}|${s.nearBoarding}`;

export interface Navigation {
  steps: NavStep[];
  state: NavState;
  /** Latest accepted fix (simulated ones carry `simulated: true`); memory only. */
  fix: Fix | null;
  /** Display clock: the simulated timetable clock while simulating, else the device clock. */
  clock: number;
  locationError: LocationError | null;
  simulated: boolean;
  simSpeed: number;
  setSimulated: (on: boolean) => void;
  setSimSpeed: (speed: number) => void;
  next: () => void;
  jump: (stepIndex: number) => void;
  /** Stop location (Finish, End trip) before the trip is cleared. */
  stop: () => void;
}

export function useNavigation(trip: ActiveTrip, onEffects: (effects: NavEffect[], steps: readonly NavStep[]) => void): Navigation {
  const { journey, trips, startedAt } = trip;
  const steps = useMemo(() => buildSteps(journey, trips), [journey, trips]);
  const callPositions = useMemo(() => engineCallPositions(trip.callPositions), [trip.callPositions]);

  const [state, setState] = useState<NavState>(() => restoreNavState(trip, steps, Date.now()));
  const stateRef = useRef(state);
  const [fix, setFix] = useState<Fix | null>(null);
  const [clock, setClock] = useState(() => Date.now());
  const [locationError, setLocationError] = useState<LocationError | null>(null);
  const [simulated, setSimulatedState] = useState(false);
  const [simSpeed, setSimSpeed] = useState<number>(DEFAULT_SIM_SPEED);
  const [simFrom, setSimFrom] = useState<{ at: number | null; epoch: number }>({ at: null, epoch: 0 });
  const [stopped, setStopped] = useState(false);
  const stopRef = useRef<(() => void) | null>(null);
  const simClock = useRef<number | null>(null);
  const lastPersisted = useRef(persisted(state));

  const ctxRef = useRef({ steps, journey, callPositions });
  const effectsRef = useRef(onEffects);
  const simulatedRef = useRef(simulated);
  useEffect(() => {
    ctxRef.current = { steps, journey, callPositions };
    effectsRef.current = onEffects;
    simulatedRef.current = simulated;
  });

  const commit = useCallback(
    (next: NavState) => {
      if (next === stateRef.current) return;
      stateRef.current = next;
      setState(next);
      const key = persisted(next);
      if (key !== lastPersisted.current) {
        lastPersisted.current = key;
        updateActiveTrip((t) => (t.startedAt === startedAt ? { ...t, nav: next } : t));
      }
    },
    [startedAt],
  );

  const dispatch = useCallback(
    (event: NavEvent, now: number) => {
      const result = advance(stateRef.current, event, { ...ctxRef.current, now });
      commit(result.state);
      if (result.effects.length > 0) {
        effectsRef.current(result.effects, ctxRef.current.steps);
        // A manual change while simulating replays the simulation from the new step.
        const manual = result.effects.find((e) => e.type === "step_changed" && e.reason === "manual");
        if (manual && simulatedRef.current && manual.type === "step_changed") {
          setSimFrom((s) => ({ at: simStartFor(ctxRef.current.steps, manual.stepIndex), epoch: s.epoch + 1 }));
        }
      }
      return result;
    },
    [commit],
  );

  const active = !stopped && state.phase !== "arrived";

  // Location: a foreground watch (or the simulated playback) while navigating.
  useEffect(() => {
    if (!active) return;
    const now = Date.now();
    // A new source starts a new fix timeline (simulated fixes carry timetable times).
    commit({ ...stateRef.current, lastFixAt: null, locationLost: false });
    simClock.current = null;
    const source = simulated
      ? simulatedSource(ctxRef.current.journey, {
          speedUp: simSpeed,
          fromTime: simFrom.at ?? simStartFor(ctxRef.current.steps, stateRef.current.stepIndex),
        })
      : locationSource();
    dispatch({ type: "locationMode", mode: "auto" }, now);
    const stop = source.watch(
      (incoming) => {
        const sim = isSimulatedFix(incoming);
        const at = sim ? incoming.at : Date.now();
        if (sim) {
          simClock.current = incoming.at;
          setClock(incoming.at);
        }
        const result = dispatch({ type: "fix", fix: incoming }, at);
        if (result.state.lastFixAt === incoming.at) setFix(incoming);
      },
      (error) => {
        if (error === "denied" || error === "unsupported") {
          setLocationError(error);
          dispatch({ type: "locationMode", mode: "manual" }, Date.now());
        }
      },
    );
    stopRef.current = stop;
    return () => {
      stop();
      if (stopRef.current === stop) stopRef.current = null;
    };
  }, [active, simulated, simSpeed, simFrom, commit, dispatch]);

  // Clock tick: countdowns and the "no location" hint (nothing advances on the clock).
  useEffect(() => {
    if (stopped) return;
    const id = setInterval(() => {
      const now = simulatedRef.current ? (simClock.current ?? Date.now()) : Date.now();
      if (!simulatedRef.current) setClock(now);
      if (simulatedRef.current && simClock.current === null) return;
      dispatch({ type: "tick" }, now);
    }, TICK_MS);
    return () => clearInterval(id);
  }, [stopped, dispatch]);

  const setSimulated = useCallback((on: boolean) => {
    setFix(null);
    setLocationError(null);
    if (!on) setClock(Date.now());
    setSimFrom((s) => ({ at: null, epoch: s.epoch + 1 }));
    setSimulatedState(on);
  }, []);

  return {
    steps,
    state,
    fix,
    clock,
    locationError,
    simulated,
    simSpeed,
    setSimulated,
    setSimSpeed,
    next: () => dispatch({ type: "next" }, simulated ? (simClock.current ?? Date.now()) : Date.now()),
    jump: (stepIndex) => dispatch({ type: "jump", stepIndex }, simulated ? (simClock.current ?? Date.now()) : Date.now()),
    stop: () => {
      stopRef.current?.();
      stopRef.current = null;
      setStopped(true);
    },
  };
}

/** Keep the screen awake while navigating; re-acquired when the page is shown again. */
export function useWakeLock(active: boolean): void {
  useEffect(() => {
    const wakeLock = typeof navigator === "undefined" ? undefined : navigator.wakeLock;
    if (!active || !wakeLock || typeof wakeLock.request !== "function") return;
    let sentinel: WakeLockSentinel | null = null;
    let cancelled = false;
    const acquire = async () => {
      if (document.visibilityState !== "visible") return;
      try {
        const lock = await wakeLock.request("screen");
        if (cancelled) void lock.release().catch(() => {});
        else sentinel = lock;
      } catch {
        // Refused (battery saver, not visible): navigation works without it.
      }
    };
    const onVisibility = () => {
      if (document.visibilityState === "visible" && (!sentinel || sentinel.released)) void acquire();
    };
    void acquire();
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      cancelled = true;
      document.removeEventListener("visibilitychange", onVisibility);
      void sentinel?.release().catch(() => {});
      sentinel = null;
    };
  }, [active]);
}
