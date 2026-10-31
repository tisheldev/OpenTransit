import type { Result } from "../api/result";
import type { StopDetail, Trip } from "../api/schemas";
import type { Journey } from "../api/types";
import type { StoredCallPositions } from "./activeTrip";
import type { CallPosition } from "./engine";
import type { NavStep, TripDetail } from "./steps";

// Data Navigate fetches once at Start (contract): a trip detail not yet fetched for a
// ride, then the positions of at most the two calls before each ride's exit (cue
// stand-in until API-C1 puts coordinates in the trip). Callers inject the fetchers, so
// the planning and the concurrency are testable and the @real spec can reuse them.

/** At most this many calls before each exit are fetched. */
export const CALLS_BEFORE_EXIT = 2;
/** Requests in flight at once. */
export const PREFETCH_CONCURRENCY = 2;

export interface CallTarget {
  ordinal: number;
  stopId: string;
}

/** Per ride step index: the calls whose positions the cues need. */
export function callTargets(steps: readonly NavStep[], trips: Readonly<Record<string, TripDetail>>): Record<number, CallTarget[]> {
  const out: Record<number, CallTarget[]> = {};
  for (const step of steps) {
    const ride = step.ride;
    if (!ride || ride.boardOrdinal === null || ride.exitOrdinal === null) continue;
    const trip = trips[ride.tripRef];
    if (!trip) continue;
    const low = Math.max(ride.boardOrdinal, ride.exitOrdinal - CALLS_BEFORE_EXIT);
    const calls = trip.calls
      .filter((call) => call.ordinal >= low && call.ordinal < ride.exitOrdinal!)
      .map((call) => ({ ordinal: call.ordinal, stopId: call.stopId }));
    if (calls.length > 0) out[step.index] = calls;
  }
  return out;
}

/** Trip refs of the journey's rides without a detail that were never requested. */
export function missingTrips(journey: Journey, trips: Readonly<Record<string, TripDetail>>, requested: readonly string[] = []): string[] {
  const refs = journey.legs.flatMap((leg) => (leg.kind === "transit" && leg.transit ? [leg.transit.engineTripId] : []));
  return [...new Set(refs)].filter((ref) => !trips[ref] && !requested.includes(ref));
}

/** Run `tasks` with at most `limit` in flight; results in input order. */
export async function runPool<T>(tasks: ReadonlyArray<() => Promise<T>>, limit = PREFETCH_CONCURRENCY): Promise<T[]> {
  const results = new Array<T>(tasks.length);
  let next = 0;
  const worker = async () => {
    while (next < tasks.length) {
      const index = next++;
      results[index] = await tasks[index]!();
    }
  };
  await Promise.all(Array.from({ length: Math.min(limit, tasks.length) }, worker));
  return results;
}

export type GetStop = (stopId: string, signal?: AbortSignal) => Promise<Result<StopDetail>>;
export type GetTrip = (tripRef: string, signal?: AbortSignal) => Promise<Result<Trip>>;

export interface FetchOptions {
  signal?: AbortSignal;
  concurrency?: number;
}

/**
 * Fetch each stop once (shared stops are requested once), then one entry per ride step:
 * "ok" when every target stop answered, otherwise "failed" (cues off for that ride).
 * Aborted requests leave their ride out, so it is retried on the next Start or mount.
 */
export async function fetchCallPositions(
  targets: Readonly<Record<number, readonly CallTarget[]>>,
  getStop: GetStop,
  options: FetchOptions = {},
): Promise<Record<string, StoredCallPositions>> {
  const stopIds = [...new Set(Object.values(targets).flatMap((calls) => calls.map((call) => call.stopId)))];
  const answers = await runPool(
    stopIds.map((stopId) => async () => {
      if (options.signal?.aborted) return { stopId, kind: "aborted" as const };
      const result = await getStop(stopId, options.signal).catch(() => null);
      if (options.signal?.aborted || (result && !result.ok && result.error.kind === "aborted")) return { stopId, kind: "aborted" as const };
      if (!result || !result.ok) return { stopId, kind: "failed" as const };
      const { latitude, longitude } = result.value.data;
      return Number.isFinite(latitude) && Number.isFinite(longitude)
        ? { stopId, kind: "ok" as const, latitude, longitude }
        : { stopId, kind: "failed" as const };
    }),
    options.concurrency ?? PREFETCH_CONCURRENCY,
  );
  const byStop = new Map(answers.map((answer) => [answer.stopId, answer]));
  const out: Record<string, StoredCallPositions> = {};
  for (const [stepIndex, calls] of Object.entries(targets)) {
    const found = calls.map((call) => ({ call, answer: byStop.get(call.stopId) }));
    if (found.some(({ answer }) => !answer || answer.kind === "aborted")) continue;
    if (found.some(({ answer }) => answer!.kind !== "ok")) {
      out[stepIndex] = { status: "failed" };
      continue;
    }
    out[stepIndex] = {
      status: "ok",
      positions: found.map(({ call, answer }) => {
        const ok = answer as { latitude: number; longitude: number };
        return { ordinal: call.ordinal, latitude: ok.latitude, longitude: ok.longitude };
      }),
    };
  }
  return out;
}

/**
 * Fetch each missing trip detail. `trips` holds the ones that arrived; `settled` every
 * ref that got an answer (or a non-abort failure), so it is never requested again.
 */
export async function fetchTrips(
  refs: readonly string[],
  getTrip: GetTrip,
  options: FetchOptions = {},
): Promise<{ trips: Record<string, TripDetail>; settled: string[] }> {
  const results = await runPool(
    refs.map((ref) => async () => {
      if (options.signal?.aborted) return { ref, kind: "aborted" as const };
      const result = await getTrip(ref, options.signal).catch(() => null);
      if (options.signal?.aborted || (result && !result.ok && result.error.kind === "aborted")) return { ref, kind: "aborted" as const };
      return result && result.ok ? { ref, kind: "ok" as const, trip: result.value.data } : { ref, kind: "failed" as const };
    }),
    options.concurrency ?? PREFETCH_CONCURRENCY,
  );
  const trips: Record<string, TripDetail> = {};
  const settled: string[] = [];
  for (const result of results) {
    if (result.kind === "aborted") continue;
    settled.push(result.ref);
    if (result.kind === "ok") trips[result.ref] = result.trip;
  }
  return { trips, settled };
}

/** The engine's view: positions per ride step index, for rides whose fetch succeeded. */
export function engineCallPositions(stored: Readonly<Record<string, StoredCallPositions>> | undefined): Record<number, CallPosition[]> {
  const out: Record<number, CallPosition[]> = {};
  for (const [key, entry] of Object.entries(stored ?? {})) {
    if (entry.status === "ok") out[Number(key)] = entry.positions;
  }
  return out;
}
