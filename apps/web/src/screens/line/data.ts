import { keepPreviousData, useQuery, type QueryClient } from "@tanstack/react-query";
import { getRoutePatterns } from "../../api/endpoints";
import { apiFetch } from "../../api/http";
import { getLine, lineKeyForRoute } from "../../api/lines";
import { encodePathRef } from "../../api/pathRef";
import { unwrap } from "../../api/result";
import { DeparturesPageSchema, StopLinesSchema, StopsPageSchema } from "../../api/schemas";
import { toIsraelIso } from "../../lib/time";

// The Line screen's reads (board 4; client design, "What the API has and lacks": the line,
// then a stop's lines with every pattern, its departures by route, the next trip). Fixed
// for a generation except departures, which move on with the clock.

const GENERATION_MS = 60 * 60_000;
const DEPARTURES_REFRESH_MS = 60_000;

/** A2: one line by its key. */
export function useLine(lineKey: string) {
  return useQuery({
    queryKey: ["line", lineKey],
    queryFn: async ({ signal }) => unwrap(await getLine(lineKey, null, signal)),
    staleTime: GENERATION_MS,
    retry: false,
  });
}

/** The first stop of a route's first pattern: where to read the line's patterns from when no stop was given. */
export function useRouteFirstStop(routeId: string | null) {
  return useQuery({
    queryKey: ["route", routeId, "firstStop"],
    queryFn: async ({ signal }) => {
      const page = unwrap(await getRoutePatterns(routeId!, { limit: 1 }, signal));
      return page.data[0]?.stops[0]?.stopId ?? null;
    },
    enabled: routeId !== null,
    staleTime: GENERATION_MS,
    retry: false,
  });
}

/** Every line through a stop with all its patterns (both directions, names and positions). */
export function useStopLinesAll(stopId: string | null) {
  return useQuery({
    queryKey: ["stop", stopId, "lines", "all"],
    queryFn: async ({ signal }) => {
      const encoded = encodePathRef(stopId!);
      if (!encoded.ok) throw new Error("unroutable stop");
      return unwrap(await apiFetch({ path: `/v1/stops/${encoded.segment}/lines`, query: { patterns: "all", limit: 50 }, signal }, StopLinesSchema));
    },
    enabled: stopId !== null,
    staleTime: GENERATION_MS,
    retry: false,
  });
}

/**
 * The next departures of one route from one stop (the line's highlighted stop, Ride it's
 * board stop), refreshed every minute; "now" is fixed when each request is made. The
 * previous answer stays on screen while a new stop or route loads.
 */
export function useRouteDepartures(stopId: string | null, routeId: string | null, horizonMinutes = 120, limit = 12) {
  return useQuery({
    queryKey: ["routeDepartures", stopId, routeId, horizonMinutes, limit],
    queryFn: async ({ signal }) => {
      const encoded = encodePathRef(stopId!);
      if (!encoded.ok) throw new Error("unroutable stop");
      const query = { from: toIsraelIso(new Date()), horizonMinutes, limit, routeId };
      return unwrap(await apiFetch({ path: `/v1/stops/${encoded.segment}/departures`, query, signal }, DeparturesPageSchema));
    },
    enabled: stopId !== null && routeId !== null,
    staleTime: DEPARTURES_REFRESH_MS / 2,
    refetchInterval: DEPARTURES_REFRESH_MS,
    placeholderData: keepPreviousData,
    retry: false,
  });
}

/** A1: train and light-rail stations around a line (for the train badge). Failure just means no badges. */
export function useRailStations(bounds: { west: number; south: number; east: number; north: number } | null) {
  const bbox = bounds ? [bounds.west, bounds.south, bounds.east, bounds.north].map((value) => value.toFixed(4)).join(",") : null;
  return useQuery({
    queryKey: ["stations", bbox],
    queryFn: async ({ signal }) =>
      unwrap(await apiFetch({ path: "/v1/stops", query: { bbox, mode: "rail,light_rail", limit: 100 }, signal }, StopsPageSchema)),
    enabled: bbox !== null,
    staleTime: GENERATION_MS,
    retry: false,
  });
}

export const lineKeyQuery = (routeId: string, shortName: string) => ({
  queryKey: ["lineKeyFor", routeId, shortName] as const,
  queryFn: async ({ signal }: { signal?: AbortSignal }) => unwrap(await lineKeyForRoute(routeId, shortName, signal)),
  staleTime: GENERATION_MS,
  retry: false,
});

/** The line a route belongs to (a stop's line, a journey's ride); idle until asked. */
export function useLineKeyFor(routeId: string | null, shortName: string | null, enabled = true) {
  return useQuery({ ...lineKeyQuery(routeId ?? "", shortName ?? ""), enabled: enabled && !!routeId && !!shortName });
}

export function fetchLineKey(client: QueryClient, routeId: string, shortName: string): Promise<string | null> {
  return client.fetchQuery(lineKeyQuery(routeId, shortName));
}
