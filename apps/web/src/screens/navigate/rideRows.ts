import type { CallPosition, NavState } from "../../nav/engine";
import type { NavStep, TripDetail } from "../../nav/steps";

// On board (board 5, 11 November 2026): how many stops are left and the stops themselves,
// from real data only. Sources, best first: the trip detail (every call's time; a name and
// position per call from API PR #35), the journey's own `intermediateStops` (PR #35), and,
// on older APIs, the names the journey gives (boarding stop, exit) plus the stops fetched
// at Start for the two calls before each exit. Calls without a name are one row with their
// count, never a made-up name. Pure.

export type StopRowKind = "here" | "stop" | "between" | "exit";

export interface StopRow {
  key: string;
  kind: StopRowKind;
  /** Scheduled time at the stop (ISO); null for the collapsed "N stops" row. */
  time: string | null;
  /** The stop's name; null when the API gave none (the row says "you are here" or the count). */
  name: string | null;
  /** For "between": how many unnamed stops the row stands for. */
  count?: number;
}

export interface RideRemaining {
  /** Stops still to come, the exit included; null without trip detail or intermediate stops. */
  left: number | null;
  /** From location fixes (the engine passed calls); otherwise from the timetable and the clock. */
  measured: boolean;
  /** The trip ordinal of the last call passed (where the passenger is); null without trip detail. */
  passed: number | null;
  rows: StopRow[];
}

interface Call {
  ordinal: number;
  departure: string | null;
  arrival: string | null;
  name: string | null;
}

/** Stops between here and the exit listed by name before the middle ones collapse to a count. */
const MAX_NAMED_BETWEEN = 2;

const named = (value: unknown): string | null => (typeof value === "string" && value.trim() ? value.trim() : null);

/** The ride's calls from boarding to exit, from the trip detail or the journey's own stops. */
function callsOf(step: NavStep, trip: TripDetail | undefined, positions: readonly CallPosition[] | undefined): { calls: Call[]; fromTrip: boolean } | null {
  const ride = step.ride!;
  const between = ride.intermediateStops ?? null;
  const byStop = new Map((between ?? []).flatMap((stop) => (stop.stopId ? [[stop.stopId, stop.name] as const] : [])));
  if (trip && ride.boardOrdinal !== null && ride.exitOrdinal !== null && ride.exitOrdinal > ride.boardOrdinal) {
    const fetched = new Map((positions ?? []).flatMap((p) => (p.name ? [[p.ordinal, p.name] as const] : [])));
    const calls = trip.calls
      .filter((call) => call.ordinal >= ride.boardOrdinal! && call.ordinal <= ride.exitOrdinal!)
      .sort((a, b) => a.ordinal - b.ordinal)
      .map((call) => ({
        ordinal: call.ordinal,
        departure: call.scheduledDeparture ?? call.scheduledArrival,
        arrival: call.scheduledArrival ?? call.scheduledDeparture,
        name:
          call.ordinal === ride.boardOrdinal
            ? (step.from?.name ?? null)
            : call.ordinal === ride.exitOrdinal
              ? step.target.name
              : (named((call as { name?: unknown }).name) ?? byStop.get(call.stopId) ?? fetched.get(call.ordinal) ?? null),
      }));
    return { calls, fromTrip: true };
  }
  if (between && step.from) {
    const calls: Call[] = [
      { ordinal: 0, departure: step.scheduledDeparture, arrival: step.scheduledDeparture, name: step.from.name },
      ...between.map((stop, i) => ({
        ordinal: i + 1,
        departure: stop.scheduledDeparture ?? stop.scheduledArrival,
        arrival: stop.scheduledArrival ?? stop.scheduledDeparture,
        name: stop.name,
      })),
      { ordinal: between.length + 1, departure: step.scheduledArrival, arrival: step.scheduledArrival, name: step.target.name },
    ];
    return { calls, fromTrip: false };
  }
  return null;
}

export function rideRemaining(
  step: NavStep,
  state: NavState,
  trip: TripDetail | undefined,
  positions: readonly CallPosition[] | undefined,
  clock: number,
): RideRemaining {
  const found = step.ride ? callsOf(step, trip, positions) : null;
  if (!found || found.calls.length < 2) {
    // Neither source: the two stops the journey names, with their times; no position.
    const rows: StopRow[] = [];
    if (step.from) rows.push({ key: "board", kind: "stop", time: step.scheduledDeparture, name: step.from.name });
    rows.push({ key: "exit", kind: "exit", time: step.scheduledArrival, name: step.target.name });
    return { left: null, measured: false, passed: null, rows };
  }
  const { calls, fromTrip } = found;
  const board = calls[0]!.ordinal;
  const exit = calls[calls.length - 1]!.ordinal;

  // The last call passed: measured by the engine once a fix passed a call, otherwise the
  // last call whose scheduled departure is not after the clock (the boarding stop at first).
  const left = fromTrip && state.stepIndex === step.index ? state.stopsLeft : null;
  let passed = board;
  let measured = false;
  if (left !== null && left < exit - board) {
    passed = exit - left;
    measured = true;
  } else {
    for (const call of calls) {
      if (call.ordinal <= board || call.ordinal >= exit) continue;
      const at = Date.parse(call.departure ?? "");
      if (Number.isFinite(at) && at <= clock) passed = Math.max(passed, call.ordinal);
    }
  }

  const rows: StopRow[] = [];
  const here = calls.find((call) => call.ordinal === passed);
  rows.push({ key: `here-${passed}`, kind: "here", time: here?.departure ?? null, name: here?.name ?? null });
  let unnamed: Call[] = [];
  const flush = () => {
    if (unnamed.length === 0) return;
    rows.push({ key: `between-${unnamed[0]!.ordinal}`, kind: "between", time: null, name: null, count: unnamed.length });
    unnamed = [];
  };
  // The panel stays short (board 5): beyond two, only the next stop and the one before
  // the exit are named; the stops between them are one row with their count.
  const middle = calls.filter((call) => call.ordinal > passed && call.ordinal < exit);
  const shown = middle.length <= MAX_NAMED_BETWEEN ? middle : [middle[0]!, middle[middle.length - 1]!];
  for (const call of middle) {
    if (!call.name || !shown.includes(call)) {
      unnamed.push(call);
      continue;
    }
    flush();
    rows.push({ key: `stop-${call.ordinal}`, kind: "stop", time: call.arrival, name: call.name });
  }
  flush();
  const last = calls[calls.length - 1]!;
  rows.push({ key: "exit", kind: "exit", time: last.arrival ?? step.scheduledArrival, name: step.target.name });
  return { left: exit - passed, measured, passed: fromTrip ? passed : null, rows };
}
