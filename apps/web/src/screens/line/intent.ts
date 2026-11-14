import { go } from "../../router";
import { readSession, writeSession } from "../../storage/session";

// How a line opens and how "Ride it" is carried to its screen. Routes carry no state beyond
// ids (router.ts), so the stop the passenger came from and the departure they chose are
// held in memory for the next Line screen (a reload forgets them, as with openStop), and
// the ride being set up is kept in sessionStorage (ids only, never a position) so a reload
// of #/ride keeps it.

export interface LineIntent {
  lineKey: string;
  /** The stop the passenger came from: the list opens there when no position is known. */
  stopId?: string | null;
  /** The direction (route) to show first. */
  routeId?: string | null;
  /** A departure already chosen (a time chip on the Stop screen). */
  tripRef?: string | null;
}

let pending: LineIntent | null = null;

export function openLine(intent: LineIntent): void {
  pending = intent;
  go({ name: "line", lineKey: intent.lineKey });
}

/** The intent of the way into this line, if any (read, not consumed: StrictMode renders twice). */
export function lineIntent(lineKey: string): LineIntent | null {
  return pending?.lineKey === lineKey ? pending : null;
}

export interface RideIntent {
  lineKey: string;
  routeId: string;
  boardStopId: string;
  alightStopId: string | null;
  /** The departure chosen; null takes the next one. */
  tripRef: string | null;
}

const isRide = (value: unknown): value is RideIntent => {
  const ride = value as Partial<RideIntent> | null;
  return (
    !!ride &&
    typeof ride.lineKey === "string" &&
    typeof ride.routeId === "string" &&
    typeof ride.boardStopId === "string" &&
    (ride.alightStopId === null || typeof ride.alightStopId === "string") &&
    (ride.tripRef === null || typeof ride.tripRef === "string")
  );
};

export function readRide(): RideIntent | null {
  return readSession("ride", isRide);
}

export function writeRide(ride: RideIntent): void {
  writeSession("ride", ride);
}

/** Ride it: the line, the stop to board at and the one to get off at (board 5). */
export function openRide(ride: RideIntent): void {
  writeRide(ride);
  go({ name: "ride" });
}
