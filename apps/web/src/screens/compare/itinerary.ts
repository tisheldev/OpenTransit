import type { Journey, Leg } from "../../api/types";
import { transitMode, type TransitMode } from "../../plan/chartLayout";
import { placeName, platformOf, type EndLabels } from "./labels";

// The selected option as an itinerary timeline (design: Route details — C04): places
// with their scheduled times, and between them a ride or a walk. Pure; RouteDetails
// draws it. Every time is a returned scheduled time; waits are the gaps between them.
//
//   08:12  ● Dizengoff Center/Dizengoff           place (origin, a boarding stop)
//          ┃ [8] towards Terminal · 4 stops       ride
//   08:18  ● Shalom station                       place (exit)
//          ┊ walk 2 min · 230 m · wait 1 min     walk (+ the wait before the next ride)
//   08:21  ● HaShalom                             place (board)

export type PlaceRole = "origin" | "board" | "exit" | "transfer" | "destination";
/** What the timeline's line looks like on one side of a place. */
export type Track = TransitMode | "walk" | null;

export type ItineraryItem =
  | {
      kind: "place";
      role: PlaceRole;
      /** Scheduled time at this place: a departure for origin / board, an arrival otherwise. */
      time: string;
      name: string;
      platform: string | null;
      above: Track;
      below: Track;
    }
  | { kind: "ride"; legIndex: number; leg: Leg; mode: TransitMode }
  | {
      kind: "walk";
      legIndex: number;
      seconds: number;
      distanceMeters: number | null;
      /** A 0 m "walk" between two stops of the same name: a transfer at the same stop. */
      sameStop: boolean;
      /** Waiting around this walk until the next ride leaves (or after the last ride). */
      waitSeconds: number;
    }
  | { kind: "wait"; seconds: number };

const ms = (iso: string) => Date.parse(iso);
const gap = (from: string, to: string) => Math.max(0, (ms(to) - ms(from)) / 1000);
const track = (leg: Leg | undefined): Track => (leg ? (leg.kind === "walk" ? "walk" : transitMode(leg)) : null);

export function sameStopTransfer(leg: Leg): boolean {
  return leg.kind === "walk" && leg.distanceMeters === 0 && leg.from.name.trim() === leg.to.name.trim();
}

export function buildItinerary(journey: Journey, ends: EndLabels): ItineraryItem[] {
  const legs = journey.legs;
  const items: ItineraryItem[] = [];
  const first = legs[0];
  if (!first) return items;
  const place = (role: PlaceRole, time: string, name: string, leg: Leg | undefined, above: Track, below: Track) =>
    items.push({ kind: "place", role, time, name: placeName(name, ends), platform: leg ? platformOf(leg) : null, above, below });

  place(
    "origin",
    first.timing.scheduledDeparture,
    first.from.name,
    first.kind === "transit" ? first : undefined,
    null,
    track(first),
  );

  legs.forEach((leg, index) => {
    const previous = legs[index - 1];
    const next = legs[index + 1];
    if (leg.kind === "transit") {
      // Ride after ride with no walk between: wait at the stop, then board.
      if (previous?.kind === "transit") {
        const wait = gap(previous.timing.scheduledArrival, leg.timing.scheduledDeparture);
        if (wait >= 60) items.push({ kind: "wait", seconds: wait });
        place("board", leg.timing.scheduledDeparture, leg.from.name, leg, track(previous), track(leg));
      }
      items.push({ kind: "ride", legIndex: index, leg, mode: transitMode(leg) });
      place(next ? "exit" : "destination", leg.timing.scheduledArrival, leg.to.name, undefined, track(leg), track(next));
      return;
    }
    // A walk: the wait before it (after a ride) and before the next ride both belong here.
    const before = previous?.kind === "transit" ? gap(previous.timing.scheduledArrival, leg.timing.scheduledDeparture) : 0;
    const after = next ? gap(leg.timing.scheduledArrival, next.timing.scheduledDeparture) : 0;
    items.push({
      kind: "walk",
      legIndex: index,
      seconds: leg.durationSeconds,
      distanceMeters: leg.distanceMeters,
      sameStop: sameStopTransfer(leg),
      waitSeconds: before + after,
    });
    if (!next) {
      place("destination", leg.timing.scheduledArrival, leg.to.name, undefined, "walk", null);
    } else if (next.kind === "transit") {
      place("board", next.timing.scheduledDeparture, next.from.name, next, "walk", track(next));
    } else {
      place("transfer", leg.timing.scheduledArrival, leg.to.name, undefined, "walk", "walk");
    }
  });
  return items;
}

/** The place items only (tests and the screen-reader summary). */
export function placesOf(items: readonly ItineraryItem[]) {
  return items.flatMap((item) => (item.kind === "place" ? [item] : []));
}
