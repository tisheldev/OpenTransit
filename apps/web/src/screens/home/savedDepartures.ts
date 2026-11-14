import { useMemo } from "react";
import { useStopsDepartures } from "../../api/queries";
import type { SavedLine, SavedStop } from "../../storage/local";
import { groupLines, shortHeadsign, type Departure, type StopLine } from "../stop/lines";
import type { NearStopDepartures } from "./homeStops";

// The next departures of Home's saved stops and lines (board 1: "דיזנגוף סנטר · 2 1 · 8 2
// דק׳", "8 מסוף הטייסים · 2 דק׳ · מדיזנגוף סנטר"). A stop the nearby answer already holds
// reuses it; any other stop costs one departures request, made only after the nearby
// answer settled, shared by a saved stop and the saved lines caught there, and cached and
// refreshed with the other departures (once a minute). Home shows at most HOME_SAVED_MAX
// saved items, so this stays a handful of standard requests a minute (client design,
// "Request limits").

/** Saved stops and lines shown on Home, after Home and Work (three rows of two). */
export const HOME_SAVED_MAX = 6;
/** Lines a saved stop's card names (as drawn: two). */
export const SAVED_STOP_LINES = 2;
const SAVED_WINDOW = { limit: 30, horizonMinutes: 90 };

export interface StopNext {
  departures: Departure[] | null;
  routes: NearStopDepartures["routes"];
}

/** A saved line's departures at its stop: same number and operator, and the saved direction. */
export function savedLineDepartures(line: SavedLine, departures: readonly Departure[]): Departure[] {
  const same = departures.filter((departure) => {
    if (departure.routeShortName.trim() !== line.shortName.trim()) return false;
    const operatorId = (departure as Record<string, unknown>).operatorId;
    return typeof operatorId !== "string" || line.operatorId === null || operatorId === line.operatorId;
  });
  if (line.destinationName === null && line.routeIdHint === null) return same;
  return same.filter(
    (departure) =>
      (line.routeIdHint !== null && departure.routeId === line.routeIdHint) ||
      (line.destinationName !== null && shortHeadsign(departure.headsign) === shortHeadsign(line.destinationName)),
  );
}

/** The next line rows for a saved stop's card. */
export function savedStopLines(next: StopNext | undefined, now: Date, trainLabel: string): StopLine[] {
  if (!next?.departures) return [];
  return groupLines(next.departures, next.routes, { trainLabel, now, max: SAVED_STOP_LINES });
}

/** The next departure of a saved line, or null when none is known. */
export function savedLineNext(line: SavedLine, next: StopNext | undefined, now: Date, trainLabel: string): StopLine | null {
  if (!next?.departures) return null;
  return groupLines(savedLineDepartures(line, next.departures), next.routes, { trainLabel, now, max: 1 })[0] ?? null;
}

/**
 * Departures for every stop a shown saved item needs, by stop id. `nearbySettled` holds the
 * extra requests back until the nearby answer is known (it may already cover the stop).
 */
export function useSavedDepartures(
  stops: readonly SavedStop[],
  lines: readonly SavedLine[],
  nearby: readonly NearStopDepartures[],
  options: { enabled: boolean; nearbySettled: boolean; now: Date; trainLabel: string },
): Map<string, StopNext> {
  const held = useMemo(() => {
    const map = new Map<string, StopNext>();
    for (const entry of nearby) if (entry.departures) map.set(entry.stop.stopId, { departures: entry.departures, routes: entry.routes });
    return map;
  }, [nearby]);

  const { now, trainLabel } = options;
  const needed = useMemo(() => {
    const ids = new Set<string>();
    for (const stop of stops) if (!held.has(stop.stopId)) ids.add(stop.stopId);
    for (const line of lines) {
      if (line.stopId === null) continue;
      // The nearby answer names a few lines per stop: ask the stop itself when it lacks this one.
      if (!held.has(line.stopId) || savedLineNext(line, held.get(line.stopId), now, trainLabel) === null) ids.add(line.stopId);
    }
    return [...ids].sort();
    // `now` moves every minute; re-deciding then is what keeps a line that left covered.
  }, [stops, lines, held, now, trainLabel]);

  const fetched = useStopsDepartures(needed, SAVED_WINDOW, options.enabled && options.nearbySettled);

  return useMemo(() => {
    const map = new Map(held);
    needed.forEach((stopId, index) => {
      const data = fetched[index]?.data;
      if (data) map.set(stopId, { departures: data, routes: [] });
    });
    return map;
  }, [held, needed, fetched]);
}
