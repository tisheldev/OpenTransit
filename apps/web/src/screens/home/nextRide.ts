import { useQuery } from "@tanstack/react-query";
import { planJourney } from "../../api/endpoints";
import { unwrap } from "../../api/result";
import type { JourneyRequest, LocationInput } from "../../api/types";
import { toIsraelIso, type Lang } from "../../lib/time";
import { haversineMeters } from "../../nav/geo";
import type { SavedPlace } from "../../storage/local";

// The next departure toward a saved place (board 1: "בית · R1 בעוד 4 דק׳"): one cheap
// journey request (a single result) from where the passenger is, or from the last start
// they chose, and its first ride. Quietly absent when it cannot be known or fails.

export interface NextRide {
  mode: string;
  label: string;
  operatorId: string | null;
  operatorName: string | null;
  /** When that ride leaves its stop. */
  departure: string;
}

export interface RideOrigin {
  latitude: number;
  longitude: number;
  stopId: string | null;
}

/** Closer than this, the passenger is already there: no next ride to show. */
const ALREADY_THERE_METERS = 250;
const NEXT_RIDE_STALE_MS = 2 * 60_000;

const input = (point: { latitude: number; longitude: number; stopId: string | null }): LocationInput =>
  point.stopId ? { kind: "stop", stopId: point.stopId } : { kind: "coordinate", latitude: point.latitude, longitude: point.longitude };

export function nextRideRequest(origin: RideOrigin, place: SavedPlace, lang: Lang, now: Date = new Date()): JourneyRequest {
  return { from: input(origin), to: input(place), departAt: toIsraelIso(now), results: 1, lang };
}

export async function fetchNextRide(request: JourneyRequest, trainLabel: string, signal?: AbortSignal): Promise<NextRide | null> {
  const answer = unwrap(await planJourney(request, signal));
  const ride = answer.data.journeys[0]?.legs.find((leg) => leg.kind === "transit" && leg.transit);
  if (!ride?.transit) return null;
  return {
    mode: ride.mode,
    label: ride.transit.routeShortName.trim() || trainLabel,
    operatorId: ride.transit.operatorId,
    operatorName: ride.transit.operatorName,
    departure: ride.timing.scheduledDeparture,
  };
}

const rounded = (value: number) => value.toFixed(3);

export function useNextRide(place: SavedPlace | null, origin: RideOrigin | null, lang: Lang, trainLabel: string, enabled: boolean) {
  const usable =
    enabled && place !== null && origin !== null && haversineMeters(origin, place) > ALREADY_THERE_METERS;
  return useQuery({
    queryKey: [
      "nextRide",
      place ? `${rounded(place.latitude)},${rounded(place.longitude)}` : null,
      origin ? `${rounded(origin.latitude)},${rounded(origin.longitude)}` : null,
      lang,
    ],
    queryFn: ({ signal }) => fetchNextRide(nextRideRequest(origin!, place!, lang), trainLabel, signal),
    enabled: usable,
    staleTime: NEXT_RIDE_STALE_MS,
    refetchInterval: NEXT_RIDE_STALE_MS,
    retry: false,
  });
}
