import { useMemo } from "react";
import { useNearbyDepartures, useNearbyStops, useStopDetails, useStopsDepartures } from "../../api/queries";
import { ApiFailure } from "../../api/result";
import type { StopDetail } from "../../api/schemas";
import type { Departure } from "../stop/lines";

// The stops around Home's centre with each one's next departures (board 1). One request to
// /v1/departures/nearby (API PR #35); an API without it answers 404, and Home then reads
// the stops list and each stop's departures instead (one request per stop).

/** A 5-minute walk at about 80 m a minute. */
export const WALK_RING_METERS = 400;
/** Stops drawn as pins around the passenger. */
export const NEAR_STOPS = 4;
/** Departure rows under the selected stop (one per line and direction). */
export const HOME_ROWS = 4;
const HORIZON_MINUTES = 60;

export interface NearStop {
  stopId: string;
  name: string | null;
  code: string | null;
  latitude: number;
  longitude: number;
}

export type StopDeparturesState = "pending" | "ready" | "unavailable" | "error";

export interface HomeStops {
  /** The stops list itself: pending, failed, or read. */
  pending: boolean;
  error: unknown;
  refetch: () => void;
  stops: NearStop[];
  /** Per stop: its departures (each line's earliest first), or null until known. */
  departures: Array<Departure[] | null>;
  states: StopDeparturesState[];
  /** Per stop, a departure that failed to load (for its error message). */
  errors: unknown[];
  /** Per stop, the routes through it (operators of departures that do not carry theirs). */
  routes: Array<StopDetail["data"]["routes"]>;
}

const notFound = (error: unknown) => error instanceof ApiFailure && error.state === "not_found";

export function useHomeStops(centre: { latitude: number; longitude: number }, enabled: boolean): HomeStops {
  const nearby = useNearbyDepartures(
    centre,
    { radiusMeters: WALK_RING_METERS, stops: NEAR_STOPS, perStop: HOME_ROWS, horizonMinutes: HORIZON_MINUTES },
    enabled,
  );
  const legacy = nearby.isError && notFound(nearby.error);

  const list = useNearbyStops(centre, { radiusMeters: WALK_RING_METERS, limit: NEAR_STOPS, enabled: enabled && legacy });
  const legacyStops = useMemo(() => (list.data?.data ?? []).slice(0, NEAR_STOPS), [list.data]);
  const legacyIds = useMemo(() => legacyStops.map((stop) => stop.stopId), [legacyStops]);
  const legacyDepartures = useStopsDepartures(legacyIds, { limit: 12, horizonMinutes: HORIZON_MINUTES }, enabled && legacy);
  const details = useStopDetails(legacyIds);

  const fromNearby = useMemo<HomeStops | null>(() => {
    if (legacy) return null;
    const entries = (nearby.data?.data ?? []).slice(0, NEAR_STOPS);
    return {
      pending: nearby.isPending,
      error: nearby.isError ? nearby.error : null,
      refetch: nearby.refetch as () => void,
      stops: entries.map((entry) => entry.stop),
      departures: entries.map((entry) => (entry.departuresState === "available" ? (entry.departures ?? []) : null)),
      states: entries.map((entry) => (entry.departuresState === "available" ? "ready" : "unavailable")),
      errors: entries.map(() => null),
      routes: entries.map(() => []),
    };
  }, [legacy, nearby.data, nearby.isPending, nearby.isError, nearby.error, nearby.refetch]);

  const fromLists = useMemo<HomeStops | null>(() => {
    if (!legacy) return null;
    return {
      pending: list.isPending,
      error: list.isError ? list.error : null,
      refetch: list.refetch as () => void,
      stops: legacyStops,
      departures: legacyStops.map((_, index) => legacyDepartures[index]?.data ?? null),
      states: legacyStops.map((_, index) => {
        const query = legacyDepartures[index];
        if (!query || query.isPending) return "pending";
        return query.error ? "error" : "ready";
      }),
      errors: legacyStops.map((_, index) => legacyDepartures[index]?.error ?? null),
      routes: legacyStops.map((_, index) => details[index]?.routes ?? []),
    };
  }, [legacy, list.isPending, list.isError, list.error, list.refetch, legacyStops, legacyDepartures, details]);

  return (fromNearby ?? fromLists)!;
}
