import type { DeparturesPage } from "../../api/schemas";
import type { Journey, JourneyRequest, Leg, LocationInput } from "../../api/types";
import type { Fix } from "../../lib/geolocation";
import { toIsraelIso, type Lang } from "../../lib/time";
import type { NavStep, TripDetail } from "../../nav/steps";

// "Bus didn't come" (board 6, 11 November 2026): the two choices drawn from where the
// passenger stands, both from real answers. Wait here: the next departure of the same
// route at this stop (departures, asked by route where the API can (PR #35) and filtered
// here as well), with its arrival from a plan that boards it, else its arrival at the exit
// stop from that trip. Walk to another stop: the best option of a fresh plan from the
// passenger (or the stop) at the time asked, without the missed trip (excludeTripRefs
// where the API can), whose first ride boards at another stop. Nothing here guesses a
// time: no answer, no choice. Pure.

export type Departure = DeparturesPage["data"][number];

/** The ride that did not come: the current ride while waiting, or the one a walk leads to. */
export function missedRide(steps: readonly NavStep[], index: number, phase: string): NavStep | null {
  const step = steps[index];
  if (!step) return null;
  if (step.kind === "ride") return phase === "waiting" ? step : null;
  if (step.kind === "walk_to_stop" || step.kind === "transfer_walk") {
    const next = steps[index + 1];
    return next?.kind === "ride" && next.from ? next : null;
  }
  return null;
}

/** Same route: by route ID, or by line number when the item carries no route ID. */
function sameRoute(item: Departure, ride: NavStep): boolean {
  const routeId = ride.ride?.routeId ?? null;
  if (item.routeId && routeId) return item.routeId === routeId;
  return item.routeShortName.trim() !== "" && item.routeShortName.trim() === (ride.ride?.routeShortName.trim() ?? "");
}

/** The next departure of the missed ride's route at its stop, after the one that did not come. */
export function nextSameRoute(items: readonly Departure[], ride: NavStep): Departure | null {
  const after = Date.parse(ride.scheduledDeparture);
  const stopId = ride.from?.stopId ?? null;
  const found = items
    .filter((item) => (!stopId || item.stopId === stopId) && sameRoute(item, ride) && item.tripRef !== ride.ride?.tripRef)
    .filter((item) => Date.parse(item.scheduledDeparture) > after)
    .sort((a, b) => Date.parse(a.scheduledDeparture) - Date.parse(b.scheduledDeparture));
  return found[0] ?? null;
}

/**
 * The next departure's arrival at the missed ride's exit stop, read from that trip's calls:
 * the first call at the exit stop after the call that departs here. Null when not there.
 */
export function exitArrival(trip: TripDetail, departure: Departure, ride: NavStep): string | null {
  const exitStop = ride.target.stopId;
  if (!exitStop) return null;
  const here = trip.calls.find((call) => call.callSequence === departure.callSequence) ?? trip.calls.find((call) => call.stopId === departure.stopId);
  if (!here) return null;
  const exit = trip.calls.filter((call) => call.stopId === exitStop && call.ordinal > here.ordinal).sort((a, b) => a.ordinal - b.ordinal)[0];
  return exit ? (exit.scheduledArrival ?? exit.scheduledDeparture) : null;
}

/**
 * Wait here when no plan boards the next departure: the ride leg swapped to that trip
 * (its departure here and its arrival at the same exit, both from the API), followed by a
 * plan from the exit at that arrival (`rest`; null when the ride ends the journey). The
 * leg keeps its drawn line (same route, same stops); its stop list is dropped, since it
 * described the other trip's times.
 */
export function swapRide(journey: Journey, ride: NavStep, departure: Departure, trip: TripDetail, exitAt: string, rest: Journey | null): Journey | null {
  const leg = ride.legIndex === null ? undefined : journey.legs[ride.legIndex];
  if (!leg?.transit) return null;
  const isLast = ride.legIndex === journey.legs.length - 1;
  if (!isLast && !rest) return null;
  const swapped: Leg = {
    ...leg,
    timing: { ...leg.timing, scheduledDeparture: departure.scheduledDeparture, scheduledArrival: exitAt },
    durationSeconds: Math.max(0, Math.round((Date.parse(exitAt) - Date.parse(departure.scheduledDeparture)) / 1000)),
    transit: { ...leg.transit, engineTripId: departure.tripRef, sourceTripId: trip.sourceTripId, serviceDate: trip.serviceDate, startTime: trip.startTime },
  };
  delete (swapped as { intermediateStops?: unknown }).intermediateStops;
  delete (swapped as { boarding?: unknown }).boarding;
  const legs = [swapped, ...(rest?.legs ?? [])];
  const walks = legs.filter((l) => l.kind === "walk");
  const departs = swapped.timing.scheduledDeparture;
  const arrives = legs[legs.length - 1]!.timing.scheduledArrival;
  const distances = walks.map((l) => l.distanceMeters);
  return {
    ...journey,
    id: `${journey.id}~wait-${departure.tripRef}`,
    timing: { ...journey.timing, scheduledDeparture: departs, scheduledArrival: arrives },
    durationSeconds: Math.round((Date.parse(arrives) - Date.parse(departs)) / 1000),
    walkingSeconds: walks.reduce((sum, l) => sum + l.durationSeconds, 0),
    walkingDistanceMeters: distances.some((d) => d === null) ? null : distances.reduce<number>((s, d) => s + (d ?? 0), 0),
    transfers: legs.filter((l) => l.kind === "transit").length - 1,
    legs,
  };
}

