import type { Journey, Leg } from "../../api/types";
import type { Fix } from "../../lib/geolocation";
import { journeyToScene, legLabel } from "../../map/fromJourney";
import type { LonLat, MapPin, MapRouteLeg, MapScene, MapStopPin, MapTag, MapTagLine } from "../../map/scene";
import type { CallPosition } from "../../nav/engine";
import { lineLengthMeters, pointAlongLine, projectOntoLine, splitLineAt, type Position } from "../../nav/geo";
import type { NavStep } from "../../nav/steps";
import type { EndLabels } from "./describe";

// What Navigate's map draws (boards 4–6, 11 November 2026). Walking: the map follows the
// passenger, the walk in ink dots (the part walked dimmer), the ride ahead in its colour,
// and the boarding stop as a large pin whose tag carries the line and the countdown. On
// board: the part of the ride already travelled in grey, the rest in colour, the next leg,
// small rings on the stops, "יורדים כאן" at the exit, framed on what is left. Bus didn't
// come: the missed line faded, the other stop as the selected pin with its departure, and
// the walk to it. Every fact a tag shows is also in the panel as text.

/** Beyond this from the ride's line a fix does not cut it into travelled and ahead. */
const ON_LINE_METERS = 150;

const lonLat = (place: { longitude: number; latitude: number }): LonLat => [place.longitude, place.latitude];

function coordinatesOf(leg: Leg | undefined): LonLat[] | null {
  const coords = leg?.geometry?.coordinates;
  if (!coords || coords.length < 2) return null;
  const line = coords.filter((point): point is [number, number] => typeof point[0] === "number" && typeof point[1] === "number");
  return line.length >= 2 ? line.map(([lon, lat]) => [lon, lat] as LonLat) : null;
}

function legOf(leg: Leg, coordinates: LonLat[] | null, tone: MapRouteLeg["tone"] = "normal"): MapRouteLeg {
  return {
    kind: leg.kind,
    mode: leg.mode,
    coordinates,
    from: lonLat(leg.from),
    to: lonLat(leg.to),
    label: legLabel(leg),
    operatorId: leg.transit?.operatorId ?? null,
    operatorName: leg.transit?.operatorName ?? null,
    tone,
  };
}

const asLonLat = (line: readonly Position[]): LonLat[] => line.map((p) => [p[0]!, p[1]!] as LonLat);

/**
 * A leg cut where `point` projects onto it: the part behind (in `behind` tone) and the
 * part ahead. Without geometry, a point, or a point near the line, the leg is whole.
 */
function cutLeg(leg: Leg, point: { latitude: number; longitude: number } | null, behind: MapRouteLeg["tone"], minAlong = 0): { legs: MapRouteLeg[]; ahead: LonLat[] | null } {
  const coordinates = coordinatesOf(leg);
  if (!coordinates || !point) return { legs: [legOf(leg, coordinates)], ahead: coordinates };
  const projection = projectOntoLine(point, coordinates, { minAlongMeters: minAlong });
  if (!projection || projection.distanceMeters > ON_LINE_METERS || projection.alongMeters <= 0) {
    return { legs: [legOf(leg, coordinates)], ahead: coordinates };
  }
  const { before, after } = splitLineAt(coordinates, projection.alongMeters);
  const legs: MapRouteLeg[] = [];
  if (before.length >= 2) legs.push(legOf(leg, asLonLat(before), behind));
  if (after.length >= 2) legs.push(legOf(leg, asLonLat(after)));
  return { legs, ahead: after.length >= 2 ? asLonLat(after) : null };
}

export function tagLine(step: NavStep, label: string): MapTagLine {
  return { mode: step.ride?.mode ?? "bus", label, operatorId: step.ride?.operatorId ?? null, operatorName: step.ride?.operatorName ?? null };
}

function tagLineOf(leg: Leg, label: string): MapTagLine {
  return { mode: leg.mode, label, operatorId: leg.transit?.operatorId ?? null, operatorName: leg.transit?.operatorName ?? null };
}

const userOf = (fix: Fix | null) => (fix ? { position: [fix.longitude, fix.latitude] as LonLat, accuracyMeters: fix.accuracyMeters } : null);

