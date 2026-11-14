import { useSyncExternalStore } from "react";
import type { LonLat, MapKnownStop } from "../scene";
import type { Bounds } from "./area";

// What the stops layer shares with the screens, outside the lazy map chunk (no MapLibre):
// where the map last settled (Home's "In this area", board 10), the group the passenger
// opened (board 9), and whether Home's map is away from the passenger (the Locate button
// reads "אליי"). Memory only; nothing here is stored.

export interface SettledView {
  /** The centre of the part of the map above the sheet. */
  center: LonLat;
  zoom: number;
  /** The visible part of the map. */
  bounds: Bounds;
}

export interface OpenGroup {
  stops: MapKnownStop[];
  center: LonLat;
  /** The row picked in the list, drawn as the chosen stop. */
  picked: string | null;
}

interface StopsViewState {
  settled: SettledView | null;
  group: OpenGroup | null;
  away: boolean;
}

let state: StopsViewState = { settled: null, group: null, away: false };
const listeners = new Set<() => void>();

function update(change: Partial<StopsViewState>): void {
  state = { ...state, ...change };
  for (const listener of listeners) listener();
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function getStopsView(): StopsViewState {
  return state;
}

export function setSettledView(settled: SettledView | null): void {
  update({ settled });
}

export function openStopGroup(stops: MapKnownStop[], picked: string | null = null): void {
  const lon = stops.reduce((sum, stop) => sum + stop.longitude, 0) / Math.max(1, stops.length);
  const lat = stops.reduce((sum, stop) => sum + stop.latitude, 0) / Math.max(1, stops.length);
  update({ group: { stops, center: [lon, lat], picked } });
}

export function pickInGroup(stopId: string | null): void {
  if (state.group && state.group.picked !== stopId) update({ group: { ...state.group, picked: stopId } });
}

export function closeStopGroup(): void {
  if (state.group) update({ group: null });
}

export function setMapAway(away: boolean): void {
  if (state.away !== away) update({ away });
}

function useSelect<T>(select: (current: StopsViewState) => T): T {
  const read = () => select(state);
  return useSyncExternalStore(subscribe, read, read);
}

export const useSettledView = () => useSelect((current) => current.settled);
export const useOpenGroup = () => useSelect((current) => current.group);
export const useMapAway = () => useSelect((current) => current.away);

/** Reset between tests. */
export function resetStopsView(): void {
  state = { settled: null, group: null, away: false };
  for (const listener of listeners) listener();
}
