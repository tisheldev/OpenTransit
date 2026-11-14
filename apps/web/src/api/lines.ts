import { planJourney, searchLines } from "./endpoints";
import type { components } from "./generated/openapi";
import type { Result } from "./result";
import type { JourneyRequest, JourneyResponse } from "./types";

// "Ride it" and the line a route belongs to (stops-and-lines contracts A2 and A3, 14
// November 2026). Lines themselves (schemas, getLine, searchLines) are in schemas.ts and
// endpoints.ts.

/**
 * The line a route belongs to (a stop's line, a journey's ride): route items carry no MOT
 * line code, so search the line's number and keep the line whose routes include it. Null
 * when the API lists no such line.
 */
export async function lineKeyForRoute(routeId: string, shortName: string, signal?: AbortSignal): Promise<Result<string | null>> {
  const found = await searchLines({ q: shortName.trim(), limit: 50 }, signal);
  if (!found.ok) return found;
  return { ...found, value: found.value.data.find((line) => line.routeIds.includes(routeId))?.lineKey ?? null };
}

/** A3: the trip to ride, where to board it and where to get off. */
export type PinnedTrip = components["schemas"]["PinnedTrip"];

export type PinnedJourneyRequest = JourneyRequest & { pinnedTrip: PinnedTrip };

/** The walk cannot make the departure: the journey is still returned. */
export const PINNED_TRIP_MISSED_BY_WALK = "PINNED_TRIP_MISSED_BY_WALK";
/** No walk to the board stop within the walking limit: outcome `no_route`, no journey. */
export const PINNED_TRIP_WALK_UNAVAILABLE = "PINNED_TRIP_WALK_UNAVAILABLE";

/** A3: one journey pinned to a trip (a walk to the board stop, then that ride). */
export function planPinnedJourney(request: PinnedJourneyRequest, signal?: AbortSignal): Promise<Result<JourneyResponse>> {
  return planJourney(request, signal);
}
