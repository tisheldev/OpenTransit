import { useSyncExternalStore } from "react";
import { recentId, savedFromChoice, type PlaceChoice } from "../plan/draft";
import { loadLocalState, updateLocalState, withRecent, type LocalState, type SavedPlace } from "../storage/local";

// A reactive view of storage/local.ts for Home, Search and Settings: read synchronously
// before the first frame (design: Home, "storage only"), written through on change.

let snapshot: LocalState | null = null;
const listeners = new Set<() => void>();

function get(): LocalState {
  if (snapshot === null) snapshot = loadLocalState().state;
  return snapshot;
}

function notify(): void {
  for (const listener of listeners) listener();
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function useLocalState(): LocalState {
  return useSyncExternalStore(subscribe, get, get);
}

/** Apply a change and persist it. False when the result is invalid (e.g. outside Israel). */
export function changeLocal(change: (state: LocalState) => LocalState): boolean {
  try {
    snapshot = updateLocalState(change);
  } catch {
    return false;
  }
  notify();
  return true;
}

/** Re-read storage (after "clear all", and between tests). */
export function reloadLocalState(): void {
  snapshot = null;
  notify();
}

export type SavedSlot = "home" | "work";

/** Within the bounds storage accepts (storage/local.ts SavedPlaceSchema). */
export function storable(choice: PlaceChoice): boolean {
  return choice.latitude >= 29 && choice.latitude <= 34 && choice.longitude >= 34 && choice.longitude <= 36;
}

export function addRecent(choice: PlaceChoice): boolean {
  if (!storable(choice)) return false;
  return changeLocal((state) => withRecent(state, savedFromChoice(choice, recentId(choice))));
}

export function saveSlot(slot: SavedSlot, choice: PlaceChoice, label?: string): boolean {
  if (!storable(choice)) return false;
  const saved = savedFromChoice(choice, slot);
  return changeLocal((state) => ({ ...state, [slot]: label ? { ...saved, label } : saved }));
}

export function addFavourite(choice: PlaceChoice, label: string, now: Date = new Date()): boolean {
  if (!storable(choice)) return false;
  const saved: SavedPlace = { ...savedFromChoice(choice, `fav-${now.getTime().toString(36)}-${Math.random().toString(36).slice(2, 6)}`, now), label };
  return changeLocal((state) => ({ ...state, favourites: [...state.favourites, saved].slice(0, 50) }));
}

/** Rename Home, Work or a favourite (by id). */
export function renameSaved(id: string, label: string): boolean {
  const trimmed = label.trim().slice(0, 200);
  if (!trimmed) return false;
  return changeLocal((state) => ({
    ...state,
    home: state.home?.id === id ? { ...state.home, label: trimmed } : state.home,
    work: state.work?.id === id ? { ...state.work, label: trimmed } : state.work,
    favourites: state.favourites.map((item) => (item.id === id ? { ...item, label: trimmed } : item)),
  }));
}

export function deleteSaved(id: string): boolean {
  return changeLocal((state) => ({
    ...state,
    home: state.home?.id === id ? null : state.home,
    work: state.work?.id === id ? null : state.work,
    favourites: state.favourites.filter((item) => item.id !== id),
  }));
}
