import type { Journey, JourneyResponse } from "../../api/types";
import type { CallPosition } from "../engine";
import type { NavStep, TripDetail } from "../steps";
import recorded from "./recorded-oct31a-dizengoff-technion.json";

// Test data for the nav modules. See README.md in this folder for its source.

interface Recorded {
  source: Record<string, unknown>;
  journeys: JourneyResponse;
  trips: Record<string, TripDetail>;
  stopPositions: Record<string, { latitude: number; longitude: number }>;
}

const data = recorded as unknown as Recorded;

export const recordedSource = data.source;
/** 0: ride first, rail, 3 rides. 1: ride first, a time-only transfer (geometry null). 2: walk first, 5 rides, zero-length same-stop transfers. */
export const recordedJourneys: Journey[] = data.journeys.data.journeys;
export const recordedTrips: Record<string, TripDetail> = data.trips;

/** Call positions per ride step: every call between board and exit, or only the two before the exit. */
export function callPositionsFor(steps: readonly NavStep[], which: "all" | "two_before_exit"): Record<number, CallPosition[]> {
  const out: Record<number, CallPosition[]> = {};
  for (const step of steps) {
    const ride = step.ride;
    if (!ride || ride.boardOrdinal === null || ride.exitOrdinal === null) continue;
    const trip = recordedTrips[ride.tripRef];
    if (!trip) continue;
    const low = which === "all" ? ride.boardOrdinal : Math.max(ride.boardOrdinal, ride.exitOrdinal - 2);
    out[step.index] = trip.calls
      .filter((call) => call.ordinal >= low && call.ordinal < ride.exitOrdinal!)
      .flatMap((call) => {
        const position = data.stopPositions[call.stopId];
        return position ? [{ ordinal: call.ordinal, ...position }] : [];
      });
  }
  return out;
}
