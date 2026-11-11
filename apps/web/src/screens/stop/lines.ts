import type { DeparturesPage, StopDetail, StopLines, Trip } from "../../api/schemas";
import { vehicleOf } from "../../lib/lines";
import type { LonLat, MapTagLine } from "../../map/scene";
import { bearingDegrees, destinationPoint, fromPosition, haversineMeters, pointAlongLine, projectOntoLine, type LatLon } from "../../nav/geo";

// The lines through a stop, from its departures (boards 1 and 7, 11 November 2026): one
// row per line and direction with its next departure, its colour and vehicle, and the
// stretch of its route ahead of the stop. Pure, so it unit-tests without the map.

export type Departure = DeparturesPage["data"][number];
type RouteItem = StopDetail["data"]["routes"][number];

export interface StopLine {
  /** One line in one direction: route and headsign. */
  key: string;
  routeId: string | null;
  /** What the badge says: the line number, or the train word for a train without one. */
  label: string;
  /** The place the line goes to, without the GTFS city prefix; null for a train number. */
  headsign: string | null;
  /** API mode ("BUS", "RAIL", "TRAM", …) for the vehicle icon. */
  mode: string;
  operatorId: string | null;
  operatorName: string | null;
  /** The next departure from this stop. */
  next: string;
  tripRef: string;
  callSequence: number;
  /** The direction and the headsign as the API sends them, to find the line's pattern. */
  directionId: string | null;
  rawHeadsign: string | null;
}

/** GTFS route_type to the API's mode words (basic and extended types). */
export function modeOfRouteType(routeType: number | null | undefined): string {
  if (routeType === null || routeType === undefined) return "BUS";
  if (routeType === 0 || (routeType >= 900 && routeType < 1000)) return "TRAM";
  if (routeType === 1 || (routeType >= 400 && routeType < 500)) return "SUBWAY";
  if (routeType === 2 || (routeType >= 100 && routeType < 200)) return "RAIL";
  return "BUS";
}

const text = (value: unknown): string | null => (typeof value === "string" && value.trim() !== "" ? value.trim() : null);

/**
 * GTFS headsigns join city and place with "_" ("תל אביב יפו_מסוף רדינג"); the boards name
 * the place only. A number alone is a train number, not a destination.
 */
export function shortHeadsign(headsign: string | null | undefined): string | null {
  const parts = (headsign ?? "").split("_").map((part) => part.trim()).filter(Boolean);
  const place = parts[parts.length - 1] ?? null;
  return place === null || /^\d+$/.test(place) ? null : place;
}

/**
 * Who runs a departure and with what: the departure's own operator and mode when the API
 * sends them (being added to departures), else the stop's route data, else a neutral bus.
 */
export function lineOf(departure: Departure, routes: readonly RouteItem[], trainLabel: string): Omit<StopLine, "key"> {
  const extra = departure as Record<string, unknown>;
  const route = routes.find((item) => item.routeId === departure.routeId);
  const mode = text(extra.mode) ?? modeOfRouteType(route?.routeType);
  const label = departure.routeShortName.trim() || (vehicleOf(mode) === "bus" ? "?" : trainLabel);
  return {
    routeId: departure.routeId,
    label,
    headsign: shortHeadsign(departure.headsign),
    mode,
    operatorId: text(extra.operatorId) ?? route?.operatorId ?? null,
    operatorName: text(extra.operatorName),
    next: departure.scheduledDeparture,
    tripRef: departure.tripRef,
    callSequence: departure.callSequence,
    directionId: text(extra.directionId),
    rawHeadsign: departure.headsign,
  };
}

type LineItem = StopLines["data"][number];
export type LinePattern = LineItem["patterns"][number];

/** The stop's routes as the lines endpoint describes them, for lineOf's fallbacks. */
export function routesOfLines(lines: readonly LineItem[]): RouteItem[] {
  return lines.map((line) => ({
    routeId: line.routeId,
    sourceId: line.routeId,
    operatorId: line.operatorId,
    routeShortName: line.routeShortName,
    routeLongName: null,
    routeType: line.routeType ?? 3,
    color: null,
    textColor: null,
  }));
}

/**
 * The pattern a departure's line follows through this stop (board 7): same route, then the
 * same direction, then the same headsign; null when the stop's lines do not include it.
 */
export function patternFor(line: StopLine, lines: readonly LineItem[]): LinePattern | null {
  const serving = (lines.find((item) => item.routeId === line.routeId)?.patterns ?? []).filter(
    (pattern) => pattern.servesStop && pattern.stopIndex !== null && pattern.stops.length >= 2,
  );
  return (
    serving.find((pattern) => pattern.directionId === line.directionId && pattern.headsign === line.rawHeadsign) ??
    serving.find((pattern) => line.directionId !== null && pattern.directionId === line.directionId) ??
    serving.find((pattern) => pattern.headsign === line.rawHeadsign) ??
    serving[0] ??
    null
  );
}

/** A pattern drawn from its stops in order (geometry "stop_sequence"). */
export function patternLine(pattern: LinePattern): LonLat[] {
  return pattern.stops.map((stop) => [stop.longitude, stop.latitude] as LonLat);
}

