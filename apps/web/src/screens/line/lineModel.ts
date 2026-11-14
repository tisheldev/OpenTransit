import type { LineItem } from "../../api/lines";
import type { DeparturesPage, StopLines, StopsPage, Trip } from "../../api/schemas";
import { haversineMeters, type LatLon } from "../../nav/geo";
import { shortHeadsign } from "../stop/lines";

// The Line screen's facts (board 4) and Ride it's (board 5), pure so they unit-test without
// React or the map: the line's directions (one pattern each), which stop it opens at and
// what is folded around it, each stop's time on the next trip, the stops where a train can
// be caught, and the line's headway.

type LinePattern = StopLines["data"][number]["patterns"][number];
export type PatternStop = LinePattern["stops"][number];
type Departure = DeparturesPage["data"][number];

export interface Direction {
  routeId: string;
  /** Where it goes, without the GTFS city prefix ("מסוף הטייסים"). */
  towards: string;
  origin: string;
  stops: PatternStop[];
}

const cleanName = (name: string | null | undefined) => (name ?? "").trim();

/**
 * One direction per route of the line, in the line's own order: the route's longest
 * pattern (a MOT route is one direction; its shorter patterns are short workings). A
 * pattern carries its own routeId (`?patterns=all` includes the other direction's routes
 * under the stop's route); one without it belongs to its item's route.
 */
export function directionsOf(line: LineItem, items: StopLines["data"]): Direction[] {
  const patterns: Array<{ routeId: string; pattern: LinePattern }> = [];
  for (const item of items) {
    for (const pattern of item.patterns) {
      const own = (pattern as Record<string, unknown>).routeId;
      const routeId = typeof own === "string" ? own : item.routeId;
      if (line.routeIds.includes(routeId) && pattern.stops.length >= 2) patterns.push({ routeId, pattern });
    }
  }
  const directions: Direction[] = [];
  for (const routeId of line.routeIds) {
    const best = patterns.filter((entry) => entry.routeId === routeId).sort((a, b) => b.pattern.stops.length - a.pattern.stops.length)[0];
    if (!best) continue;
    const described = line.directions.find((direction) => direction.routeId === routeId);
    const stops = best.pattern.stops;
    const towards =
      shortHeadsign(described?.headsign ?? best.pattern.headsign) ?? (cleanName(described?.destinationName) || cleanName(stops[stops.length - 1]?.name));
    directions.push({ routeId, towards, origin: cleanName(described?.originName) || cleanName(stops[0]?.name), stops });
  }
  return directions;
}

/** Where the list opens: the stop nearest the passenger, else a stop asked for, else the first. */
export function anchorIndex(stops: readonly PatternStop[], fix: LatLon | null, preferred: readonly (string | null | undefined)[] = []): number {
  if (fix && stops.length > 0) {
    let best = 0;
    let bestDistance = Infinity;
    stops.forEach((stop, index) => {
      const distance = haversineMeters(fix, stop);
      if (distance < bestDistance) {
        best = index;
        bestDistance = distance;
      }
    });
    // Further than 2 km the passenger is not "near" this line: open where asked instead.
    if (bestDistance <= 2000 || preferred.every((id) => !id)) return best;
  }
  for (const id of preferred) {
    const index = id ? stops.findIndex((stop) => stop.stopId === id) : -1;
    if (index >= 0) return index;
  }
  return 0;
}

/** Stops shown after the anchor before the rest fold (board 4: four, then "17 more", then the end). */
export const AFTER_VISIBLE = 4;

export type StopRow =
  | { kind: "stop"; index: number }
  | { kind: "earlier"; count: number; from: number; to: number }
  | { kind: "more"; count: number; from: number; to: number };

/**
 * The list around the anchor: earlier stops folded into one row (unless opened), the
 * anchor, a few stops after it, the rest folded (unless opened), and the terminus.
 */
export function stopRows(count: number, anchor: number, open: { earlier: boolean; later: boolean }, afterVisible = AFTER_VISIBLE): StopRow[] {
  const rows: StopRow[] = [];
  if (count === 0) return rows;
  const last = count - 1;
  if (anchor > 0) {
    if (open.earlier) for (let i = 0; i < anchor; i += 1) rows.push({ kind: "stop", index: i });
    else rows.push({ kind: "earlier", count: anchor, from: 0, to: anchor - 1 });
  }
  rows.push({ kind: "stop", index: anchor });
  if (anchor === last) return rows;
  const between = last - anchor - 1;
  if (open.later || between <= afterVisible + 1) {
    for (let i = anchor + 1; i < last; i += 1) rows.push({ kind: "stop", index: i });
  } else {
    for (let i = anchor + 1; i <= anchor + afterVisible; i += 1) rows.push({ kind: "stop", index: i });
    rows.push({ kind: "more", count: between - afterVisible, from: anchor + afterVisible + 1, to: last - 1 });
  }
  rows.push({ kind: "stop", index: last });
  return rows;
}

/**
 * Each pattern stop's time on a trip (its departure, or arrival at the end), matched to
 * the trip's calls in order by stop id; null where the trip does not call.
 */