export interface NavSceneInput {
  journey: Journey;
  steps: readonly NavStep[];
  step: NavStep;
  /** The step's phase: a ride "waiting" is drawn as the walk to its stop. */
  waiting: boolean;
  labels: EndLabels;
  fix: Fix | null;
  /** Known positions of this ride's calls (the two before the exit, when fetched). */
  callPositions?: readonly CallPosition[];
  /** On board without a fix: the last call passed by the timetable, when its position is known. */
  passedOrdinal?: number | null;
  words: {
    /** The boarding tag: line badge text and the countdown ("4 דק׳"). */
    badge: string;
    countdown: string | null;
    exitHere: string;
  };
}

/** Walking to a ride's stop (or waiting at it): board 4. */
function walkScene(input: NavSceneInput, ride: NavStep): MapScene {
  const { journey, step, fix, words } = input;
  const route: MapRouteLeg[] = [];
  const walkLeg = step.kind === "ride" || step.legIndex === null ? undefined : journey.legs[step.legIndex];
  if (walkLeg) route.push(...cutLeg(walkLeg, fix, "faded").legs);
  const rideLeg = ride.legIndex === null ? undefined : journey.legs[ride.legIndex];
  if (rideLeg) route.push(legOf(rideLeg, coordinatesOf(rideLeg)));
  const stop = ride.from!;
  const at = lonLat(stop);
  const stopPins: MapStopPin[] = [{ id: "board", position: at, selected: true, ariaLabel: stop.name }];
  const tags: MapTag[] = [{ id: "board", position: at, kind: "strong", line: tagLine(ride, words.badge), text: words.countdown ?? undefined }];
  const frame: LonLat[] = [at];
  if (walkLeg) frame.push(lonLat(walkLeg.from));
  return {
    route,
    pins: [],
    stopPins,
    tags,
    user: userOf(fix),
    camera: fix ? "follow" : "fit",
    topControls: true,
    fitTo: fix ? null : frame,
    pick: false,
  };
}

/** On board: board 5. */
function rideScene(input: NavSceneInput): MapScene {
  const { journey, steps, step, fix, words } = input;
  const leg = journey.legs[step.legIndex!]!;
  const coordinates = coordinatesOf(leg);
  const boardAlong = coordinates && step.from ? (projectOntoLine(step.from, coordinates)?.alongMeters ?? 0) : 0;
  // Where the passenger is: the fix, else the last call passed by the timetable (if placed).
  const passed = input.passedOrdinal != null ? input.callPositions?.find((call) => call.ordinal === input.passedOrdinal) : undefined;
  const cut = cutLeg(leg, fix ?? passed ?? null, "travelled", boardAlong);
  const route: MapRouteLeg[] = [...cut.legs];
  // The next leg (and the ride after a transfer walk), so the change is on the map.
  const pins: MapPin[] = [];
  for (const next of [steps[step.index + 1], steps[step.index + 2]]) {
    if (!next || next.legIndex === null) break;
    const nextLeg = journey.legs[next.legIndex]!;
    route.push(legOf(nextLeg, coordinatesOf(nextLeg)));
    if (next.kind === "ride") {
      if (next.from) pins.push({ id: `board-${next.index}`, role: "transfer", position: lonLat(next.from), label: next.from.name, mode: nextLeg.mode });
      break;
    }
  }
  // Small rings on the stops: every stop the journey lists (API PR #35), else the calls
  // whose positions were fetched at Start (the two before the exit).
  const between = step.ride?.intermediateStops;
  if (between && between.length > 0) {
    between.forEach((stop, i) => pins.push({ id: `call-${i}`, role: "stop", position: lonLat(stop), label: stop.name, mode: leg.mode }));
  } else {
    for (const call of input.callPositions ?? []) {
      pins.push({ id: `call-${call.ordinal}`, role: "stop", position: lonLat(call), label: call.name ?? "", mode: leg.mode });
    }
  }
  const exit = lonLat(step.target);
  pins.push({ id: "exit", role: "stop", position: exit, label: step.target.name, mode: leg.mode });
  const frame: LonLat[] = [...(cut.ahead ?? []), exit];
  if (fix) frame.push([fix.longitude, fix.latitude]);
  return {
    route,
    pins,
    stopPins: [],
    tags: [{ id: "exit", position: exit, kind: "strong", text: words.exitHere }],
    user: userOf(fix),
    camera: "fit",
    fitTo: frame,
    pick: false,
    // The close button floats over the top of the map: keep "יורדים כאן" clear of it.
    topControls: true,
  };
}

