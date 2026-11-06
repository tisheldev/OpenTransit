import type { Journey, Leg } from "../../api/types";
import { transitMode, type TransitMode } from "../../plan/chartLayout";
import { placeName, platformOf, type EndLabels } from "./labels";

// The selected option as an itinerary timeline (design: Route details — C04): places
// with their scheduled times, and between them a ride or a walk. Pure; RouteDetails
// draws it as steps (buildSteps, below). Every time is a returned scheduled time; waits
// are the gaps between them.
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

// The same itinerary as the design's step list (StepList, under the chart): one step per
// ride (boarding time and line, with its exit stop at its arrival time), per walk and per
// wait, then the arrival. Origin and boarding places fold into the step that leaves them:
// the first step carries the departure time, a later boarding stop is the walk's
// destination or the previous ride's exit.
//
//   08:07  [8]   towards Terminal · 3 stops · 7 min      ride
//   08:14   •    Get off · Shalom station                 its exit
//          walk  Walk 2 min · 230 m / to HaShalom         walk (+ waits)
//   09:52  pin   Arrive · Technion                         place

export type Step =
  | { kind: "ride"; time: string; leg: Leg; mode: TransitMode; exit: { time: string; name: string } | null }
  | {
      kind: "walk";
      /** The departure time when the trip starts with this walk; otherwise null. */
      time: string | null;
      seconds: number;
      distanceMeters: number | null;
      sameStop: boolean;
      waitSeconds: number;
      /** Where the walk leads (a boarding stop), or null when the arrival follows. */
      to: string | null;
    }
  | { kind: "wait"; seconds: number }
  | { kind: "place"; role: Exclude<PlaceRole, "origin" | "board">; time: string; name: string };

export function buildSteps(journey: Journey, ends: EndLabels): Step[] {
  const items = buildItinerary(journey, ends);
  const steps: Step[] = [];
  for (let index = 0; index < items.length; index += 1) {
    const item = items[index]!;
    const next = items[index + 1];
    if (item.kind === "ride") {
      const exit = next?.kind === "place" && next.role === "exit" ? { time: next.time, name: next.name } : null;
      if (exit) index += 1;
      steps.push({ kind: "ride", time: item.leg.timing.scheduledDeparture, leg: item.leg, mode: item.mode, exit });
    } else if (item.kind === "walk") {
      const leg = journey.legs[item.legIndex]!;
      steps.push({
        kind: "walk",
        time: steps.length === 0 ? leg.timing.scheduledDeparture : null,
        seconds: item.seconds,
        distanceMeters: item.distanceMeters,
        sameStop: item.sameStop,
        waitSeconds: item.waitSeconds,
        to: next?.kind === "place" && next.role !== "destination" ? next.name : null,
      });
    } else if (item.kind === "wait") {
      steps.push(item);
    } else if (item.role !== "origin" && item.role !== "board") {
      steps.push({ kind: "place", role: item.role, time: item.time, name: item.name });
    }
  }
  return steps;
}
