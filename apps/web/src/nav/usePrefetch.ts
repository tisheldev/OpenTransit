import { useEffect } from "react";
import { getStop, getTrip } from "../api/endpoints";
import { getActiveTrip, updateActiveTrip, type ActiveTrip } from "./activeTrip";
import { callTargets, fetchCallPositions, fetchTrips, missingTrips, type GetStop, type GetTrip } from "./callPositions";
import { buildSteps } from "./steps";

// At Start (first Navigate mount for a trip), in the background: trip details missing
// for a ride (requested once), then call positions for cues. Results are stored in the
// active trip, so a reload repeats no request; failures only disable cues for that ride.

export interface PrefetchApi {
  getStop: GetStop;
  getTrip: GetTrip;
}

const defaultApi: PrefetchApi = { getStop, getTrip };
const running = new Map<string, AbortController>();

function current(startedAt: string): ActiveTrip | null {
  const trip = getActiveTrip();
  return trip && trip.startedAt === startedAt ? trip : null;
}

function updateSame(startedAt: string, change: (trip: ActiveTrip) => ActiveTrip): void {
  updateActiveTrip((trip) => (trip.startedAt === startedAt ? change(trip) : trip));
}

export async function prefetchForTrip(startedAt: string, api: PrefetchApi, signal: AbortSignal): Promise<void> {
  let trip = current(startedAt);
  if (!trip) return;
  const missing = missingTrips(trip.journey, trip.trips, trip.tripsRequested);
  if (missing.length > 0) {
    const { trips, settled } = await fetchTrips(missing, api.getTrip, { signal });
    if (signal.aborted) return;
    updateSame(startedAt, (t) => ({
      ...t,
      trips: { ...t.trips, ...trips },
      tripsRequested: [...new Set([...(t.tripsRequested ?? []), ...settled])],
    }));
  }
  trip = current(startedAt);
  if (!trip) return;
  const stored = trip.callPositions ?? {};
  const targets = Object.fromEntries(
    Object.entries(callTargets(buildSteps(trip.journey, trip.trips), trip.trips)).filter(([index]) => !(index in stored)),
  );
  if (Object.keys(targets).length === 0) return;
  const entries = await fetchCallPositions(targets, api.getStop, { signal });
  if (signal.aborted || Object.keys(entries).length === 0) return;
  updateSame(startedAt, (t) => ({ ...t, callPositions: { ...(t.callPositions ?? {}), ...entries } }));
}

/** Run the prefetch once per trip while Navigate is mounted (aborted on unmount). */
export function useTripPrefetch(startedAt: string | null, api: PrefetchApi = defaultApi): void {
  useEffect(() => {
    if (!startedAt || running.has(startedAt)) return;
    const controller = new AbortController();
    running.set(startedAt, controller);
    void prefetchForTrip(startedAt, api, controller.signal).finally(() => {
      if (running.get(startedAt) === controller) running.delete(startedAt);
    });
    return () => {
      controller.abort();
      if (running.get(startedAt) === controller) running.delete(startedAt);
    };
  }, [startedAt, api]);
}