/** The plan after a swapped ride: from its exit stop at its arrival there. Null when the ride ends the journey. */
export function afterExitRequest(journey: Journey, ride: NavStep, exitAt: string, lang: Lang): JourneyRequest | null {
  if (ride.legIndex === null || ride.legIndex === journey.legs.length - 1 || !ride.target.stopId) return null;
  const to = destinationInput(journey);
  if (!to) return null;
  return { from: { kind: "stop", stopId: ride.target.stopId }, to, departAt: toIsraelIso(new Date(exitAt)), results: MISSED_RESULTS, lang };
}

export const firstRide = (journey: Journey): Leg | null => journey.legs.find((leg) => leg.kind === "transit") ?? null;

/** Walking before the first ride, in seconds. */
export function walkBeforeRide(journey: Journey): number {
  let seconds = 0;
  for (const leg of journey.legs) {
    if (leg.kind === "transit") break;
    seconds += leg.durationSeconds;
  }
  return seconds;
}

const sameInstant = (a: string, b: string) => Date.parse(a) === Date.parse(b);
const arrival = (journey: Journey) => Date.parse(journey.timing.scheduledArrival);

/** A planned journey that boards exactly that departure (same stop, route and time). */
export function waitJourney(journeys: readonly Journey[], ride: NavStep, departure: Departure): Journey | null {
  const matches = journeys.filter((journey) => {
    const leg = firstRide(journey);
    if (!leg?.transit) return false;
    const routeOk = leg.transit.routeId === (ride.ride?.routeId ?? leg.transit.routeId) || leg.transit.routeShortName === ride.ride?.routeShortName;
    return leg.from.stopId === departure.stopId && routeOk && sameInstant(leg.timing.scheduledDeparture, departure.scheduledDeparture);
  });
  return matches.sort((a, b) => arrival(a) - arrival(b))[0] ?? null;
}

/** The earliest-arriving planned journey whose first ride boards at another stop. */
export function walkJourney(journeys: readonly Journey[], ride: NavStep): Journey | null {
  const here = ride.from?.stopId ?? null;
  const elsewhere = journeys.filter((journey) => {
    const leg = firstRide(journey);
    return !!leg?.transit && !!leg.from.stopId && leg.from.stopId !== here;
  });
  return elsewhere.sort((a, b) => arrival(a) - arrival(b))[0] ?? null;
}

/** Where the journey ends, as a journey input (coordinates unless it ends at a stop). */
export function destinationInput(journey: Journey): LocationInput | null {
  const last = journey.legs[journey.legs.length - 1];
  if (!last) return null;
  if (last.to.stopId) return { kind: "stop", stopId: last.to.stopId };
  return { kind: "coordinate", latitude: last.to.latitude, longitude: last.to.longitude };
}

export const MISSED_RESULTS = 3;

/** Plan from the stop, leaving at the next departure (it should board it). */
export function waitRequest(journey: Journey, departure: Departure, lang: Lang): JourneyRequest | null {
  const to = destinationInput(journey);
  if (!to) return null;
  return { from: { kind: "stop", stopId: departure.stopId }, to, departAt: toIsraelIso(new Date(departure.scheduledDeparture)), results: MISSED_RESULTS, lang };
}

/** Plan from where the passenger stands (or the stop, without a fix), leaving at `at`. */
export function walkRequest(journey: Journey, ride: NavStep, fix: Fix | null, at: number, lang: Lang): JourneyRequest | null {
  const to = destinationInput(journey);
  const from = fix ? { latitude: fix.latitude, longitude: fix.longitude } : ride.from;
  if (!to || !from || !Number.isFinite(from.latitude) || !Number.isFinite(from.longitude)) return null;
  return {
    from: { kind: "coordinate", latitude: from.latitude, longitude: from.longitude },
    to,
    departAt: toIsraelIso(new Date(at)),
    results: MISSED_RESULTS,
    lang,
  };
}