export function stopTimes(stops: readonly PatternStop[], trip: Trip["data"] | null): Array<string | null> {
  if (!trip) return stops.map(() => null);
  const calls = [...trip.calls].sort((a, b) => a.callSequence - b.callSequence);
  let next = 0;
  return stops.map((stop) => {
    for (let i = next; i < calls.length; i += 1) {
      if (calls[i]!.stopId === stop.stopId) {
        next = i + 1;
        return calls[i]!.scheduledDeparture ?? calls[i]!.scheduledArrival;
      }
    }
    return null;
  });
}

/** Departures of the line's direction at its stop, soonest first, without repeats. */
export function lineDepartures(departures: readonly Departure[], routeId: string, now: Date): Departure[] {
  const seen = new Set<string>();
  return departures
    .filter((item) => item.routeId === routeId && Date.parse(item.scheduledDeparture) >= now.getTime() - 30_000)
    .sort((a, b) => Date.parse(a.scheduledDeparture) - Date.parse(b.scheduledDeparture))
    .filter((item) => (seen.has(item.tripRef) ? false : (seen.add(item.tripRef), true)));
}

/**
 * "כל 12 דק׳ בערך": the median gap between the next departures, in whole minutes; null
 * with fewer than three departures (two gaps) or an irregular gap above two hours.
 */
export function headwayMinutes(departures: readonly Departure[]): number | null {
  const times = departures.map((item) => Date.parse(item.scheduledDeparture)).sort((a, b) => a - b);
  const gaps = times.slice(1).map((time, index) => (time - times[index]!) / 60_000).filter((gap) => gap > 0);
  if (gaps.length < 2) return null;
  const sorted = [...gaps].sort((a, b) => a - b);
  const middle = sorted.length % 2 ? sorted[(sorted.length - 1) / 2]! : (sorted[sorted.length / 2 - 1]! + sorted[sorted.length / 2]!) / 2;
  const minutes = Math.round(middle);
  return minutes > 0 && minutes <= 120 ? minutes : null;
}

export type RailKind = "rail" | "light_rail";

/** Within this distance of a station, a stop "can catch a train" (board 4: the train badge). */
export const RAIL_NEAR_METERS = 200;

/** Each stop's nearest rail or light-rail station within reach, by stop id. */
export function railAt(stops: readonly PatternStop[], stations: StopsPage["data"]): Map<string, RailKind> {
  const rail = stations
    .map((station) => ({ station, mode: String((station as Record<string, unknown>).mode ?? "") }))
    .filter((entry): entry is { station: (typeof stations)[number]; mode: RailKind } => entry.mode === "rail" || entry.mode === "light_rail");
  const found = new Map<string, RailKind>();
  for (const stop of stops) {
    let best: { distance: number; mode: RailKind } | null = null;
    for (const { station, mode } of rail) {
      const distance = haversineMeters(stop, station);
      if (distance <= RAIL_NEAR_METERS && (!best || distance < best.distance)) best = { distance, mode };
    }
    if (best) found.set(stop.stopId, best.mode);
  }
  return found;
}

/** The pattern's extent, padded, for the stations request (west, south, east, north). */
export function paddedBounds(stops: readonly PatternStop[], padDegrees = 0.003): { west: number; south: number; east: number; north: number } | null {
  if (stops.length === 0) return null;
  const lons = stops.map((stop) => stop.longitude);
  const lats = stops.map((stop) => stop.latitude);
  return {
    west: Math.min(...lons) - padDegrees,
    south: Math.min(...lats) - padDegrees,
    east: Math.max(...lons) + padDegrees,
    north: Math.max(...lats) + padDegrees,
  };
}

/** Minutes on foot for a straight-line distance (about 75 m a minute once streets are counted). */
export function walkMinutes(meters: number): number {
  return Math.max(1, Math.ceil(meters / 75));
}

// --- Ride it (board 5) --------------------------------------------------------------

export type RideRow =
  | { kind: "stop"; index: number; role: "board" | "between" | "alight" | "after" }
  | { kind: "more"; count: number };

/** Stops shown greyed after the exit before the rest fold (board 5: one, then "16 more"). */
export const AFTER_EXIT_VISIBLE = 1;

/** The ride from the board stop: its stops to the exit, one after it, the rest folded. */
export function rideRows(count: number, board: number, alight: number | null, open = false): RideRow[] {
  const rows: RideRow[] = [];
  const last = count - 1;
  const exit = alight !== null && alight > board ? Math.min(alight, last) : null;
  rows.push({ kind: "stop", index: board, role: "board" });
  if (exit === null) {
    for (let i = board + 1; i <= last; i += 1) rows.push({ kind: "stop", index: i, role: "between" });
    return rows;
  }
  for (let i = board + 1; i < exit; i += 1) rows.push({ kind: "stop", index: i, role: "between" });
  rows.push({ kind: "stop", index: exit, role: "alight" });
  const after = last - exit;
  if (open || after <= AFTER_EXIT_VISIBLE + 1) {
    for (let i = exit + 1; i <= last; i += 1) rows.push({ kind: "stop", index: i, role: "after" });
  } else {
    for (let i = exit + 1; i <= exit + AFTER_EXIT_VISIBLE; i += 1) rows.push({ kind: "stop", index: i, role: "after" });
    rows.push({ kind: "more", count: after - AFTER_EXIT_VISIBLE });
  }
  return rows;
}
