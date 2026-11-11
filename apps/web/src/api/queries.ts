import { QueryClient, useQuery } from "@tanstack/react-query";
import { isRetryable } from "./classify";
import { getStatus, getStopDepartures, planJourney, searchPlaces, type Lang } from "./endpoints";
import { apiFetch } from "./http";
import { encodePathRef } from "./pathRef";
import { ApiFailure, unwrap } from "./result";
import { DeparturesPageSchema } from "./schemas";
import type { JourneyRequest } from "./types";

export const queryKeys = {
  status: ["status"] as const,
  places: (q: string, lang: Lang, near: string | null) => ["places", q, lang, near] as const,
};

export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        // One retry for transient failures; 429 is handled by the screen honouring Retry-After.
        retry: (count, error) =>
          count < 1 && error instanceof ApiFailure && isRetryable(error.state) && error.state !== "rate_limited",
        refetchOnWindowFocus: false,
      },
    },
  });
}

/**
 * Data status for the shell banners and Settings (design: Screens, cached 5 minutes).
 * The shell enables it only after the first paint: Home renders from storage alone.
 */
export function useStatus(options: { enabled?: boolean } = {}) {
  return useQuery({
    queryKey: queryKeys.status,
    queryFn: async ({ signal }) => unwrap(await getStatus(signal)),
    staleTime: 5 * 60_000,
    enabled: options.enabled ?? true,
  });
}

export const PLACES_LIMIT = 10;
export const PLACES_MIN_CHARS = 2;

/**
 * Place search (design: Where to / Where from). `q` is already debounced by the caller;
 * a new key drops the old query, and TanStack aborts its request through `signal`.
 * `near` is sent only when the caller already holds a position.
 */
export function usePlaceSearch(q: string, lang: Lang, near: { latitude: number; longitude: number } | null) {
  const trimmed = q.trim();
  const nearKey = near ? `${near.latitude.toFixed(4)},${near.longitude.toFixed(4)}` : null;
  return useQuery({
    queryKey: queryKeys.places(trimmed, lang, nearKey),
    queryFn: async ({ signal }) =>
      unwrap(await searchPlaces({ q: trimmed, lang, near, limit: PLACES_LIMIT }, signal)),
    enabled: trimmed.length >= PLACES_MIN_CHARS,
    staleTime: 60_000,
  });
}

/**
 * One page of departures from a stop from a fixed instant (Navigate, "Bus didn't come":
 * the next departure of the same route). The caller fixes `from` when the question is
 * asked, so the key does not move with the clock; null keeps the query idle. `routeId`
 * asks the API for that route only (API PR #35); an API without the filter ignores the
 * unknown parameter and answers every route, so callers still filter by route.
 */
export function useDeparturesFrom(
  stopId: string | null,
  from: string | null,
  options: { routeId?: string | null; horizonMinutes?: number; limit?: number } = {},
) {
  const { routeId = null, horizonMinutes = 120, limit = 100 } = options;
  return useQuery({
    queryKey: ["departuresFrom", stopId, from, routeId, horizonMinutes, limit] as const,
    queryFn: async ({ signal }) => {
      const encoded = encodePathRef(stopId!);
      if (!encoded.ok) return unwrap(await getStopDepartures(stopId!, { from: from!, horizonMinutes, limit }, signal));
      const query = { from: from!, horizonMinutes, limit, routeId };
      return unwrap(await apiFetch({ path: `/v1/stops/${encoded.segment}/departures`, query, signal }, DeparturesPageSchema));
    },
    enabled: stopId !== null && from !== null,
    staleTime: 60_000,
    retry: false,
  });
}

/**
 * A journey plan that leaves out some trips (Navigate, "Bus didn't come": the bus that did
 * not come). `excludeTripRefs` is newer (API PR #35); an API without it refuses the field
 * (422 invalid request), so the plan is asked again without it and the caller keeps its
 * own filter. Null keeps the query idle.
 */
export function usePlanExcluding(request: JourneyRequest | null, excludeTripRefs: readonly string[]) {
  return useQuery({
    queryKey: ["planExcluding", request, excludeTripRefs] as const,
    queryFn: async ({ signal }) => {
      if (excludeTripRefs.length > 0) {
        const first = await planJourney({ ...request!, excludeTripRefs: excludeTripRefs.slice(0, 5) } as JourneyRequest, signal);
        const refused = !first.ok && (first.error.kind === "problem" || first.error.kind === "http") && (first.error.status === 400 || first.error.status === 422);
        if (!refused) return unwrap(first);
      }
      return unwrap(await planJourney(request!, signal));
    },
    enabled: request !== null,
    staleTime: 60_000,
    retry: false,
  });
}