/** Walking to the destination: the walk, the destination, the passenger. */
function finalWalkScene(input: NavSceneInput): MapScene {
  const { journey, step, fix, labels } = input;
  const leg = journey.legs[step.legIndex!]!;
  const destination: MapPin = { id: "destination", role: "destination", position: lonLat(leg.to), label: labels.destination ?? "" };
  return {
    route: cutLeg(leg, fix, "faded").legs,
    pins: [destination],
    user: userOf(fix),
    camera: fix ? "follow" : "fit",
    topControls: true,
    fitTo: fix ? null : [lonLat(leg.from), lonLat(leg.to)],
    pick: false,
  };
}

export function navScene(input: NavSceneInput): MapScene {
  const { journey, steps, step, labels, fix } = input;
  if (step.kind === "ride" && input.waiting && step.from) return walkScene(input, step);
  if (step.kind === "ride" && step.legIndex !== null) return rideScene(input);
  if (step.kind === "walk_to_stop" || step.kind === "transfer_walk") {
    const ride = steps[step.index + 1];
    if (ride?.kind === "ride" && ride.from) return walkScene(input, ride);
  }
  if (step.kind === "walk_to_destination" && step.legIndex !== null) return finalWalkScene(input);
  // Arrived (or anything else): the whole journey.
  const base = journeyToScene(journey, { originLabel: labels.origin, destinationLabel: labels.destination });
  return { ...base, user: userOf(fix), camera: "fit", pick: false, topControls: true };
}

export interface MissedSceneInput {
  journey: Journey;
  ride: NavStep;
  fix: Fix | null;
  /** The missed line's next departure here ("הבא 17:59"), when known. */
  waitText: string | null;
  /** The other stop's option, when the plan found one. */
  walk: { journey: Journey; badge: string; departs: string; walkText: string } | null;
  badge: string;
}

/** Bus didn't come: board 6. */
export function missedScene({ journey, ride, fix, waitText, walk, badge }: MissedSceneInput): MapScene {
  const route: MapRouteLeg[] = [];
  const rideLeg = ride.legIndex === null ? undefined : journey.legs[ride.legIndex];
  if (rideLeg) route.push(legOf(rideLeg, coordinatesOf(rideLeg), "faded"));
  const here = lonLat(ride.from!);
  const stopPins: MapStopPin[] = [{ id: "missed", position: here, ariaLabel: ride.from!.name }];
  const tags: MapTag[] = [{ id: "missed", position: here, kind: "faded", line: tagLine(ride, badge), text: waitText ?? undefined }];
  const frame: LonLat[] = [here];
  if (fix) frame.push([fix.longitude, fix.latitude]);
  if (walk) {
    let walkLine: LonLat[] = [];
    for (const leg of walk.journey.legs) {
      if (leg.kind === "transit") {
        route.push(legOf(leg, coordinatesOf(leg)));
        const stop = lonLat(leg.from);
        stopPins.push({ id: "other", position: stop, selected: true, ariaLabel: leg.from.name });
        tags.push({ id: "other", position: stop, kind: "strong", line: tagLineOf(leg, walk.badge), text: walk.departs, anchor: "below" });
        frame.push(stop);
        break;
      }
      const coordinates = coordinatesOf(leg);
      route.push(legOf(leg, coordinates));
      if (coordinates) walkLine = [...walkLine, ...coordinates];
    }
    // The walk's minutes beside its middle.
    const middle = walkLine.length >= 2 ? pointAlongLine(walkLine, lineLengthMeters(walkLine) / 2) : null;
    if (middle) tags.push({ id: "walk", position: [middle.longitude, middle.latitude], kind: "faded", text: walk.walkText, anchor: "center" });
  }
  return { route, pins: [], stopPins, tags, user: userOf(fix), camera: "fit", fitTo: frame, pick: false, topControls: true };
}
