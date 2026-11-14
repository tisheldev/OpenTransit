import { QueryClient, useQueries, useQuery } from "@tanstack/react-query";
import { toIsraelIso } from "../lib/time";
import { isRetryable } from "./classify";
import { getLine, getNearbyDepartures, getStatus, getStop, getStopDepartures, getStopLines, listStops, planJourney, searchLines, searchPlaces, type Lang } from "./endpoints";
import { apiFetch } from "./http";
import { encodePathRef } from "./pathRef";
import { ApiFailure, unwrap } from "./result";
import { DeparturesPageSchema, type DeparturesPage, type StopDetail } from "./schemas";
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

// --- lines (contract A2; board 2, 14 November 2026) ----------------------------------

/** Lines asked per search: the first few are shown, the rest behind "N more lines". */
export const LINES_LIMIT = 50;
/** A line number is often one character (user, 14 November 2026: one character searches). */
export const LINES_MIN_CHARS = 1;
const LINE_STALE_MS = 60 * 60_000;

/**
 * Line search by number prefix. `q` is already debounced; `near` (only when the caller
 * already holds a position) ranks nearby lines first and fills `nearestStop`.
 */
export function useLineSearch(q: string, near: { latitude: number; longitude: number } | null, enabled = true) {
  const trimmed = q.trim();
  const nearKey = near ? `${near.latitude.toFixed(3)},${near.longitude.toFixed(3)}` : null;
  return useQuery({
    queryKey: ["lines", trimmed, nearKey] as const,
    queryFn: async ({ signal }) => unwrap(await searchLines({ q: trimmed, near, limit: LINES_LIMIT }, signal)),
    enabled: enabled && trimmed.length >= LINES_MIN_CHARS,
    staleTime: LINE_STALE_MS,
    retry: false,
  });
}

/** One line by key (fixed for a generation). Null keeps it idle. */
export function useLine(lineKey: string | null, near: { latitude: number; longitude: number } | null = null) {
  const nearKey = near ? `${near.latitude.toFixed(3)},${near.longitude.toFixed(3)}` : null;
  return useQuery({
    queryKey: ["line", lineKey ?? "idle", nearKey] as const,
    queryFn: async ({ signal }) => unwrap(await getLine(lineKey!, near, signal)),
    enabled: lineKey !== null,
    staleTime: LINE_STALE_MS,
    retry: false,
  });
}

// --- stops (boards 1 and 7, 11 November 2026: Home's nearby stops, a tapped stop) ------

const roundedPoint = (point: { latitude: number; longitude: number }) =>
  `${point.latitude.toFixed(4)},${point.longitude.toFixed(4)}`;

export const stopKeys = {
  near: (point: string, radius: number, limit: number) => ["stops", "near", point, radius, limit] as const,
  stop: (stopId: string) => ["stop", stopId] as const,
  departures: (stopId: string, limit: number, horizon: number) => ["departures", stopId, limit, horizon] as const,
};

/** A stop's detail is fixed for a generation; departures move on with the clock. */
const STOP_STALE_MS = 60 * 60_000;
export const DEPARTURES_REFRESH_MS = 60_000;

/** Stops around a point, nearest first (Home: the 5-minute walk). Null keeps it idle. */
export function useNearbyStops(
  point: { latitude: number; longitude: number } | null,
  options: { radiusMeters: number; limit: number; enabled?: boolean },
) {
  const key = point ? roundedPoint(point) : "none";
  return useQuery({
    queryKey: stopKeys.near(key, options.radiusMeters, options.limit),
    queryFn: async ({ signal }) =>
      unwrap(await listStops({ near: point!, radiusMeters: options.radiusMeters }, { limit: options.limit }, signal)),
    enabled: point !== null && (options.enabled ?? true),
    staleTime: STOP_STALE_MS,
  });
}

/** One stop with the routes through it (board 7). */
export function useStopDetail(stopId: string | null) {
  return useQuery({
    queryKey: stopId ? stopKeys.stop(stopId) : ["stop", "idle"],
    queryFn: async ({ signal }) => unwrap(await getStop(stopId!, signal)),
    enabled: stopId !== null,
    staleTime: STOP_STALE_MS,
  });
}

