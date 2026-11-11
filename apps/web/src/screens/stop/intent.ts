import { go } from "../../router";

// Which line to show when a stop opens (Home: a tapped departure row opens its stop with
// that line's route drawn). Routes carry no state (router.ts: no ids beyond the stop's),
// so the choice is held here in memory for the next stop screen; a reload forgets it.

let pending: { stopId: string; lineKey: string | null } | null = null;

/** Open a stop's screen, optionally with one of its lines already chosen. */
export function openStop(stopId: string, lineKey: string | null = null): void {
  pending = { stopId, lineKey };
  go({ name: "stop", stopId });
}

/** The line chosen on the way into this stop, if any (read, not consumed: StrictMode renders twice). */
export function initialLine(stopId: string): string | null {
  return pending?.stopId === stopId ? pending.lineKey : null;
}