/** The part of a pattern from the stop onward: the line's way out of it. */
export function patternAhead(pattern: LinePattern, stop: LatLon): LonLat[] | null {
  const index = pattern.stopIndex ?? -1;
  if (index < 0 || index >= pattern.stops.length - 1) return null;
  return [toLonLat(stop), ...patternLine(pattern).slice(index + 1)];
}

/** One row per line and direction, by next departure; departures already left are dropped. */
export function groupLines(
  departures: readonly Departure[],
  routes: readonly RouteItem[],
  options: { trainLabel: string; now: Date; max?: number },
): StopLine[] {
  const now = options.now.getTime();
  const sorted = [...departures]
    .filter((item) => Date.parse(item.scheduledDeparture) >= now - 30_000)
    .sort((a, b) => Date.parse(a.scheduledDeparture) - Date.parse(b.scheduledDeparture));
  const lines = new Map<string, StopLine>();
  for (const departure of sorted) {
    const key = `${departure.routeId ?? departure.routeShortName}|${departure.headsign ?? ""}`;
    if (!lines.has(key)) lines.set(key, { key, ...lineOf(departure, routes, options.trainLabel) });
  }
  return [...lines.values()].slice(0, options.max ?? Infinity);
}

/** The badge a line shows on a map tag. */
export function tagLine(line: StopLine): MapTagLine {
  return { mode: line.mode, label: line.label, operatorId: line.operatorId, operatorName: line.operatorName };
}

/** Whole minutes until a departure (0 once it is due). */
export function minutesTo(instant: string, now: Date): number {
  return Math.max(0, Math.ceil((Date.parse(instant) - now.getTime()) / 60_000));
}

const toLonLat = (point: LatLon): LonLat => [point.longitude, point.latitude];

/**
 * The line's route from the stop onward (its direction of travel): the trip's shape cut
 * where the stop projects onto it. Null without a shape, or when the stop is not on it.
 */
export function routeAhead(shape: Trip["data"]["shape"], stop: LatLon): LonLat[] | null {
  const line = (shape?.coordinates ?? []).filter((point) => point.length >= 2) as LonLat[];
  if (line.length < 2) return null;
  const projection = projectOntoLine(stop, line);
  // A shape that never comes within 300 m of the stop is some other pass or a bad match.
  if (!projection || projection.distanceMeters > 300) return null;
  const start = pointAlongLine(line, projection.alongMeters);
  const ahead = [start ? toLonLat(start) : line[projection.segment]!, ...line.slice(projection.segment + 1)];
  return ahead.length >= 2 ? ahead : null;
}

/** The first `meters` of a line (a line's fan out of the stop). */
export function firstStretch(line: readonly LonLat[], meters: number): LonLat[] {
  if (line.length < 2) return [...line];
  const out: LonLat[] = [line[0]!];
  let left = meters;
  for (let i = 1; i < line.length; i += 1) {
    const a = fromPosition(line[i - 1]!);
    const b = fromPosition(line[i]!);
    const length = haversineMeters(a, b);
    if (length >= left) {
      const t = length > 0 ? left / length : 0;
      out.push([a.longitude + (b.longitude - a.longitude) * t, a.latitude + (b.latitude - a.latitude) * t]);
      return out;
    }
    out.push(line[i]!);
    left -= length;
  }
  return out;
}

const ARROWS = ["↑", "↗", "→", "↘", "↓", "↙", "←", "↖"] as const;

/**
 * Where to put the direction arrow on a chosen line, and which way it points (the map is
 * north-up and never rotates): a little way out of the stop.
 */
export function directionMark(line: readonly LonLat[], atMeters = 260): { position: LonLat; arrow: string } | null {
  const a = pointAlongLine(line, atMeters - 40);
  const b = pointAlongLine(line, atMeters + 40);
  if (!a || !b || haversineMeters(a, b) < 1) return null;
  const bearing = bearingDegrees(a, b);
  const at = pointAlongLine(line, atMeters)!;
  return { position: toLonLat(at), arrow: ARROWS[Math.round((((bearing % 360) + 360) % 360) / 45) % 8]! };
}

/**
 * A spot near the stop for the tag of a line with no route shape: `count` such tags are
 * spread evenly around it, starting north-north-east, far enough apart not to overlap.
 */
export function spotAround(stop: LatLon, index: number, count: number, meters = 260): LonLat {
  return toLonLat(destinationPoint(stop, (20 + (index * 360) / Math.max(1, count)) % 360, meters));
}

/** The calls after the stop's own call: the stops the chosen line goes on to. */
export function callsAhead(trip: Trip["data"], callSequence: number, max: number): Trip["data"]["calls"] {
  return trip.calls.filter((call) => call.callSequence > callSequence).slice(0, max);
}

/** A call's own coordinates, when the trip carries them (the API is adding them). */
export function callPosition(call: Trip["data"]["calls"][number]): LonLat | null {
  const extra = call as Record<string, unknown>;
  const lat = extra.latitude;
  const lon = extra.longitude;
  return typeof lat === "number" && typeof lon === "number" ? [lon, lat] : null;
}