export interface DepartureWindow {
  limit: number;
  horizonMinutes: number;
}

function departuresQuery(stopId: string, window: DepartureWindow, enabled: boolean) {
  return {
    queryKey: stopKeys.departures(stopId, window.limit, window.horizonMinutes),
    // "Now" is fixed when the request is made: an explicit Israel time with its offset.
    queryFn: async ({ signal }: { signal?: AbortSignal }) =>
      unwrap(
        await getStopDepartures(
          stopId,
          { from: toIsraelIso(new Date()), horizonMinutes: window.horizonMinutes, limit: window.limit },
          signal,
        ),
      ),
    enabled,
    staleTime: DEPARTURES_REFRESH_MS / 2,
    refetchInterval: DEPARTURES_REFRESH_MS,
  };
}

/** The next departures from one stop, refreshed every minute. Null keeps it idle. */
export function useStopDepartures(stopId: string | null, window: DepartureWindow) {
  return useQuery(departuresQuery(stopId ?? "", window, stopId !== null));
}

export interface StopDepartures {
  data: DeparturesPage["data"] | null;
  isPending: boolean;
  error: Error | null;
}

const departuresData = (results: ReadonlyArray<{ data?: DeparturesPage; isPending: boolean; error: Error | null }>): StopDepartures[] =>
  results.map((result) => ({ data: result.data?.data ?? null, isPending: result.isPending, error: result.error }));

/**
 * The next departures from several stops at once (Home's fallback without the nearby
 * endpoint): each stop's departures and state, as one array that keeps its identity until
 * an answer changes.
 */
export function useStopsDepartures(stopIds: readonly string[], window: DepartureWindow, enabled = true) {
  return useQueries({ queries: stopIds.map((stopId) => departuresQuery(stopId, window, enabled)), combine: departuresData });
}

export interface NearbyWindow {
  radiusMeters: number;
  stops: number;
  perStop: number;
  horizonMinutes: number;
}

/**
 * Board 1 in one request: the stops around a point with each line's next departure,
 * refreshed every minute. Null keeps it idle. An API without the endpoint answers 404:
 * the caller then falls back to the stops list and each stop's departures.
 */
export function useNearbyDepartures(point: { latitude: number; longitude: number } | null, window: NearbyWindow, enabled = true) {
  return useQuery({
    queryKey: ["departures", "nearby", point ? roundedPoint(point) : "none", window.radiusMeters, window.stops, window.perStop, window.horizonMinutes],
    queryFn: async ({ signal }) =>
      unwrap(await getNearbyDepartures({ near: point!, from: toIsraelIso(new Date()), ...window }, signal)),
    enabled: point !== null && enabled,
    staleTime: DEPARTURES_REFRESH_MS / 2,
    refetchInterval: DEPARTURES_REFRESH_MS,
    retry: false,
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

/** Board 7: the lines through a stop with their patterns' stops (fixed for a generation). */
export function useStopLines(stopId: string | null) {
  return useQuery({
    queryKey: stopId ? ["stop", stopId, "lines"] : ["stop", "idle", "lines"],
    queryFn: async ({ signal }) => unwrap(await getStopLines(stopId!, signal)),
    enabled: stopId !== null,
    staleTime: STOP_STALE_MS,
    retry: false,
  });
}

const stopData =(results: ReadonlyArray<{ data?: StopDetail }>) => results.map((result) => result.data?.data ?? null);

/**
 * Stop details for several stops (Home's nearby stops, the calls along a chosen line):
 * each one's data or null, as one array that keeps its identity until an answer changes.
 */
export function useStopDetails(stopIds: readonly string[]) {
  return useQueries({
    queries: stopIds.map((stopId) => ({
      queryKey: stopKeys.stop(stopId),
      queryFn: async ({ signal }: { signal?: AbortSignal }) => unwrap(await getStop(stopId, signal)),
      staleTime: STOP_STALE_MS,
      retry: false,
    })),
    combine: stopData,
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
