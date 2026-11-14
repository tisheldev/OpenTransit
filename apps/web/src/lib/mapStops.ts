import { useSyncExternalStore } from "react";
import { loadLocalState, updateLocalState } from "../storage/local";

// Which stops Home's map shows at neighbourhood zoom (user, 15 November 2026, trying the map
// on real data: "this way too bloated ... I want to see the map"). Below street zoom the
// stops the sheet lists are always full signs; "dots" draws every other stop as a small
// muted dot (option A), "listed" draws none (option C). From street zoom every stop is a
// sign either way. A switch in Settings while the user decides between the two; kept in
// local settings, absent meaning "dots".

export type MapStops = "dots" | "listed";
export const MAP_STOPS: readonly MapStops[] = ["dots", "listed"];
export const DEFAULT_MAP_STOPS: MapStops = "dots";

let current: MapStops | undefined;
const listeners = new Set<() => void>();

export function getMapStops(): MapStops {
  current ??= loadLocalState().state.settings.mapStops ?? DEFAULT_MAP_STOPS;
  return current;
}

/** Choose (Settings): stored locally, and the map redraws at once. */
export function setMapStops(value: MapStops): void {
  current = value;
  updateLocalState((state) => ({ ...state, settings: { ...state.settings, mapStops: value } }));
  for (const listener of listeners) listener();
}

/** Forget the in-memory choice (tests; clear all local data). */
export function resetMapStops(): void {
  current = undefined;
  for (const listener of listeners) listener();
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function useMapStops(): MapStops {
  return useSyncExternalStore(subscribe, getMapStops, getMapStops);
}
