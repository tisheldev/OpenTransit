import { QueryClient, useQuery } from "@tanstack/react-query";
import { isRetryable } from "./classify";
import { getStatus, searchPlaces, type Lang } from "./endpoints";
import { ApiFailure, unwrap } from "./result";

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
