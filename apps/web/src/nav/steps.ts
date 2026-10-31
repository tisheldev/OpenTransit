import type { Trip } from "../api/schemas";
import type { Journey, Leg } from "../api/types";

// Steps map one-to-one from the journey's legs, then `arrive` (design: Navigation
// engine, "Steps"). Everything a step card needs is read from the journey and, when it
// was fetched, the trip detail; nothing is invented (a time-only walk has no distance).

export type NavStepKind = "walk_to_stop" | "ride" | "transfer_walk" | "walk_to_destination" | "arrive";

export type TripDetail = Trip["data"];

export interface NavPlace {
  /** As the API names it; coordinate ends are "START"/"END" (the screen shows the draft label). */
  name: string;
  latitude: number;
  longitude: number;
  stopId: string | null;
  stopCode: string | null;
}

export interface NavRide {
  /** The trip to fetch (`GET /v1/trips/{tripRef}`): the leg's `transit.engineTripId`. */
  tripRef: string;
  /** API leg mode: "bus", "rail", "light_rail", … */
  mode: string;
  /** Route short name, or null when empty (rail): say "train to {destinationName}" then. */
  lineLabel: string | null;
  routeShortName: string;
  /** As returned; for rail it is the train number. */
  headsign: string | null;
  /** Where this ride gets off (the leg's `to.name`). */
  destinationName: string;
  operatorId: string;
  operatorName: string;
  routeId: string;
  /** Call ordinals in the trip detail; null when the detail is missing or did not match. */
  boardOrdinal: number | null;
  exitOrdinal: number | null;
  /** Stops ridden (exit ordinal − board ordinal); null without both ordinals. */
  stopCount: number | null;
}

export interface NavStep {
  index: number;
  /** The journey leg this step comes from; null for `arrive`. */
  legIndex: number | null;
  kind: NavStepKind;
  /** Where the step starts (null for `arrive`). For a ride, the boarding stop. */
  from: NavPlace | null;
  /** Where the step ends: the stop to walk to, the exit stop, or the destination. */
  target: NavPlace;
  scheduledDeparture: string;
  scheduledArrival: string;
  durationSeconds: number;
  /** Null when unknown (e.g. a transfer whose street path is unavailable): show time only. */
  distanceMeters: number | null;
  /** Whether the leg has a street/route geometry. */
  hasGeometry: boolean;
  ride: NavRide | null;
}

const place = (location: Leg["from"]): NavPlace => ({
  name: location.name,
  latitude: location.latitude,
  longitude: location.longitude,
  stopId: location.stopId ?? null,
  stopCode: location.stopCode ?? null,
});

const sameInstant = (a: string | null | undefined, b: string): boolean =>
  typeof a === "string" && Date.parse(a) === Date.parse(b);

type Call = TripDetail["calls"][number];

/** Match a stop in the trip's calls: same stop and scheduled time, else the only call at that stop. */
function matchCall(calls: readonly Call[], stopId: string | null, time: string, side: "board" | "exit", after: number): Call | null {
  if (!stopId) return null;
  const atStop = calls.filter((call) => call.stopId === stopId && call.ordinal > after);
  const timed = atStop.find((call) =>
    side === "board"
      ? sameInstant(call.scheduledDeparture ?? call.scheduledArrival, time)
      : sameInstant(call.scheduledArrival ?? call.scheduledDeparture, time),
  );
  if (timed) return timed;
  return atStop.length === 1 ? atStop[0]! : null;
}

export function rideOrdinals(
  leg: Leg,
  trip: TripDetail | undefined,
): { boardOrdinal: number | null; exitOrdinal: number | null; stopCount: number | null } {
  if (!trip) return { boardOrdinal: null, exitOrdinal: null, stopCount: null };
  const board = matchCall(trip.calls, leg.from.stopId ?? null, leg.timing.scheduledDeparture, "board", -Infinity);
  const exit = board ? matchCall(trip.calls, leg.to.stopId ?? null, leg.timing.scheduledArrival, "exit", board.ordinal) : null;
  if (!board || !exit) return { boardOrdinal: board?.ordinal ?? null, exitOrdinal: null, stopCount: null };
  return { boardOrdinal: board.ordinal, exitOrdinal: exit.ordinal, stopCount: exit.ordinal - board.ordinal };
}

function walkKind(legs: readonly Leg[], index: number): NavStepKind {
  const transitBefore = legs.slice(0, index).some((leg) => leg.kind === "transit");
  const transitAfter = legs.slice(index + 1).some((leg) => leg.kind === "transit");
  if (!transitAfter) return "walk_to_destination";
  return transitBefore ? "transfer_walk" : "walk_to_stop";
}

/**
 * Steps for a journey. `trips` holds trip details by engineTripId (as ActiveTrip keeps
 * them); a missing one leaves that ride's ordinals and stop count null.
 */
export function buildSteps(journey: Journey, trips: Readonly<Record<string, TripDetail>> = {}): NavStep[] {
  const steps: NavStep[] = journey.legs.map((leg, legIndex) => {
    const base = {
      index: legIndex,
      legIndex,
      from: place(leg.from),
      target: place(leg.to),
      scheduledDeparture: leg.timing.scheduledDeparture,
      scheduledArrival: leg.timing.scheduledArrival,
      durationSeconds: leg.durationSeconds,
      distanceMeters: leg.distanceMeters ?? null,
      hasGeometry: (leg.geometry?.coordinates.length ?? 0) >= 2,
    };
    if (leg.kind === "transit" && leg.transit) {
      const transit = leg.transit;
      const shortName = transit.routeShortName.trim();
      return {
        ...base,
        kind: "ride",
        ride: {
          tripRef: transit.engineTripId,
          mode: leg.mode,
          lineLabel: shortName === "" ? null : shortName,
          routeShortName: transit.routeShortName,
          headsign: transit.headsign ?? null,
          destinationName: leg.to.name,
          operatorId: transit.operatorId,
          operatorName: transit.operatorName,
          routeId: transit.routeId,
          ...rideOrdinals(leg, trips[transit.engineTripId]),
        },
      };
    }
    return { ...base, kind: walkKind(journey.legs, legIndex), ride: null };
  });
  const last = journey.legs[journey.legs.length - 1];
  steps.push({
    index: steps.length,
    legIndex: null,
    kind: "arrive",
    from: null,
    target: last
      ? place(last.to)
      : { name: "", latitude: NaN, longitude: NaN, stopId: null, stopCode: null },
    scheduledDeparture: journey.timing.scheduledArrival,
    scheduledArrival: journey.timing.scheduledArrival,
    durationSeconds: 0,
    distanceMeters: null,
    hasGeometry: false,
    ride: null,
  });
  return steps;
}
