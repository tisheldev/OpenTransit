import { haversineMeters, type LatLon } from "../../nav/geo";
import { groupLines, type Departure, type StopLine } from "../stop/lines";
import type { NearStop, NearStopDepartures } from "./homeStops";

// "Near you" on Home (board 1; user, 12 November 2026: "Lines nearby"): the next departure
// of each line across the stops within a 5-minute walk, each row naming its stop and the
// walk to it. Pure, so it unit-tests without the screen.

/** Walking pace for "N min walk" (the 400 m ring is a 5-minute walk). */
export const WALK_METERS_PER_MINUTE = 80;
/** The walk the list covers, in minutes (the ring). */
export const NEAR_WALK_MINUTES = 5;
/** Rows in "Near you"; the sheet scrolls past the board's four. */
export const NEAR_LINES = 6;

export interface NearLine {
  line: StopLine;
  stop: NearStop;
  stopName: string;
  walkMinutes: number;
}

/** Whole minutes on foot, at least one. */
export function walkMinutes(meters: number): number {
  return Math.max(1, Math.ceil(meters / WALK_METERS_PER_MINUTE));
}

export const nearStopName = (stop: NearStop): string => stop.name ?? stop.code ?? stop.stopId;

/**
 * One line: its operator and number (the MOT line code is not on a departure; an operator
 * does not run two lines with one number in one place). Directions are the same line.
 */
export function lineIdentity(line: Pick<StopLine, "operatorId" | "operatorName" | "mode" | "label">): string {
  return `${line.operatorId ?? line.operatorName ?? line.mode}|${line.label}`;
}

/** The API's own distance from the centre it was asked about, else a straight line from `centre`. */
function metersTo(stop: NearStop, centre: LatLon): number {
  const sent = (stop as NearStop & { distanceMeters?: number | null }).distanceMeters;
  return typeof sent === "number" && Number.isFinite(sent) ? sent : haversineMeters(centre, stop);
}

/**
 * Each line's next departure across the stops, earliest first; on a tie, the nearer stop.
 * Departures already gone are dropped (groupLines). The stops are the API's answer within
 * the 400 m ring, so every one is within the walk; none is dropped here.
 */
export function nearLines(
  stops: readonly NearStopDepartures[],
  centre: LatLon,
  options: { trainLabel: string; now: Date; max?: number },
): NearLine[] {
  const best = new Map<string, NearLine>();
  for (const entry of stops) {
    if (!entry.departures) continue;
    const minutes = walkMinutes(metersTo(entry.stop, centre));
    for (const line of groupLines(entry.departures as Departure[], entry.routes, { trainLabel: options.trainLabel, now: options.now })) {
      const key = lineIdentity(line);
      const held = best.get(key);
      const sooner = held ? Date.parse(line.next) - Date.parse(held.line.next) : -1;
      if (!held || sooner < 0 || (sooner === 0 && minutes < held.walkMinutes)) {
        best.set(key, { line, stop: entry.stop, stopName: nearStopName(entry.stop), walkMinutes: minutes });
      }
    }
  }
  return [...best.values()]
    .sort((a, b) => Date.parse(a.line.next) - Date.parse(b.line.next) || a.walkMinutes - b.walkMinutes)
    .slice(0, options.max ?? NEAR_LINES);
}
