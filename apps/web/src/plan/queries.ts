import { useQueries, useQuery, type QueryClient } from "@tanstack/react-query";
import { planJourney, getTrip } from "../api/endpoints";
import { unwrap } from "../api/result";
import type { Trip } from "../api/schemas";
import type { JourneyRequest, JourneyResponse } from "../api/types";
import type { Lang } from "../lib/time";
import type { PlanDraft } from "./draft";
import { resolveJourneyRequest, type PlannedRequest, type TimeOverride } from "./journeyQuery";

// Compare's queries (design: Compare, "Data"). Journeys are keyed by the exact request;
// trips by engineTripId and kept for long (a dated trip does not change within a
// generation). TanStack Query passes an AbortSignal, so a superseded request is cancelled.

export const planKeys = {
  request: (draft: PlanDraft, lang: Lang, override: TimeOverride | null, attempt: number) =>
    ["journeyRequest", draft, lang, override, attempt] as const,
  journeys: (request: JourneyRequest) => ["journeys", request] as const,
  trip: (tripRef: string) => ["trip", tripRef] as const,
};

export const TRIP_STALE_MS = 60 * 60_000;

/** SP04 client marks (design: Performance budget), read by the @real test. */
export const MARK_REQUEST = "ot:journeys:request";
export const MARK_PAINTED = "ot:journeys:painted";

/**
 * Build the request for a draft. "My location" is resolved here, when the request is
 * made, and "now" is fixed at that moment; `attempt` forces a fresh resolution.
 */
export function useJourneyRequest(draft: PlanDraft, lang: Lang, override: TimeOverride | null, attempt = 0) {
  return useQuery({
    queryKey: planKeys.request(draft, lang, override, attempt),
    queryFn: () => resolveJourneyRequest(draft, { lang, override }),
    staleTime: Infinity,
    gcTime: 5 * 60_000,
    retry: false,
  });
}

export interface JourneyAnswer {
  response: JourneyResponse;
  /** The request the answer belongs to. */
  sent: JourneyRequest;
}

export async function fetchJourneys(planned: PlannedRequest, signal?: AbortSignal): Promise<JourneyAnswer> {
  globalThis.performance?.mark?.(MARK_REQUEST);
  return { response: unwrap(await planJourney(planned.request, signal)), sent: planned.request };
}

/** Journeys for a built request; null keeps the query idle. Retry is the passenger's. */
export function useJourneys(planned: PlannedRequest | null) {
  return useQuery({
    queryKey: planned ? planKeys.journeys(planned.request) : ["journeys", "idle"],
    queryFn: ({ signal }) => fetchJourneys(planned!, signal),
    enabled: planned !== null,
    staleTime: 2 * 60_000,
    retry: false,
  });
}

async function fetchTrip(tripRef: string, signal?: AbortSignal): Promise<Trip> {
  return unwrap(await getTrip(tripRef, signal));
}

/** One trip detail (route details' stop count and exit). */
export function useTrip(tripRef: string | null) {
  return useQuery({
    queryKey: tripRef ? planKeys.trip(tripRef) : ["trip", "idle"],
    queryFn: ({ signal }) => fetchTrip(tripRef!, signal),
    enabled: tripRef !== null,
    staleTime: TRIP_STALE_MS,
    retry: false,
  });
}

/** Trip details for several legs at once (the selected option's rides). */
export function useTrips(tripRefs: readonly string[], enabled = true) {
  return useQueries({
    queries: tripRefs.map((tripRef) => ({
      queryKey: planKeys.trip(tripRef),
      queryFn: ({ signal }: { signal?: AbortSignal }) => fetchTrip(tripRef, signal),
      enabled,
      staleTime: TRIP_STALE_MS,
      retry: false,
    })),
  });
}

/** Trips already fetched for these refs (Start hands them to the active trip). */
export function cachedTrips(client: QueryClient, tripRefs: readonly string[]): Record<string, Trip["data"]> {
  const trips: Record<string, Trip["data"]> = {};
  for (const ref of tripRefs) {
    const trip = client.getQueryData<Trip>(planKeys.trip(ref));
    if (trip) trips[ref] = trip.data;
  }
  return trips;
}
