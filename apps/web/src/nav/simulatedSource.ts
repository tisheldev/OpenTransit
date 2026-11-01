import type { Journey } from "../api/types";
import type { Fix, LocationSource } from "../lib/geolocation";
import { simulateJourney, type SimulatedFix, type SimulateOptions } from "./simulate";

// SIMULATED location source (testing tool): plays `simulateJourney` back in real time,
// sped up. Every fix it emits carries `simulated: true` and the timetable clock in `at`,
// so the caller passes `now = fix.at` to the engine. Never presented as a real fix.

/** Speed-ups offered on the Navigate screen. */
export const SIM_SPEEDS = [10, 30, 120, 600] as const;
export const DEFAULT_SIM_SPEED = 30;

/** How often playback checks for due fixes (real milliseconds). */
const PLAYBACK_TICK_MS = 50;

export function isSimulatedFix(fix: Fix): fix is SimulatedFix {
  return (fix as Partial<SimulatedFix>).simulated === true;
}

export interface SimulatedSourceOptions extends Omit<SimulateOptions, "speedUp"> {
  speedUp?: number;
  /** Start playback at this timetable time (epoch ms): earlier fixes are skipped. */
  fromTime?: number | null;
}

export function simulatedSource(journey: Journey, options: SimulatedSourceOptions = {}): LocationSource {
  const speedUp = options.speedUp ?? DEFAULT_SIM_SPEED;
  const all = simulateJourney(journey, { ...options, speedUp });
  const from = options.fromTime ?? null;
  const fixes = from === null ? all : all.filter((fix) => fix.at >= from);
  return {
    current() {
      const first = fixes[0];
      return Promise.resolve(first ? { ok: true as const, fix: first } : { ok: false as const, error: "unavailable" as const });
    },
    watch(onFix, onError) {
      if (fixes.length === 0) {
        onError("unavailable");
        return () => {};
      }
      const base = fixes[0]!.offsetMs;
      const started = Date.now();
      let next = 0;
      let timer: ReturnType<typeof setTimeout> | null = null;
      let stopped = false;
      const play = () => {
        timer = null;
        const elapsed = Date.now() - started;
        while (!stopped && next < fixes.length && fixes[next]!.offsetMs - base <= elapsed) onFix(fixes[next++]!);
        if (!stopped && next < fixes.length) timer = setTimeout(play, PLAYBACK_TICK_MS);
      };
      play();
      return () => {
        stopped = true;
        if (timer !== null) clearTimeout(timer);
      };
    },
  };
}
